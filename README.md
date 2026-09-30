# Agent Wiki Plugin

Your agents maintain a wiki you own. Useful knowledge survives; conversations stay out of the wiki.

Connect your self-hosted [Agent Wiki](https://github.com/dispatchlabs-ai/agent-wiki), then let your agent consult and improve its articles during ordinary work. The plugin provides setup and editorial skills. Your native MCP client connects directly to your wiki; there is no publisher-operated content relay.

**Source alpha · MIT · Python 3.11+ · local Codex clients on macOS and Linux.** You need a reachable Agent Wiki server with article writes enabled, a wiki account, and permission to invoke an agent with article read/write access. The plugin does not deploy a server. See [compatibility and verification](docs/verification.md) for what has actually been tested.

## Use it with your AI agent

Give an agent with shell access, web access, and your native Codex client this prompt, replacing the example domain:

> Follow https://github.com/dispatchlabs-ai/agent-wiki-plugin/blob/main/docs/agent-guide.md to install Agent Wiki Plugin and connect my wiki at wiki.example.com. Preserve my other settings. Help me complete sign-in, verify a read-only article search, and use this wiki as durable memory during our work. Save useful article edits, never conversation transcripts or traces.

The first useful result is a relevant article search from your own wiki. Setup asks you to complete the wiki's native browser sign-in; it does not ask you to paste a password or token into chat. A new client session may be required before the tools become available.

## Install manually

Add this repository's marketplace and install its plugin:

```sh
codex plugin marketplace add dispatchlabs-ai/agent-wiki-plugin
codex plugin add agent-wiki@agent-wiki-plugins
```

Start a fresh session and ask: **“Connect my wiki at wiki.example.com.”** The setup skill accepts a domain, HTTPS origin, or full MCP endpoint. For clients without the CLI installer, install from the added marketplace in the desktop Plugins directory. See the [setup guide](docs/agent-guide.md) for source-checkout installation, authentication, and recovery.

## What gets saved

The agent can search, read, preview, and edit articles, preserving revision checks and retry identifiers. It saves selected facts, decisions, procedures, and verified lessons. It does not scan session directories, upload prompts or transcripts, install a trace collector, or add activity hooks. Article content and search terms still reach your chosen server; native OAuth and ordinary server access logs also exist. See [data boundaries](docs/privacy.md).

Plugin installation alone does not guarantee an update after every task. The prompt above establishes the ongoing-memory intent; you can also put that preference in your own standing agent instructions. A task with nothing useful to preserve should make no edit.

## Scope

This repository distributes skills and a local connection helper. It does not bundle one fixed MCP URL: the helper creates a dedicated native `agent_wiki` connection with only the five article tools and `wiki:read,wiki:write` scopes. The endpoint lives in user configuration, so plugin updates preserve it. Credentials stay with the native client.

ChatGPT web has a separate personal MCP connection flow; it does not read local Codex configuration. Web/mobile installation from this repository and arbitrary-domain public-directory onboarding are not claimed as verified. [Platform details](docs/architecture.md).

Created by **Chris Reynolds, cofounder of Dispatch Labs AI**. Contributions are welcome under MIT, without a CLA. [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) · [Changelog](CHANGELOG.md)
