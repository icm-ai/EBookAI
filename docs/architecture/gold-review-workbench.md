# Milestone 16 — Annotation Review Workbench & Gold Promotion

Milestone 16 turns the Milestone 15 review queue into an interactive,
source-grounded annotation workflow.

The workbench is deliberately stricter than editing a JSON file by hand. It
separates three different human actions:

1. **confirm** — acknowledge one element or one task as checked;
2. **promote** — create a reviewed gold artifact after preflight passes;
3. **publish** — explicitly replace canonical corpus gold after an optimistic
   concurrency check.

A confirmation never silently changes canonical gold, and a promotion never
silently publishes it.

## UI

The frontend now has a **Gold Review** tab beside the existing Human Review
workspace.

The workbench has three columns:

- **review queue** — the 25 Milestone 15 target pages and their current
  unannotated/draft/reviewed status;
- **source canvas** — a rendered image of the exact SHA-256-pinned PDF page,
  parser bounding boxes, optional gold bounding boxes, and current evaluator
  evidence;
- **annotation editor** — task completeness, element editing/confirmation,
  reading order, promotion preflight, reviewed-artifact export, audit export,
  and explicit canonical publish.

Clicking a parser bounding box seeds the new-element editor with its text and
bbox. This is a convenience only; it does not confirm the parser output as
truth.

## Source and parser binding

Opening a target performs the following sequence:

1. look up the target in `benchmark/corpus/review-plan.json`;
2. verify/materialize the exact corpus PDF through `CorpusStore`;
3. verify the SHA-256 from `benchmark/corpus/manifest.json`;
4. run the selected parser adapter (PyMuPDF by default);
5. clone existing canonical gold into an isolated staged draft, or create a new
   empty staged page for an unannotated target;
6. render only the requested PDF page for human inspection.

Optional MinerU and Marker overlays use the same parser registry as the parser
benchmark. If an optional backend is unavailable the API returns an explicit
error rather than silently substituting another parser.

## Review decisions

Every confirmation records:

- subject type: `element` or `task`;
- subject id;
- reviewer identity;
- UTC timestamp;
- optional note.

Editing an element invalidates that element's confirmation.

Changing reading order invalidates the `reading_order` task confirmation.

Removing a task removes stale confirmation state for that task.

The staged annotation always remains `draft` until promotion.

## Task completeness

A task confirmation means the reviewer has checked the complete intended scope
for that page, not merely that one example exists.

This distinction matters especially for:

- `text`, where the annotated text should cover the evaluated page scope;
- `reading_order`, where all staged element ids must be represented before
  promotion;
- structural tasks, where both missing and spurious structures affect
  precision/recall.

The workbench preflight requires every enabled task and every staged element on
the active review page to be explicitly confirmed.

## Multi-page safety

Gold annotation status is document-level, while the workbench is page-focused.

To avoid accidentally authenticating unrelated draft work, promotion is
blocked when the canonical annotation contains **other draft pages** that have
not already been reviewed.

The intended incremental workflow is:

1. review/promote/publish the current draft page;
2. canonical annotation becomes reviewed;
3. open another queue page for that document;
4. the previously reviewed pages remain trusted history while the newly added
   page is staged as draft;
5. review/promote/publish again.

This supports gradual corpus expansion without a single-page action implicitly
promoting other unfinished pages.

## Promotion preflight

Promotion is allowed only when:

- the source annotation still matches the corpus document id and SHA-256;
- the staged annotation is still `draft`;
- there are no other blocking draft pages;
- all staged elements on the active page are confirmed;
- all enabled tasks on the active page are confirmed;
- reading order covers every staged element when the task is enabled;
- the promotion reviewer is non-empty;
- the promotion reviewer personally made at least one confirmation.

Promotion creates:

- `promoted-gold.json`;
- `promotion-audit.json`.

It does **not** mutate canonical gold.

## Promotion audit

The audit sidecar preserves review process information without changing the
Milestone 14 gold schema.

It records:

- workbench session id;
- document id and page index;
- parser backend;
- exact source SHA-256;
- canonical annotation hash observed when the session opened;
- staged annotation hash;
- promoted annotation hash;
- reviewer identity;
- promotion timestamp;
- publish timestamp, when present;
- every element/task confirmation;
- deterministic evaluator metrics and matching evidence captured at promotion.

The reviewed gold JSON therefore remains a clean evaluator input, while the
audit sidecar provides provenance for maintainers and reviewers.

## Explicit publish

Publish is a separate maintainer operation.

Before replacing the manifest-linked canonical gold file, the store reloads
the current canonical annotation and compares it with the hash observed when
the review session opened.

If another reviewer or process changed canonical gold in the meantime, publish
fails instead of overwriting it.

Canonical replacement itself is an atomic file replacement.

If the source checkout is read-only, publish also fails explicitly. In that
case the reviewer should download:

- the reviewed gold JSON;
- the promotion audit JSON;

and commit them from a writable maintainer checkout.

This behavior is intentional for production/container deployments.

## Docker behavior

The runtime image now contains the `benchmark/` assets so the Gold Review tab
can inspect the queue and materialize corpus sources.

The API initializes the workbench lazily. Missing benchmark assets therefore do
not prevent normal EBookAI conversion/review services from starting.

The standard Docker image should generally be treated as an inspection/export
environment rather than the authoritative place to mutate repository gold.
Canonical publish is primarily a local-maintainer workflow unless
`benchmark/` is mounted from a writable checkout.

## API

The workbench is exposed under `/api/gold-review`.

Key endpoints:

```text
GET    /queue
POST   /sessions
GET    /sessions/{id}
GET    /sessions/{id}/page.png
PUT    /sessions/{id}/tasks
PUT    /sessions/{id}/elements/{element_id}
DELETE /sessions/{id}/elements/{element_id}
PUT    /sessions/{id}/reading-order
POST   /sessions/{id}/confirm
POST   /sessions/{id}/promote
POST   /sessions/{id}/publish
GET    /sessions/{id}/export/promoted
GET    /sessions/{id}/export/audit
```

The API never accepts an arbitrary source path. A review session can only be
created for a document/page pair already present in the source-pinned review
plan.

## Storage

Review sessions are persisted under the configured EBookAI output directory:

```text
outputs/
  gold-review-cache/
  gold-review-workspace/
    <session-id>/
      gold-review-session.json
      promoted-gold.json
      promotion-audit.json
```

The source PDF cache remains SHA-256 pinned through `CorpusStore`.

## Relationship to the parser leaderboard

Milestone 16 does not relax Milestone 15 leaderboard eligibility.

A staged draft and even an un-published promoted artifact do not alter the
benchmark corpus. Only canonical gold whose status is `reviewed` is consumed
by the default reviewed-only leaderboard.

This means the lifecycle is explicit:

```text
review queue
  -> staged draft
  -> confirmations / edits
  -> promotion preflight
  -> reviewed artifact + audit
  -> explicit canonical publish
  -> reviewed-only parser leaderboard
  -> saved regression baseline
```

## Current practical next action

The repository currently has two real draft seeds:

- NIST EEL page index 8;
- NIST AI RMF page index 3.

They are the first candidates to run through the new workbench and receive
independent human review. After canonical publication, the reviewed-only
leaderboard can produce its first eligible parser entry and the project can
save its first reviewed baseline snapshot.
