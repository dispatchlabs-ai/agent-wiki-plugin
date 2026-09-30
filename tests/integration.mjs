// Optional integration against a separately checked-out Agent Wiki engine.
// All accounts, tokens, content, native profiles, and requests are synthetic.
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL, fileURLToPath } from "node:url";
import { createServer } from "node:net";
import { once } from "node:events";
import { createHash } from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const engine = process.env.AGENT_WIKI_ENGINE;
const root = fileURLToPath(new URL("../", import.meta.url));
const helper = path.join(root, "plugins/agent-wiki/skills/connect-wiki/scripts/wiki_connection.py");
const allowed = ["wiki.search", "wiki.read", "wiki.history", "wiki.preview", "wiki.save"];

test("real Agent Wiki article workflow and native OAuth use no trace authority", { skip: !engine, timeout: 60000 }, async (t) => {
  const load = (name) => import(pathToFileURL(path.join(engine, "src", name)).href);
  const [{ ControlStore }, { AgentStore }, { RemoteAgents }, { createWiki }, { git, markdown }] = await Promise.all([
    load("control-store.mjs"), load("agent-store.mjs"), load("remote-agents.mjs"), load("server.mjs"), load("git-wiki.mjs"),
  ]);
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "wiki-plugin-integration-"));
  let app, listener, control;
  t.after(async () => {
    if (app) await new Promise((resolve) => { app.close(resolve); app.closeAllConnections(); });
    if (listener) await new Promise((resolve) => listener.close(resolve));
    control?.close();
    fs.rmSync(temporary, { recursive: true, force: true });
  });
  // git -C does not override inherited GIT_DIR/GIT_WORK_TREE. Keep every
  // engine Git call inside this fixture and prevent ambient hooks/templates.
  for (const key of Object.keys(process.env)) {
    if (key.startsWith("GIT_")) delete process.env[key];
  }
  const gitEmpty = path.join(temporary, "empty-git-config");
  fs.mkdirSync(gitEmpty);
  Object.assign(process.env, {
    GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL: "/dev/null",
    GIT_CONFIG_SYSTEM: "/dev/null", GIT_TEMPLATE_DIR: gitEmpty,
    GIT_CONFIG_COUNT: "1", GIT_CONFIG_KEY_0: "core.hooksPath", GIT_CONFIG_VALUE_0: gitEmpty,
  });
  const repo = path.join(temporary, "content");
  const home = path.join(temporary, "native-client");
  fs.mkdirSync(path.join(repo, "wiki"), { recursive: true });
  fs.mkdirSync(home, { mode: 0o700 });
  fs.writeFileSync(path.join(home, "config.toml"), 'mcp_oauth_credentials_store = "file"\n');
  git(repo, ["init", "-b", "main"]);
  git(repo, ["config", "user.name", "Synthetic editor"]);
  git(repo, ["config", "user.email", "editor@example.invalid"]);
  fs.writeFileSync(path.join(repo, "wiki/cedar.md"), markdown({ title: "Cedar recovery", description: "Synthetic deployment guide", topic: "Operations", custom: { keep: true } }, "Cedar runs on port 8080.\n"));
  git(repo, ["add", "."]);
  git(repo, ["commit", "-m", "Add synthetic guide"]);
  control = new ControlStore(path.join(temporary, "control.sqlite3"));
  const owner = control.bootstrap({ issuer: "https://identity.example.invalid", subject: "synthetic-owner", name: "Synthetic owner" });
  const agents = new AgentStore(control);
  // The definition deliberately includes a trace tool; narrowed OAuth scope must still hide it.
  const actor = agents.create(owner, { name: "Synthetic editor", definition: { instructions: "Maintain synthetic articles.", tools: [...allowed, "wiki.traceSearch"] } });
  control.grant(owner, actor.id, "editor");
  listener = createServer();
  listener.listen(0, "127.0.0.1");
  await once(listener, "listening");
  const origin = `http://127.0.0.1:${listener.address().port}`;
  app = createWiki({ repo, origin, control, write: true, development: true, traces: null, evidenceUrl: null, articleMediaRoot: null });
  app.listen(listener);
  await once(app, "listening");
  const remote = new RemoteAgents(agents, origin);
  const requests = [];
  app.on("request", (req) => { requests.push({ method: req.method, path: new URL(req.url, origin).pathname }); });

  const registration = remote.register({ client_name: "Synthetic integration", redirect_uris: ["http://127.0.0.1:8765/callback"], token_endpoint_auth_method: "none" });
  const verifier = "v".repeat(64);
  const authorization = new URLSearchParams({ client_id: registration.client_id, redirect_uri: registration.redirect_uris[0], response_type: "code", code_challenge_method: "S256", code_challenge: createHash("sha256").update(verifier).digest("base64url"), resource: origin + "/mcp", scope: "wiki:read wiki:write", state: "synthetic-state", agent: actor.id, decision: "allow" });
  const redirect = new URL(remote.approve(owner, authorization));
  const token = remote.exchange(new URLSearchParams({ client_id: registration.client_id, grant_type: "authorization_code", code: redirect.searchParams.get("code"), code_verifier: verifier, redirect_uri: registration.redirect_uris[0], resource: origin + "/mcp" }));
  assert.deepEqual(token.scope.split(" ").sort(), ["wiki:read", "wiki:write"]);
  let requestId = 0;
  async function rpc(method, params) {
    const response = await fetch(origin + "/mcp", { method: "POST", headers: { Authorization: `Bearer ${token.access_token}`, "Content-Type": "application/json", Accept: "application/json, text/event-stream" }, body: JSON.stringify({ jsonrpc: "2.0", id: ++requestId, method, params }) });
    assert.equal(response.status, 200);
    const body = await response.text();
    if (response.headers.get("Content-Type")?.includes("text/event-stream")) {
      return body.split("\n").filter((line) => line.startsWith("data:")).map((line) => JSON.parse(line.slice(5))).find((message) => message.id === requestId);
    }
    return JSON.parse(body);
  }
  await rpc("initialize", { protocolVersion: "2025-03-26", capabilities: {}, clientInfo: { name: "synthetic-plugin-check", version: "1" } });
  const discovery = await rpc("tools/list", {});
  assert.deepEqual(discovery.result.tools.map((tool) => tool.name).sort(), [...allowed].sort());
  const call = async (name, args) => {
    const response = await rpc("tools/call", { name, arguments: args });
    assert.equal(response.error, undefined, JSON.stringify(response.error));
    return { envelope: response.result, data: JSON.parse(response.result.content[0].text) };
  };
  const search = await call("wiki.search", { q: "Cedar" });
  assert.equal(search.data.articles[0].id, "cedar");
  const read = await call("wiki.read", { id: "cedar" });
  const body = read.data.body + "\nRestart the Cedar service after restoring its configuration. Verified in a synthetic recovery drill.\n";
  const preview = await call("wiki.preview", { body });
  assert.equal(preview.envelope.isError, undefined);
  const draft = { operation_id: "plugin-integration-save", updates: [{ id: "cedar", expected_revision_id: read.data.revision_id, title: read.data.title, description: read.data.description, topic: read.data.topic, body, summary: "Record the synthetic recovery step." }] };
  const saved = await call("wiki.save", draft);
  assert.equal(saved.envelope.isError, undefined, JSON.stringify(saved.data));
  const retried = await call("wiki.save", draft);
  assert.equal(retried.data.commit, saved.data.commit);
  const fresh = await call("wiki.read", { id: "cedar" });
  assert.match(fresh.data.body, /Restart the Cedar service/);
  assert.equal(fresh.data.number, read.data.number + 1);
  const history = await call("wiki.history", { id: "cedar" });
  assert.equal(history.envelope.isError, undefined);
  const stale = await call("wiki.save", { ...draft, operation_id: "plugin-integration-stale" });
  assert.equal(stale.envelope.isError, true);
  assert.equal((await call("wiki.read", { id: "cedar" })).data.revision_id, fresh.data.revision_id);
  const matter = createRequire(path.join(engine, "package.json"))("gray-matter");
  assert.equal(matter(fs.readFileSync(path.join(repo, "wiki/cedar.md"), "utf8")).data.custom.keep, true);
  // A negative authorization check is separate from the plugin's article workflow.
  const denied = await rpc("tools/call", { name: "wiki.traceSearch", arguments: { q: "synthetic" } });
  assert.ok(denied.error || denied.result?.isError);
  assert.ok(requests.every((request) => !request.path.startsWith("/api/traces") && !request.path.includes("ingest")));

  // Real native OAuth: automate approval only inside this disposable fixture.
  // Do not use browser automation or these fixture accounts against a real wiki.
  const noBrowser = path.join(temporary, "no-browser");
  fs.writeFileSync(noBrowser, "#!/bin/sh\nexit 0\n", { mode: 0o700 });
  const env = { ...process.env, CODEX_HOME: home, BROWSER: noBrowser };
  let nativeOutput = "";
  let nativeAuthorized = false;
  let approvalTask;
  const child = spawn("python3", [helper, "connect", origin, "--allow-local-http", "--codex-home", home], { env, cwd: home, stdio: ["ignore", "pipe", "pipe"] });
  t.after(() => child.kill());
  const inspect = (bytes) => {
    nativeOutput += bytes.toString();
    if (nativeAuthorized) return;
    const match = nativeOutput.match(/(http:\/\/127\.0\.0\.1:\d+\/oauth\/authorize\?[^\s]+)\s/);
    if (!match) return;
    nativeAuthorized = true;
    approvalTask = (async () => {
      const url = new URL(match[1]);
      assert.deepEqual(url.searchParams.get("scope").split(" ").sort(), ["wiki:read", "wiki:write"]);
      const params = new URLSearchParams(url.search);
      params.set("agent", actor.id);
      params.set("decision", "allow");
      const callback = remote.approve(owner, params);
      assert.equal((await fetch(callback)).status, 200);
    })();
  };
  child.stdout.on("data", inspect);
  child.stderr.on("data", inspect);
  const timer = setTimeout(() => child.kill("SIGTERM"), 30000);
  const [exitCode] = await once(child, "close");
  clearTimeout(timer);
  await approvalTask;
  assert.ok(nativeAuthorized, "Native OAuth did not present an authorization URL.");
  assert.equal(exitCode, 0, "Native setup/authentication failed; inspect the isolated fixture, not real credentials.");
  assert.match(nativeOutput, /native_login_completed/);
  const disconnect = spawnSync("python3", [helper, "disconnect", "--codex-home", home], { env, cwd: home, encoding: "utf8" });
  assert.equal(disconnect.status, 0, disconnect.stdout);
  assert.equal(JSON.parse(disconnect.stdout).state, "disconnected");
  assert.equal(fs.readFileSync(path.join(home, "config.toml"), "utf8").trim(), 'mcp_oauth_credentials_store = "file"');
  t.diagnostic("Verified five article tools, read/preview/save/history, same-operation retry, stale-revision rejection, fresh read, trace denial, native scoped OAuth, and disconnect.");
});
