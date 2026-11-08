# Article writes

Agent Wiki owns authorization, storage, and retry behavior. Discover the current schema instead of assuming the example below matches every server release. The first alpha targets the Agent Wiki v0.8.17 article interface.

## Targeted edits

When the server offers `wiki.edit`, use it to change part of an existing article. Send only the change; the article's other text and metadata are preserved:

```json
{
  "operation_id": "a-new-unique-identifier",
  "id": "article-id",
  "summary": "Correct the rollback owner.",
  "edits": [{ "old_text": "exact current text", "new_text": "replacement text" }]
}
```

`old_text` must match exactly once, so include enough surrounding text to make it unique, or set `replace_all`. Use `{ "section": "anchor", "new_text": "..." }` with `expected_revision_id` to replace a section and its subsections, including the heading, or `{ "append": "...", "section": "anchor" }` to add text. Get anchors from `wiki.read` with `fields: ["sections"]`. A partial read of the relevant section is enough. If `old_text` is not found, read the current text again rather than guessing.

When the server offers `wiki.delete`, use it to remove an article. Links to it in other articles are repaired in the same commit, as plain text or to `replace_with` when another article now covers the subject; report the repaired articles listed in the receipt. Git retains the history.

## Full saves

Use `wiki.save` for new articles, full rewrites, and servers without `wiki.edit`. For an existing article, obtain a complete `wiki.read` result immediately before editing. Preserve its current title, description, topic, related links, questions, body, and other fields unless the task calls for a change. Pass the returned `revision_id` as `expected_revision_id`. For a new article use `null`, after checking for existing coverage and an ID collision.

An ordinary save has this shape:

```json
{
  "operation_id": "a-new-unique-identifier",
  "updates": [{
    "id": "deployment-recovery",
    "expected_revision_id": "revision-from-the-complete-read",
    "title": "Deployment recovery",
    "description": "Verified recovery steps and their limits.",
    "topic": "Operations",
    "summary": "Document the verified rollback procedure.",
    "body": "The complete revised article goes here."
  }]
}
```

Use the edit's `summary` to describe the knowledge change, not to archive the session. Include optional metadata when preserving or deliberately changing it. Omit the optional `evidence` field: existing evidence is preserved, and this article-only client cannot verify new quotations against private traces. Do not supply an empty evidence array merely because you did not inspect the archive; that would clear existing evidence. Link ordinary external sources in article prose when relevant.

- **Stale revision:** read the new current article, merge the intended contribution with the intervening changes, then submit the revised request under a new operation ID. Never overwrite the other editor's work.
- **Timeout or lost response:** retain the exact request and retry with the same operation ID and arguments. A changed request under an existing ID is a conflict. Do not create a second operation until the first outcome is resolved.
- **Permission failure:** report the missing article authorization. Do not request trace scope or switch identities to bypass the denial.
- **Commit versus publication:** `state`, `commit`, `remote`, and `publication` describe separate outcomes. A committed edit with a push/publication problem is not a rollback; report it accurately and follow the server's recovery guidance.
- **Large reads:** a resource link or partial read is not the full article. Request appropriate smaller ranges for research, but obtain the complete current article through an authorized article interface before replacing it. If the host cannot do that, stop that edit and explain the limitation rather than reconstructing missing content.

After success, reread the changed article or relevant section and confirm the intended result. Do not rewrite a published article just to make its wording match your earlier draft.
