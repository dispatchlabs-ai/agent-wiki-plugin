import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import tomllib
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py"
spec = importlib.util.spec_from_file_location("wiki_connection", SCRIPT)
connection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(connection)


class EndpointTests(unittest.TestCase):
    def test_domain_and_explicit_endpoint(self):
        for supplied, expected in (
            ("wiki.example.com", "https://wiki.example.com/mcp"),
            ("https://WIKI.example.com/", "https://wiki.example.com/mcp"),
            ("wiki.example.com:8443", "https://wiki.example.com:8443/mcp"),
            ("https://example.com/tenant/mcp", "https://example.com/tenant/mcp"),
            ("https://bücher.example", "https://xn--bcher-kva.example/mcp"),
            ("https://[::1]:8443", "https://[::1]:8443/mcp"),
        ):
            with self.subTest(supplied=supplied):
                self.assertEqual(connection.normalize_endpoint(supplied), expected)

    def test_rejects_secret_bearing_and_ambiguous_urls(self):
        for supplied in (
            "", "ftp://wiki.example.com", "http://wiki.example.com",
            "https://user:secret@wiki.example.com/mcp", "https://wiki.example.com/mcp?token=secret",
            "https://wiki.example.com/#secret", "wiki.example.com\\@evil.example",
            "https://wiki.example.com:invalid", "https://wiki.example.com:0",
            "https://wiki.example.com/../mcp", "https://wiki.example.com/%2e%2e/mcp",
            "https://wiki.example.com/\ninjected", "https://wiki..example.com",
        ):
            with self.subTest(supplied=supplied), self.assertRaises(connection.SetupError) as raised:
                connection.normalize_endpoint(supplied)
            self.assertNotIn("secret", str(raised.exception))

    def test_http_requires_explicit_loopback_opt_in(self):
        with self.assertRaises(connection.SetupError):
            connection.normalize_endpoint("http://127.0.0.1:4000")
        self.assertEqual(connection.normalize_endpoint("http://127.0.0.1:4000", True), "http://127.0.0.1:4000/mcp")
        for supplied in ("http://10.0.0.1", "http://localhost.example.com", "http://example.com"):
            with self.subTest(supplied=supplied), self.assertRaises(connection.SetupError):
                connection.normalize_endpoint(supplied, True)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name) / "client"
        self.home.mkdir()
        self.path = self.home / "config.toml"
        self.url = "https://wiki.example.com/mcp"

    def test_preserves_unrelated_configuration_and_is_idempotent(self):
        original = '# Personal settings\nmodel = "chosen-model"\n[mcp_servers.other]\nurl = "https://other.example/mcp"\n[projects."/some/path"]\ntrust_level = "trusted"\n'
        self.path.write_text(original)
        self.path.chmod(0o600)
        result = connection.configure(self.home, "agent_wiki", self.url)
        first = self.path.read_text()
        self.assertTrue(first.startswith(original))
        parsed = tomllib.loads(first)
        self.assertEqual(parsed["mcp_servers"]["other"]["url"], "https://other.example/mcp")
        self.assertEqual(parsed["model"], "chosen-model")
        self.assertEqual(parsed["mcp_servers"]["agent_wiki"]["enabled_tools"], ["wiki.search", "wiki.read", "wiki.history", "wiki.preview", "wiki.save"])
        self.assertEqual(parsed["mcp_servers"]["agent_wiki"]["scopes"], ["wiki:read", "wiki:write"])
        self.assertNotIn("trace", first)
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertTrue(result["changed"])
        self.assertFalse(connection.configure(self.home, "agent_wiki", self.url)["changed"])
        self.assertEqual(first, self.path.read_text())

    def test_dry_run_does_not_create_a_client_home(self):
        home = self.home / "does-not-exist"
        self.assertEqual(connection.configure(home, "agent_wiki", self.url, True)["state"], "planned")
        self.assertFalse(home.exists())

    def test_crlf_unrelated_content_is_preserved_byte_for_byte(self):
        original = b'# Preserve line endings\r\nmodel = "chosen-model"\r\n'
        self.path.write_bytes(original)
        connection.configure(self.home, "agent_wiki", self.url)
        self.assertTrue(self.path.read_bytes().startswith(original))

    def test_native_appended_tables_inside_markers_are_preserved(self):
        connection.configure(self.home, "agent_wiki", self.url)
        closing = connection.markers("agent_wiki")[1]
        unrelated = '[projects."/synthetic/workspace"]\ntrust_level = "trusted"\n\n[plugins."agent-wiki@agent-wiki-plugins"]\nenabled = true\n'
        self.path.write_text(self.path.read_text().replace(closing, unrelated + closing))
        before = self.path.read_bytes()
        self.assertEqual(connection.status(self.home, "agent_wiki")["state"], "configured")
        self.assertFalse(connection.configure(self.home, "agent_wiki", self.url)["changed"])
        self.assertEqual(self.path.read_bytes(), before)
        with patch.object(connection, "native_auth"):
            self.assertEqual(connection.disconnect(self.home, "agent_wiki")["state"], "disconnected")
        self.assertIn(unrelated, self.path.read_text())
        self.assertNotIn("agent-wiki-plugin:agent_wiki", self.path.read_text())
        self.assertEqual(tomllib.loads(self.path.read_text()), tomllib.loads(unrelated))

    def test_unmanaged_server_and_inline_table_conflict_preserve_bytes(self):
        for original in (
            '[mcp_servers.agent_wiki]\nurl = "https://existing.example/mcp"\n',
            'mcp_servers = { other = { url = "https://other.example/mcp" } }\n',
            'invalid = [\n',
        ):
            with self.subTest(original=original):
                self.path.write_text(original)
                with self.assertRaises(connection.SetupError):
                    connection.configure(self.home, "agent_wiki", self.url)
                self.assertEqual(self.path.read_text(), original)

    def test_changing_domain_does_not_reuse_connection(self):
        connection.configure(self.home, "agent_wiki", self.url)
        original = self.path.read_text()
        with self.assertRaises(connection.SetupError) as raised:
            connection.configure(self.home, "agent_wiki", "https://another.example/mcp")
        self.assertEqual(raised.exception.code, "SERVER_CHANGE")
        self.assertEqual(self.path.read_text(), original)
        connection.configure(self.home, "other_wiki", "https://another.example/mcp")
        self.assertEqual(len(tomllib.loads(self.path.read_text())["mcp_servers"]), 2)

    def test_unfamiliar_managed_fields_are_not_overwritten(self):
        connection.configure(self.home, "agent_wiki", self.url)
        original = self.path.read_text().replace('scopes = ', 'bearer_token_env_var = "PRIVATE_TOKEN"\nscopes = ')
        self.path.write_text(original)
        with self.assertRaises(connection.SetupError):
            connection.configure(self.home, "agent_wiki", self.url)
        self.assertEqual(self.path.read_text(), original)

    def test_symlink_is_not_followed(self):
        target = self.home / "managed.toml"
        target.write_text('model = "unchanged"\n')
        self.path.symlink_to(target)
        with self.assertRaises(connection.SetupError):
            connection.configure(self.home, "agent_wiki", self.url)
        self.assertEqual(target.read_text(), 'model = "unchanged"\n')

    def test_native_login_uses_scoped_arguments_and_isolated_home(self):
        connection.configure(self.home, "agent_wiki", self.url)
        with patch.object(connection.shutil, "which", return_value="/native/codex"), patch.object(connection.subprocess, "run") as run:
            run.return_value.returncode = 0
            connection.native_auth(self.home, "agent_wiki", "login")
            self.assertEqual(run.call_args.args[0], ["/native/codex", "mcp", "login", "agent_wiki", "--scopes", "wiki:read,wiki:write"])
            self.assertEqual(run.call_args.kwargs["env"]["CODEX_HOME"], str(self.home))
            self.assertEqual(run.call_args.kwargs["cwd"], self.home)

    def test_failed_auth_preserves_connection_and_disconnect_preserves_other_settings(self):
        self.path.write_text('model = "keep-me"\n')
        connection.configure(self.home, "agent_wiki", self.url)
        original = self.path.read_text()
        with patch.object(connection.shutil, "which", return_value="/native/codex"), patch.object(connection.subprocess, "run") as run:
            run.return_value.returncode = 1
            with self.assertRaises(connection.SetupError):
                connection.disconnect(self.home, "agent_wiki")
            self.assertEqual(self.path.read_text(), original)
            run.return_value.returncode = 0
            self.assertEqual(connection.disconnect(self.home, "agent_wiki")["state"], "disconnected")
        self.assertEqual(tomllib.loads(self.path.read_text()), {"model": "keep-me"})

    @unittest.skipUnless(shutil.which("codex"), "native Codex CLI not installed")
    def test_native_client_accepts_generated_configuration(self):
        connection.configure(self.home, "agent_wiki", self.url)
        env = {**os.environ, "CODEX_HOME": str(self.home)}
        result = subprocess.run(["codex", "mcp", "get", "agent_wiki", "--json"], env=env, cwd=self.home, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(config["transport"]["url"], self.url)
        self.assertEqual(set(config["enabled_tools"]), set(connection.TOOLS))
        # The native get JSON omits scopes. Runtime scopes are checked by the
        # optional real-server OAuth integration test, not inferred here.


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.code = 401
        self.response = {}
        self.streaming = False
        test = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                test.requests.append((self.path, dict(self.headers), json.loads(body)))
                self.send_response(test.code)
                self.send_header("Content-Type", "text/event-stream" if test.streaming else "application/json")
                if test.code == 401:
                    self.send_header("WWW-Authenticate", 'Bearer resource_metadata="https://wiki.example/.well-known/oauth-protected-resource/mcp"')
                if test.code == 302:
                    self.send_header("Location", "/redirect-target")
                self.end_headers()
                data = json.dumps(test.response).encode()
                self.wfile.write(b": keepalive\n\nevent: message\ndata: " + data + b"\n\n" if test.streaming else data)

            def log_message(self, *_):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.cleanup)
        self.endpoint = f"http://127.0.0.1:{self.server.server_port}/mcp"

    def cleanup(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_auth_challenge_needs_no_credentials_or_user_content(self):
        result = connection.probe(self.endpoint)
        self.assertEqual(result["authentication"], "required")
        path, headers, payload = self.requests[0]
        self.assertEqual(path, "/mcp")
        self.assertNotIn("Authorization", headers)
        self.assertNotIn("Cookie", headers)
        self.assertEqual(payload["method"], "initialize")
        self.assertEqual(set(payload["params"]), {"protocolVersion", "capabilities", "clientInfo"})

    def test_json_initialization_is_connectivity_not_tool_verification(self):
        self.code = 200
        self.response = {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "agent-wiki", "version": "test"}}}
        self.assertTrue(connection.probe(self.endpoint)["reachable"])
        self.assertFalse(connection.probe(self.endpoint)["tools_verified"])

    def test_redirect_is_not_followed(self):
        self.code = 302
        with self.assertRaises(connection.SetupError) as raised:
            connection.probe(self.endpoint)
        self.assertEqual(raised.exception.code, "REDIRECT_REFUSED")
        self.assertEqual(len(self.requests), 1)

    def test_streamed_initialization(self):
        self.code = 200
        self.streaming = True
        self.response = {"jsonrpc": "2.0", "id": 1, "result": {"serverInfo": {"name": "agent-wiki", "version": "test"}}}
        self.assertTrue(connection.probe(self.endpoint)["reachable"])

    def test_non_mcp_json_is_rejected(self):
        self.code = 200
        self.response = {"message": "ordinary website"}
        with self.assertRaises(connection.SetupError) as raised:
            connection.probe(self.endpoint)
        self.assertEqual(raised.exception.code, "NOT_MCP")

    def test_deeply_nested_untrusted_json_has_structured_error(self):
        import io
        response = io.BytesIO(b"[" * 200000 + b"0" + b"]" * 200000)
        response.headers = {"Content-Type": "application/json"}
        with patch.object(connection.urllib.request, "build_opener") as build:
            build.return_value.open.return_value = response
            with self.assertRaises(connection.SetupError) as raised:
                connection.probe(self.endpoint)
        self.assertEqual(raised.exception.code, "NOT_MCP")

        # JSON depth limits differ between Python versions; exercise the error
        # mapping deterministically as well as the actual untrusted response.
        with patch.object(connection.urllib.request, "build_opener"), patch.object(connection, "initialization_response", side_effect=RecursionError):
            with self.assertRaises(connection.SetupError) as raised:
                connection.probe(self.endpoint)
        self.assertEqual(raised.exception.code, "NOT_MCP")


if __name__ == "__main__":
    unittest.main()
