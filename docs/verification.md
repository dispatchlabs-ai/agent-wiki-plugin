# Verification and maturity

Version `0.1.0-alpha.1` is a source alpha. No package-registry release or public-directory approval is implied.

## Verified September 30, 2026

- **macOS 27.0:** Python 3.14.7 and Codex 0.153.4 passed the 21 portable checks, real native configuration parsing, repository-marketplace installation/removal, and the synthetic engine integration.
- **Linux (Omarchy/Arch):** Python 3.14.7, Codex 0.157.1, and Node 26.8.1 passed the same 21 portable checks and synthetic engine integration.
- **Agent Wiki v0.8.17**, commit `c99235e173baf2897b47a0412577d74fe442526f`: discovery returned exactly the five article tools. Search/read/preview/save/history, same-operation retries, stale-revision rejection, preservation of unknown frontmatter, and fresh reads passed. A trace operation was denied even though the synthetic agent definition included it, because OAuth had only article scopes.
- **Native OAuth:** the real native client completed registration, PKCE, token exchange, and logout against a disposable server. The test asserted the requested scopes were exactly `wiki:read wiki:write`. Owner approval was automated inside the synthetic fixture; this does not test a production identity provider or a human browser sign-in.
- **Independent OSS/security review:** reviewed source, packaging, configuration preservation, test isolation, and data boundaries. Reported defects were corrected and covered by regression checks; the final review reported no remaining actionable findings.

Tests use disposable configuration homes, accounts, and content. They do not change a normal client profile or connect to a real private wiki. Native-client acceptance is skipped when `codex` is absent; that skip is not authentication evidence.

**Clean public clones** passed the portable checks and real-server integration on macOS and Linux. Automatic CI is enrolled on maintainer-owned Linux infrastructure and publishes the repository check result on the exact commit; it skips the native-client acceptance case when the client is absent from the build sandbox. Native OAuth and model tests are separately recorded above/below.

**Fresh-agent quickstart on macOS and Linux:** a new native session followed the exact README prompt with the example domain replaced by a disposable loopback endpoint, installed from the public marketplace, and completed authenticated article search/read. A second fresh session saved a synthetic maintenance fact; a third retrieved it from the article. The fixture supplied already-completed native sign-in and explicitly authorized loopback HTTP. No human interaction was needed inside this fixture; real deployments still need account access and browser sign-in. The initial run exposed native TOML comment relocation; the helper was fixed and the complete three-session workflow passed again without manual configuration repair. Linux completed the same three-session workflow. Its first attempt stopped because the configured model was unavailable to the native account; rerunning with an available model in the isolated profile passed, without changing workstation settings.

Desktop UI installation, ChatGPT web/mobile installation, arbitrary-domain public-directory onboarding, Windows, and production identity-provider sign-in are unverified. Model-led outcomes depend on the native account's available model and client policies.

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
