# Verification and maturity

Version `0.1.0-alpha.1` is a source alpha. No package-registry release or public-directory approval is implied.

## Verified September 30, 2026

- **macOS 27.0:** Python 3.14.7 and Codex 0.153.4 passed the 19 portable checks, real native configuration parsing, repository-marketplace installation/removal, and the synthetic engine integration.
- **Linux (Omarchy/Arch):** Python 3.14.7, Codex 0.157.1, and Node 26.8.1 passed the same 19 portable checks and synthetic engine integration.
- **Agent Wiki v0.8.17**, commit `c99235e173baf2897b47a0412577d74fe442526f`: discovery returned exactly the five article tools. Search/read/preview/save/history, same-operation retries, stale-revision rejection, preservation of unknown frontmatter, and fresh reads passed. A trace operation was denied even though the synthetic agent definition included it, because OAuth had only article scopes.
- **Native OAuth:** the real native client completed registration, PKCE, token exchange, and logout against a disposable server. The test asserted the requested scopes were exactly `wiki:read wiki:write`. Owner approval was automated inside the synthetic fixture; this does not test a production identity provider or a human browser sign-in.
- **Independent OSS/security review:** reviewed source, packaging, configuration preservation, and data boundaries. The two reported input-handling defects were corrected and covered by regression checks.

Tests use disposable configuration homes, accounts, and content. They do not change a normal client profile or connect to a real private wiki. Native-client acceptance is skipped when `codex` is absent; that skip is not authentication evidence.

The published README prompt in a fresh model session, clean public-repository installation, and automatic CI enrollment are still being checked. The quickstart is not yet claimed as verified. Desktop UI installation, ChatGPT web/mobile installation, arbitrary-domain public-directory onboarding, Windows, and production identity-provider sign-in are unverified.

## Reproduce

From a clean clone, run the dependency-free portable suite:

```sh
python3 scripts/check.py
```

With the native `codex` command installed, this also checks native configuration acceptance. Python 3.11+ is the declared runtime baseline; the executions recorded above used Python 3.14.7.

For optional real-server integration, separately check out the pinned engine and install its locked dependencies (Node 24.19+):

```sh
git clone https://github.com/dispatchlabs-ai/agent-wiki.git /tmp/agent-wiki-engine
git -C /tmp/agent-wiki-engine checkout c99235e173baf2897b47a0412577d74fe442526f
npm --prefix /tmp/agent-wiki-engine ci
AGENT_WIKI_ENGINE=/tmp/agent-wiki-engine node --test tests/integration.mjs
```

The engine is a test dependency, not a plugin runtime dependency. The integration uses loopback HTTP only inside its disposable fixture. It requires the native `codex` CLI but no real wiki account.
