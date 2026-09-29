# Milestone 17 — Multi-reviewer Consensus & Reviewed Baselines

Milestone 17 adds an independence boundary between human review and canonical
benchmark truth.

Milestone 16 can still create a promoted review candidate, but Milestone 17
allows two independently promoted candidates for the same page to be compared
before canonical publication.

## Trust model

A consensus pair is accepted only when both sessions:

- are distinct persisted review sessions;
- have been promoted;
- target the same document and page;
- are bound to the same source SHA-256;
- opened from the same canonical gold hash;
- have different `reviewed_by` identities;
- agree on every page outside the active review page.

This prevents a reviewer from comparing a candidate against itself, prevents
source drift, and prevents a consensus operation from silently reconciling
unrelated document changes.

## Semantic comparison

Consensus does not diff provenance strings such as notes or reviewer names.

The active page is normalized into three semantic dimensions:

- enabled `tasks`;
- ordered `reading_order`;
- elements keyed by stable `element_id`.

An element conflict covers its complete semantic payload: type, text, bbox,
heading level, and attrs. Added or removed elements are represented as a
conflict where one candidate is null.

Conflict ids are deterministic:

```text
tasks
reading_order
element:<stable-element-id>
```

If the two candidates have no semantic conflicts, consensus gold is generated
immediately.

## Adjudication

When conflicts exist, every conflict must be resolved explicitly.

The adjudicator chooses candidate A or B for each conflict. The adjudicator
identity must differ from both original reviewers.

The workbench does not silently merge conflicting text, bboxes, task scopes, or
reading order. It also does not use an LLM to decide which reviewer is correct.

Once all conflicts are resolved, the resulting page is re-parsed through the
normal `GoldPageAnnotation` schema. Invalid combinations therefore remain
blocked by existing gold invariants.

The final `reviewed_by` field records both reviewers and, when needed, the
adjudicator identities.

## Consensus artifacts

A consensus bundle is stored below the existing Gold Review workspace:

```text
outputs/gold-review-workspace/consensus/<bundle-id>/
  consensus-bundle.json
  consensus-gold.json
  consensus-audit.json
```

Milestone 18 additionally promotes the final published consensus audit into
`benchmark/corpus/provenance/` and updates a canonical provenance registry.
Workspace audits remain useful session evidence, while the corpus provenance
record is what the governance gate trusts.

The audit records:

- both source session ids;
- both reviewer identities;
- source SHA-256;
- canonical hash observed by both sessions;
- candidate annotation hashes;
- semantic conflicts;
- every adjudication choice;
- consensus annotation hash;
- publish timestamp.

## Canonical publish

Consensus publication is explicit.

Before replacing canonical gold, the store reloads the manifest-linked
annotation and verifies that its hash still equals the revision observed when
both independent sessions started.

A concurrent canonical change blocks publication.

The original Milestone 16 single-reviewer publish API remains available for
backward compatibility and local workflows. For benchmark-grade reviewed gold,
the Milestone 17 consensus path is the intended workflow.

## Workbench UI

The Gold Review tab now includes a **Two-reviewer consensus** panel.

A reviewer can copy/add two promoted session ids, compare them, inspect each
semantic conflict side-by-side, and hand conflicts to an independent
adjudicator.

When consensus is ready the UI exposes:

- consensus gold JSON;
- consensus audit JSON;
- explicit maintainer canonical publish.

## API

New endpoints under `/api/gold-review`:

```text
POST /consensus
GET  /consensus/{bundle_id}
POST /consensus/{bundle_id}/adjudicate
POST /consensus/{bundle_id}/publish
GET  /consensus/{bundle_id}/export/gold
GET  /consensus/{bundle_id}/export/audit
```

## Reviewed baseline snapshots

A parser baseline is now more than a copied leaderboard file.

`ReviewedBaselineSnapshot` freezes:

- corpus id;
- corpus manifest SHA-256;
- SHA-256 of every canonical reviewed gold file;
- complete reviewed-only leaderboard policy and entries;
- creation timestamp.

Baseline creation is rejected when:

- the leaderboard includes draft gold;
- no backend is eligible under the leaderboard policy;
- there is no canonical reviewed gold;
- the leaderboard and manifest corpus ids differ.

Create a snapshot after running the benchmark and reviewed-only leaderboard:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli baseline-create \
  artifacts/parser-benchmark/leaderboard/leaderboard.json \
  --manifest benchmark/corpus/manifest.json \
  --output benchmark/leaderboard/baselines/first-reviewed.json
```

## Why no real baseline is committed yet

The repository's existing real gold seeds are still draft annotations. They
must not be relabeled as reviewed by implementation code or by an AI-generated
migration.

Milestone 17 therefore ships the consensus machinery and baseline gate, but it
intentionally does **not** fabricate the first real reviewed baseline.

The first real snapshot should be created only after two humans independently
review a real target (starting with the existing NIST draft seeds), any
disagreement is independently adjudicated, and the consensus gold is
canonically published.

## Recommended first real baseline sequence

1. Reviewer A opens the same pinned NIST target and completes M16 review.
2. Reviewer B independently opens the target from the same canonical revision.
3. Both promote their sessions without publishing.
4. Create an M17 consensus bundle.
5. If conflicts exist, a third reviewer adjudicates them.
6. Publish consensus gold.
7. Run the parser benchmark against the now-reviewed canonical gold.
8. Build the reviewed-only leaderboard.
9. Run `baseline-create`.
10. Commit the canonical gold, consensus audit, and reviewed baseline snapshot.

This produces a baseline whose accuracy numbers can be traced back to exact
source bytes and explicit independent human decisions.
