---
name: connect-wiki
description: Connect, inspect, or disconnect a user's own Agent Wiki when they provide a domain or MCP URL, or ask to set up wiki memory. Configures a dedicated article-only native MCP connection for local Codex clients and explains the separate ChatGPT web setup.
---

Connect the user's chosen wiki directly. Ask for its domain or endpoint only if it is missing. Keep the server choice in the user's native client configuration; never edit the installed plugin to store it.

## Local Codex clients

Use the bundled `scripts/wiki_connection.py` with Python 3.11 or newer. The native `codex` CLI must be installed for sign-in. Resolve the script relative to this skill's directory, not the current working directory.

1. Run `python3 <skill-directory>/scripts/wiki_connection.py status`. Preserve existing connections, credentials, and unrelated settings. If a connection already matches the requested server, use it.
2. Run `python3 <skill-directory>/scripts/wiki_connection.py connect <domain-or-HTTPS-endpoint>`. This checks the endpoint, adds the dedicated `agent_wiki` connection, and starts native OAuth for `wiki:read,wiki:write`. The user completes their wiki's browser sign-in and agent selection. Do not ask for a password in chat or copy credentials into files.
3. If sign-in was interrupted, retry `login`; the completed configuration is retained. If the name already belongs to another connection, preserve it and use `--name <new_name>` for a separate connection. A domain change must not reuse an existing connection's credentials.
4. Restart the native client or start a fresh session as required by that client. A successful setup command does not prove tools are available in the current chat.
5. Discover the connected server's tools and confirm article search/read/history/preview/save are available. Use a read-only article search to verify the connection. Report missing writes, authentication, or network access accurately; do not broaden scopes to make a check pass.

The helper prints JSON with the configuration and next step. Native sign-in messages go to stderr. `--no-login` only configures; it must not be described as authenticated. `--skip-probe` deliberately leaves endpoint connectivity unverified. `status` reports configuration, not authentication. Run `--help` for custom names, isolated client homes, and explicit loopback HTTP testing. Use `disconnect` to log out and remove only this helper's managed connection.

The configured allowlist is `wiki.search`, `wiki.read`, `wiki.history`, `wiki.preview`, and `wiki.save`. Other wiki connections are separate; do not remove or weaken them. Never add trace tools, trace scope, collectors, or activity hooks.

If the machine's configuration is managed by an organization or deployment system, follow that system's supported configuration path instead of bypassing it. The helper refuses conflicting or unfamiliar configuration.

## ChatGPT web

Web chats do not read local Codex configuration. Use the user's ChatGPT personal MCP connection flow: developer mode where available, Plugins → plus, the full HTTPS MCP endpoint, then native authentication. Open the relevant interface with available browser tools when authorized. Preserve required user sign-in and consent steps. See [ChatGPT connection instructions](https://developers.openai.com/plugins/deploy/connect-chatgpt).

The local helper cannot install a hosted connection, and a repository installation does not establish web or mobile availability. Do not claim that local configuration synced to those environments. An administrator must restrict the selected wiki identity to article read/write and the five article tools; inspect discovery before using the connection.

## Start using memory

When the user has asked to use the wiki as ongoing memory, use the companion `maintain-wiki` skill during useful work. Otherwise demonstrate a relevant search and explain that durable article updates are available. Do not create a test article without a user request or an explicitly designated disposable wiki.
