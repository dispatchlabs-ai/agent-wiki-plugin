#!/usr/bin/env python3
"""Configure a direct, article-only Agent Wiki connection in native Codex.

No runtime dependencies. Credentials are exclusively owned by the native client.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import tomllib
import urllib.error
import urllib.parse
import urllib.request

VERSION = "0.1.0-alpha.1"
TOOLS = ("wiki.search", "wiki.read", "wiki.history", "wiki.preview", "wiki.save")
SCOPES = ("wiki:read", "wiki:write")


class SetupError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def normalize_endpoint(value: str, allow_local_http: bool = False) -> str:
    value = value.strip()
    if not value or any(c.isspace() or ord(c) < 32 for c in value):
        raise SetupError("INVALID_URL", "Supply a domain or HTTPS MCP endpoint without whitespace.")
    if "\\" in value:
        raise SetupError("INVALID_URL", "Backslashes are not permitted in an endpoint.")
    if "://" not in value:
        value = "https://" + value
    try:
        parsed = urllib.parse.urlsplit(value)
        host = parsed.hostname
        port = parsed.port
        if not host or parsed.username is not None or parsed.password is not None:
            raise ValueError()
        if parsed.query or parsed.fragment or "?" in value or "#" in value:
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
            host = address.compressed
            loopback = address.is_loopback
            if address.version == 6:
                host = "[" + host + "]"
        except ValueError:
            host = host.encode("idna").decode("ascii").lower()
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host):
                raise ValueError()
            if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in host.split(".")):
                raise ValueError()
            loopback = host == "localhost"
        if parsed.scheme != "https" and not (
            parsed.scheme == "http" and allow_local_http and loopback
        ):
            raise SetupError("HTTPS_REQUIRED", "Use HTTPS. --allow-local-http permits only explicit loopback testing.")
        if port == 0:
            raise ValueError()
        path = parsed.path if parsed.path not in ("", "/") else "/mcp"
        if any(part in (".", "..") for part in urllib.parse.unquote(path).split("/")):
            raise ValueError()
        return urllib.parse.urlunsplit((parsed.scheme, host + (f":{port}" if port else ""), path, "", ""))
    except (ValueError, UnicodeError):
        raise SetupError("INVALID_URL", "Use a valid domain or endpoint without credentials, query parameters, fragments, or path traversal.") from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(endpoint: str) -> dict:
    """Send only protocol/client metadata; no credentials or user content."""
    payload = {
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                   "clientInfo": {"name": "agent-wiki-plugin-setup", "version": VERSION}},
    }
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode(), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"},
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=15) as response:
            result = initialization_response(response)
            if result.get("id") != 1 or not isinstance(result.get("result", {}).get("serverInfo"), dict):
                raise SetupError("NOT_MCP", "The endpoint did not return an MCP initialization result.")
            return {"reachable": True, "authentication": "not_challenged", "tools_verified": False}
    except urllib.error.HTTPError as error:
        error.close()
        if error.code == 401 and "resource_metadata=" in error.headers.get("WWW-Authenticate", ""):
            return {"reachable": True, "authentication": "required", "tools_verified": False}
        if 300 <= error.code < 400:
            raise SetupError("REDIRECT_REFUSED", "Use the server's canonical MCP URL; setup does not follow endpoint redirects.") from None
        raise SetupError("ENDPOINT_REJECTED", f"Endpoint returned HTTP {error.code}; verify its MCP path and authentication discovery.") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise SetupError("NETWORK_ERROR", "Cannot reach the endpoint. Check DNS, network access, and its trusted HTTPS certificate.") from None
    except (ValueError, AttributeError, RecursionError):
        raise SetupError("NOT_MCP", "The endpoint did not return a valid MCP initialization result.") from None


def initialization_response(response) -> dict:
    """Read one initialization result from either MCP HTTP response format."""
    budget = 1024 * 1024
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type:
        raw = response.read(budget + 1)
        if len(raw) <= budget:
            return json.loads(raw)
    elif "text/event-stream" in content_type:
        consumed = 0
        data = []
        while consumed <= budget:
            line = response.readline(budget + 1)
            if not line:
                break
            consumed += len(line)
            if consumed > budget:
                break
            if line.rstrip(b"\r\n") == b"":
                if data:
                    message = json.loads(b"\n".join(data))
                    if isinstance(message, dict) and message.get("id") == 1:
                        return message
                data = []
            elif line.startswith(b"data:"):
                data.append(line[5:].lstrip(b" ").rstrip(b"\r\n"))
        if consumed <= budget:
            raise SetupError("NOT_MCP", "The event stream ended without an MCP initialization result.")
    else:
        raise SetupError("UNVERIFIED_ENDPOINT", "Expected a JSON or event-stream MCP response. Verify the endpoint before using --skip-probe.")
    raise SetupError("UNVERIFIED_ENDPOINT", "MCP initialization response exceeds the probe's 1 MiB budget.")


def configuration(endpoint: str) -> dict:
    return {"url": endpoint, "enabled_tools": list(TOOLS), "scopes": list(SCOPES)}


def markers(name: str) -> tuple[str, str]:
    return (f"# >>> agent-wiki-plugin:{name} >>>", f"# <<< agent-wiki-plugin:{name} <<<")


def block(name: str, endpoint: str) -> str:
    start, end = markers(name)
    return "\n".join((start, f"[mcp_servers.{name}]", f"url = {json.dumps(endpoint)}",
                     f"enabled_tools = {json.dumps(list(TOOLS))}",
                     f"scopes = {json.dumps(list(SCOPES))}", end)) + "\n"


def read_config(path: Path) -> tuple[str, dict]:
    if path.is_symlink():
        raise SetupError("MANAGED_CONFIG", "The client configuration is a symlink. Use its owning configuration system.")
    try:
        if path.exists():
            with path.open(encoding="utf-8", newline="") as handle:
                text = handle.read()
        else:
            text = ""
        return text, tomllib.loads(text)
    except (UnicodeError, tomllib.TOMLDecodeError, RecursionError):
        raise SetupError("INVALID_CONFIG", "Existing client configuration is not valid UTF-8 TOML; it was not changed.") from None


def managed_range(text: str, name: str) -> tuple[int, int] | None:
    start, end = markers(name)
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == start]
    ends = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == end]
    if not starts and not ends:
        return None
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise SetupError("CONFIG_CONFLICT", "Connection markers are ambiguous; configuration was not changed.")
    return sum(map(len, lines[:starts[0]])), sum(map(len, lines[:ends[0] + 1]))


def inspect_connection(text: str, parsed: dict, name: str) -> tuple[dict | None, tuple[int, int] | None]:
    servers = parsed.get("mcp_servers", {})
    if not isinstance(servers, dict):
        raise SetupError("CONFIG_CONFLICT", "The existing mcp_servers setting is not a table.")
    existing = servers.get(name)
    span = managed_range(text, name)
    if existing is None and span is None:
        return None, None
    if span is None or not isinstance(existing, dict):
        raise SetupError("CONFIG_CONFLICT", "That connection is not managed by this helper. Preserve it and choose a different --name.")
    try:
        section = tomllib.loads(text[span[0]:span[1]])
    except tomllib.TOMLDecodeError:
        raise SetupError("CONFIG_CONFLICT", "Connection markers do not delimit an independent TOML table; nothing was changed.") from None
    if section != {"mcp_servers": {name: existing}} or not isinstance(existing.get("url"), str) or existing != configuration(existing["url"]):
        raise SetupError("CONFIG_CONFLICT", "The managed connection contains unfamiliar settings. Preserve it and review the configuration manually.")
    return existing, span


@contextlib.contextmanager
def config_lock(home: Path):
    home.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = home / ".agent-wiki-plugin.lock"
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock, flags, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SetupError("CONFIG_BUSY", "Another setup process is editing this client configuration; retry after it finishes.") from None
        yield
    finally:
        os.close(fd)


def atomic_config(path: Path, previous: str, updated: str) -> None:
    try:
        tomllib.loads(updated)
    except tomllib.TOMLDecodeError:
        raise SetupError("CONFIG_CONFLICT", "Adding this connection would conflict with the existing TOML layout; nothing was changed.") from None
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=".agent-wiki-", suffix=".toml", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        current, _ = read_config(path)
        if current != previous:
            raise SetupError("CONFIG_CHANGED", "Client configuration changed during setup; nothing was replaced. Retry with the current file.")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configure(home: Path, name: str, endpoint: str, dry_run: bool = False) -> dict:
    with contextlib.nullcontext() if dry_run else config_lock(home):
        path = home / "config.toml"
        text, parsed = read_config(path)
        existing, _ = inspect_connection(text, parsed, name)
        if existing:
            if existing["url"] != endpoint:
                raise SetupError("SERVER_CHANGE", "This name already points to another server. Use a new --name, or disconnect the old connection first.")
            changed = False
        else:
            updated = text + ("\n" if text and not text.endswith("\n") else "") + "\n" + block(name, endpoint)
            try:
                tomllib.loads(updated)
            except tomllib.TOMLDecodeError:
                raise SetupError("CONFIG_CONFLICT", "Existing TOML layout conflicts with this connection. Nothing was changed.") from None
            changed = True
            if not dry_run:
                atomic_config(path, text, updated)
        return {"state": "planned" if dry_run else "configured", "changed": changed,
                "name": name, "endpoint": endpoint, "config": str(path),
                "tools": list(TOOLS), "scopes": list(SCOPES), "authentication": "unverified"}


def status(home: Path, name: str) -> dict:
    text, parsed = read_config(home / "config.toml")
    existing, _ = inspect_connection(text, parsed, name)
    return {"state": "configured" if existing else "not_configured", "name": name,
            "endpoint": existing["url"] if existing else None,
            "config": str(home / "config.toml"), "authentication": "unverified",
            "tools": existing["enabled_tools"] if existing else [],
            "scopes": existing["scopes"] if existing else []}


def native_auth(home: Path, name: str, action: str) -> None:
    if status(home, name)["state"] != "configured":
        raise SetupError("NOT_CONFIGURED", "Configure the connection before authenticating.")
    executable = shutil.which("codex")
    if executable is None:
        raise SetupError("CODEX_MISSING", "Install the native Codex CLI, then retry login. Configuration is preserved.")
    command = [executable, "mcp", action, name]
    if action == "login":
        command.extend(["--scopes", ",".join(SCOPES)])
    environment = dict(os.environ)
    environment["CODEX_HOME"] = str(home)
    result = subprocess.run(command, env=environment, cwd=home, stdout=sys.stderr, stderr=sys.stderr)
    if result.returncode != 0:
        raise SetupError("AUTH_INCOMPLETE", f"Native {action} did not complete. Configuration was preserved; retry when ready.")


def disconnect(home: Path, name: str) -> dict:
    # Native logout needs the old connection available. Recheck its identity afterwards.
    before = status(home, name)
    if before["state"] == "not_configured":
        return {"state": "not_configured", "name": name, "changed": False}
    native_auth(home, name, "logout")
    with config_lock(home):
        path = home / "config.toml"
        text, parsed = read_config(path)
        existing, span = inspect_connection(text, parsed, name)
        if existing is None or existing["url"] != before["endpoint"]:
            raise SetupError("CONFIG_CHANGED", "Connection changed during logout. Configuration was not removed.")
        atomic_config(path, text, text[:span[0]] + text[span[1]:])
    return {"state": "disconnected", "name": name, "changed": True}


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--version", action="version", version=VERSION)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--name", default="agent_wiki", help="Dedicated MCP connection name (default: agent_wiki)")
    common.add_argument("--codex-home", type=Path, help="Native Codex configuration home; defaults to CODEX_HOME or ~/.codex")
    actions = root.add_subparsers(dest="action", required=True)
    connect = actions.add_parser("connect", parents=[common], help="Check and configure your wiki, then start native sign-in")
    connect.add_argument("server", help="Domain, HTTPS origin, or full HTTPS MCP URL")
    connect.add_argument("--no-login", action="store_true", help="Configure only; authentication remains unverified")
    connect.add_argument("--skip-probe", action="store_true", help="Leave endpoint connectivity unverified")
    connect.add_argument("--dry-run", action="store_true", help="Plan configuration without network access or sign-in")
    connect.add_argument("--allow-local-http", action="store_true", help="Allow HTTP only for explicit loopback testing")
    for command in ("status", "login", "disconnect"):
        actions.add_parser(command, parents=[common])
    check = actions.add_parser("probe", help="Check an endpoint without credentials or user content")
    check.add_argument("server")
    check.add_argument("--allow-local-http", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.action == "probe":
            endpoint = normalize_endpoint(args.server, args.allow_local_http)
            result = {"endpoint": endpoint, **probe(endpoint)}
        else:
            if not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", args.name):
                raise SetupError("INVALID_NAME", "Use a lowercase connection name beginning with a letter, containing letters, digits, or underscores.")
            home = (args.codex_home or Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))).expanduser().absolute()
            if args.action == "connect":
                endpoint = normalize_endpoint(args.server, args.allow_local_http)
                inspection = {"reachable": "unverified", "tools_verified": False}
                if not args.skip_probe and not args.dry_run:
                    inspection = probe(endpoint)
                result = configure(home, args.name, endpoint, args.dry_run)
                result["probe"] = inspection
                if not args.no_login and not args.dry_run:
                    native_auth(home, args.name, "login")
                    result["authentication"] = "native_login_completed"
                result["next_step"] = "Start a fresh client session, verify article tools, and run a read-only wiki search."
            elif args.action == "status":
                result = status(home, args.name)
            elif args.action == "login":
                native_auth(home, args.name, "login")
                result = {**status(home, args.name), "authentication": "native_login_completed"}
            else:
                result = disconnect(home, args.name)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except SetupError as error:
        print(json.dumps({"state": "error", "code": error.code, "message": str(error)}))
        return 1
    except (OSError, KeyboardInterrupt):
        print(json.dumps({"state": "error", "code": "LOCAL_OPERATION_FAILED", "message": "Local setup could not complete. Check file permissions and retry; inspect status before continuing."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
