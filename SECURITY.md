# Security

This is an early source alpha. Only the latest alpha is maintained; production suitability has not been established.

Report vulnerabilities privately using this repository's GitHub **Security → Report a vulnerability** feature. If that feature is unavailable, open an issue requesting a private contact without including exploit details, credentials, or private wiki data.

Include affected versions, a synthetic reproduction, and the security impact. No response-time guarantee or bounty program is offered.

The native MCP client owns OAuth credentials. The helper must not read credential stores, follow endpoint redirects, modify unrelated configuration, reuse one connection name for another server without disconnecting, or add trace tools/scopes. TLS validation stays enabled. The server remains responsible for authorization and article permissions. See `docs/privacy.md` for data handling.
