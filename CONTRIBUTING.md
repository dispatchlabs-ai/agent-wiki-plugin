# Contributing

Agent Wiki Plugin is maintained by Chris Reynolds. Contributions are welcome under the MIT license, without a CLA or copyright assignment.

Use Python 3.11+ on macOS or Linux. Clone the repository and run `python3 scripts/check.py`; there are no Python package dependencies. The optional native configuration acceptance test also needs the `codex` CLI. Keep credentials, private installation details, and real conversation data out of fixtures and issues.

Keep the plugin independently installable from its repository. The native client owns credentials, Agent Wiki owns article operations and authorization, and the skills own setup/editorial guidance. Preserve the no-transcript/no-trace boundary, existing user configuration, revision checks, and uncertain-retry behavior. Do not add a content relay or silently widen scopes.

Document observable changes and update `CHANGELOG.md`. Run the portable checks and relevant synthetic integration checks before submitting a pull request. Avoid changes to unrelated files. The maintainer integrates onto `main`; release versions, marketplace metadata, and the helper version must agree.

Report ordinary bugs through GitHub issues with a minimal synthetic reproduction and redacted diagnostics. Follow `SECURITY.md` for sensitive reports. Automatic CI is run on maintainer-owned infrastructure; this repository does not use GitHub Actions.
