# Data boundaries

The plugin has no publisher-operated service, collector, telemetry client, or scheduled job. It does not read conversation/session directories or install hooks. Setup creates a dedicated native connection exposing only article search, read, history, preview, and save, and requests `wiki:read` and `wiki:write`.

The setup probe sends the selected endpoint a JSON-RPC MCP initialization request containing protocol version and the helper's name/version. Authentication uses the native client's browser OAuth flow. That client stores its credentials; this helper does not read or duplicate them.

During use, the selected wiki receives intentional article queries and edits. Articles can include useful knowledge learned during a conversation. The editorial skill forbids uploading the surrounding transcript, raw prompts, hidden reasoning, tool execution archives, or credentials, including embedding them inside otherwise permitted article saves. No software wrapper can prove every model-authored sentence is appropriate; review the chosen agent's behavior and the server's permissions.

Existing wiki history and article content can already contain quotations or other published information. Article-only access does not redact existing articles. The plugin omits trace tools and does not request trace scope; server-side scope enforcement remains essential.

Server operators control their own logs, retention, accounts, and content publication. Configure those systems to avoid raw request-body logging if that is part of your privacy requirement. OpenAI/native client data handling remains governed by those products' settings and terms. This plugin does not change either provider's policies.

Other MCP connections and previously installed trace collectors are independent. This installer preserves them rather than silently changing an operator's deployment. Removing this plugin does not remove its native MCP connection; use the documented disconnect command to sign out and remove that connection.
