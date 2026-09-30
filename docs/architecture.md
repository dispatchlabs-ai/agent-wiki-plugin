# Architecture and platform boundaries

The repository is a Git-backed plugin marketplace containing one portable Agent Plugins package. It has two skills: `connect-wiki` for setup and `maintain-wiki` for article work. Its setup helper uses the Python standard library and delegates credential handling to the native Codex client.

```text
Repository plugin → setup and editorial skills
User domain       → native article-only MCP connection → user's Agent Wiki
Native OAuth      → user's wiki authorization service
```

The package intentionally contains no fixed `mcp.json` endpoint. A user-specific connection is a native `[mcp_servers.agent_wiki]` table, with an explicit article tool allowlist and read/write scopes. It is stored outside the installed plugin. Native tools remain independently configured after plugin removal until explicitly disconnected. This is a skills plugin with a setup helper, not a hidden proxy MCP server.

The helper never calls article save or searches a chat archive. Its network probe contains only MCP protocol and client metadata. Once connected, the model calls the wiki's existing public tools; server-side authorization, optimistic revisions, idempotency, and publication remain engine responsibilities. Client tool filtering is additional discovery control, not a substitute for server authorization.

## Platform support

The initial target is local Codex on macOS/Linux with a native MCP configuration. Desktop clients sharing that native host configuration can use it, subject to their plugin support and policy. Python 3.11+ is required for standard-library TOML parsing. No npm package, server adapter, or publisher account is required on the client.

ChatGPT web does not read local Codex configuration. Its documented personal-plugin path is developer mode → Plugins → plus → full MCP URL → native authentication. Account/workspace policies may restrict that path. The repository's local installer does not perform it or establish portable web/mobile installation. A workspace can package a connection using its own registered MCP integration and the same skills; that is a separately verified deployment.

Public-directory templates are a separate distribution mechanism. OpenAI documents approval-limited workspace endpoint templates; support for arbitrary user-owned domains and individual self-service remains unverified. This alpha does not depend on that mechanism.

## Compatibility contract

The plugin targets the article operations in Agent Wiki v0.8.17. The native client must support HTTP MCP, OAuth, configured scopes, and `enabled_tools`. The skills discover current tool schemas. They do not assume a provider-specific tool namespace or direct filesystem access to wiki content.

The helper preserves unrelated TOML and refuses an existing connection it does not own. Its managed section is intentionally conservative: unfamiliar settings require review. It writes atomically and checks for intervening edits; its advisory lock serializes this helper's own writers. Other client writers do not share that lock, so avoid running setup during simultaneous configuration changes.

## Upstream references

Checked September 30, 2026:

- [Plugin packages and repository marketplaces](https://developers.openai.com/plugins/build/plugins)
- [Native MCP configuration](https://learn.chatgpt.com/docs/extend/mcp)
- [ChatGPT personal connection flow](https://developers.openai.com/plugins/deploy/connect-chatgpt)
- [Public template endpoint limits](https://developers.openai.com/plugins/deploy/app-review#template-mcp-server-urls)
- [Agent Wiki interface and permission contract](https://github.com/dispatchlabs-ai/agent-wiki/blob/v0.8.17/docs/interfaces.md)
