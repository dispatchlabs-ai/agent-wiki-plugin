# Install and connect a wiki

Use this guide when a user asks you to install the plugin and connect their own Agent Wiki. The first acceptance result is an article search through the user's selected server, followed by durable article maintenance when they have authorized it.

## Requirements

- A local Codex environment on macOS or Linux, with Python 3.11+ and the native `codex` command.
- A reachable HTTPS Agent Wiki MCP endpoint. A bare domain such as `wiki.example.com` means `https://wiki.example.com/mcp`. A supplied non-root URL is treated as the complete MCP endpoint.
- An account on that wiki and permission to invoke an agent with an editor grant and the five article tools: `wiki.search`, `wiki.read`, `wiki.history`, `wiki.preview`, `wiki.save`. Article writes must be enabled by the operator. See the engine's [remote agent guide](https://github.com/dispatchlabs-ai/agent-wiki/blob/main/docs/remote-agents.md).
- Browser sign-in by the user. Keep credentials in the native client; never ask for passwords or tokens in conversation.

Do not deploy a wiki or change an unrelated server to satisfy these prerequisites. If configuration is managed centrally, use that system's approved installation path.

## Install the repository plugin

```sh
codex plugin marketplace add dispatchlabs-ai/agent-wiki-plugin
codex plugin add agent-wiki@agent-wiki-plugins
```

For a source checkout or a pinned tag:

```sh
git clone https://github.com/dispatchlabs-ai/agent-wiki-plugin.git
cd agent-wiki-plugin
# Optional: pin the published source alpha before adding the local marketplace.
git checkout v0.1.0-alpha.1
codex plugin marketplace add .
codex plugin add agent-wiki@agent-wiki-plugins
```

The marketplace is named `agent-wiki-plugins`; the plugin is `agent-wiki`. If your client offers installation only through the desktop UI, select this marketplace in Plugins and install Agent Wiki there. Restart or start a fresh session after installation. Do not assume a successful install retroactively loaded skills into the current chat.

## Configure the user's domain

Use the installed `connect-wiki` skill. From a source checkout, the same helper can be run directly:

```sh
python3 plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py connect wiki.example.com
```

The helper sends an unauthenticated MCP initialization probe, writes an article-only `agent_wiki` connection into the native client configuration, then runs native OAuth sign-in. The user signs in as themselves and selects an agent they may invoke. A missing sign-in leaves configuration intact; run `login` to continue.

```sh
python3 plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py status
python3 plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py login
```

The native configuration home defaults to `CODEX_HOME` or `~/.codex`. `--codex-home /path/to/client-home` explicitly selects another native client home. The helper writes only its marked connection section. It preserves unrelated TOML, refuses an existing unmanaged connection of the same name, and refuses symlinked configuration owned by another system. It never reads the native credential store.

Useful alternatives:

```sh
# Inspect the plan without changing files, contacting the server, or signing in.
python3 plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py connect wiki.example.com --dry-run

# Configure now and sign in later. This is not an authenticated connection yet.
python3 plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py connect wiki.example.com --no-login

# Add a second wiki without replacing the first server's identity or credentials.
python3 plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py connect team.example.com --name team_wiki
```

`--skip-probe` leaves connectivity unverified and is intended for deliberate recovery when the native client can connect but the limited initialization probe cannot. The probe does not follow redirects, copy cookies, or send an authorization header. `--allow-local-http` permits loopback-only synthetic testing; it does not enable plaintext remote connections.

## Verify the real result

In a fresh native client session:

1. Discover tools for the configured connection and confirm the five article operations are present. Inspect the server identity if multiple wikis are connected.
2. Search for a topic relevant to the user's work and read a matching article. Report a real article link or an honest empty result.
3. Confirm that the connection does not expose trace tools. Do not request trace scope to repair a read/write problem. The server must also enforce article-only scope.
4. When the user has authorized ongoing wiki memory, use `maintain-wiki` during normal work. To test writes, use a separately designated disposable wiki or a user-requested useful article change; never create junk pages in a real wiki just to test installation.

Configuration, native sign-in, tool discovery, and a successful article operation are separate checkpoints. Report which completed. A local successful connection does not establish ChatGPT web/mobile availability.

## Update and disconnect

Refresh the tracked repository marketplace with `codex plugin marketplace upgrade agent-wiki-plugins`, then use your client's plugin update/reinstall flow and start a new session. The native connection settings are outside the plugin package and survive updates. Check release notes before upgrading.

To sign out and remove the helper's connection:

```sh
python3 plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py disconnect
codex plugin remove agent-wiki@agent-wiki-plugins
```

Native logout must succeed before configuration removal. Revoking a connection in the wiki's own account UI is available independently. Removing the plugin alone does not revoke the separately configured native MCP connection.

## Failures and recovery

Helper stdout is one JSON result. Native sign-in diagnostics go to stderr. Exit 0 means the requested setup operation completed; it does not imply a live article check. Exit 1 reports a structured `code`; invalid CLI usage exits 2.

| Code | What to do |
| --- | --- |
| `INVALID_URL`, `HTTPS_REQUIRED` | Supply a valid HTTPS domain or endpoint without embedded credentials. |
| `NETWORK_ERROR`, `ENDPOINT_REJECTED` | Verify DNS, certificate trust, network reachability, the MCP path, and authorization discovery. |
| `REDIRECT_REFUSED` | Use the canonical endpoint URL. |
| `NOT_MCP`, `UNVERIFIED_ENDPOINT` | Verify this is an MCP endpoint; an ordinary website or uninspected response is insufficient. |
| `CONFIG_CONFLICT`, `MANAGED_CONFIG` | Preserve the existing configuration; choose a different connection name or use the owning configuration system. |
| `SERVER_CHANGE` | Use another name, or disconnect the old endpoint before reusing its name. |
| `CONFIG_BUSY`, `CONFIG_CHANGED` | Retry once the concurrent configuration change finishes. |
| `CODEX_MISSING`, `AUTH_INCOMPLETE` | Install/fix the native client or complete sign-in, then retry `login`. |

The helper configures one native connection; it does not bypass enterprise policy, install a server, or repair the server's account grants.
