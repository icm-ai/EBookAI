# Milestone 19 — Benchmark Change Control & Reviewer Operations

Milestone 19 adds operational control around the benchmark truth created by
Milestones 14–18.

The focus is not a new metric. It is the maintenance workflow around:

- assigning independent human reviewers;
- tracking review batches;
- proposing reviewed baseline versions;
- reviewing gold/baseline/policy changes in pull requests;
- requiring independent approvals;
- publishing a PR-friendly semantic change report.

## Reviewer operations

Review batches are stored under:

```text
benchmark/review-batches/
```

A batch contains explicit page assignments:

```text
document_id
page_index
reviewer_a
reviewer_b
adjudicator (optional)
```

Reviewer A and reviewer B must be different identities. If an adjudicator is
assigned, that identity must differ from both reviewers.

Every assignment must correspond to a target in
`benchmark/corpus/review-plan.json`. A batch cannot silently introduce a page
outside the maintained review plan.

Create a batch:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli review-batch-create \
  --id nist-high-priority-01 \
  --created-by <maintainer> \
  --reviewer-a <reviewer-a> \
  --reviewer-b <reviewer-b> \
  --adjudicator <adjudicator> \
  --priorities high \
  --limit 5
```

The default output is:

```text
benchmark/review-batches/<batch-id>.json
```

Batch progress is derived from the canonical Milestone 18 provenance registry,
not from a manually toggled status field:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli review-batch-report \
  benchmark/review-batches/nist-high-priority-01.json \
  --output artifacts/nist-high-priority-01.md
```

A page becomes `reviewed` in the batch report only when canonical consensus
provenance exists for that document/page.

## Baseline proposal versus activation

Milestone 18 baseline versions are immutable.

Milestone 19 treats registration without activation as a proposal:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli baseline-register \
  benchmark/leaderboard/baselines/2026-10-candidate.json \
  --id 2026-10-candidate \
  --no-activate
```

This records a candidate version without changing the active regression
baseline.

Activation is a later change to the baseline registry. That registry change is
governed by pull-request change control and independent review.

This separation makes the two decisions explicit:

1. is this snapshot a valid candidate?
2. should this candidate become the active regression baseline?

## Governed benchmark paths

The change-control engine tracks benchmark truth and the code that defines its
trust semantics.

Governed asset categories include:

- corpus manifest;
- review plan;
- canonical gold;
- consensus provenance registry and audits;
- reviewed baseline snapshots and registry;
- governance policy;
- change-control policy;
- review batches.

The governance-engine category additionally includes:

- benchmark change-control workflow;
- main CI workflow;
- baseline implementation;
- consensus implementation;
- provenance implementation;
- governance implementation;
- change-control implementation.

Changes to governance policy, change-control policy, or governance-engine code
require two independent PR approvals by default.

## PR semantic diff

Generate the same report locally:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli change-control-report \
  --base-ref <base-sha> \
  --head-ref <head-sha> \
  --policy benchmark/governance/change-control.json \
  --output artifacts/benchmark-change-control
```

The report contains:

- changed governed path;
- category;
- added/modified/deleted status;
- exact before/after SHA-256;
- required approval count;
- semantic summary.

Examples of semantic summaries:

- gold: draft/reviewed status, page set, reviewed_by;
- baseline registry: active baseline before/after and version count;
- governance policy: changed keys;
- review plan: target count before/after;
- review batch: assignment count before/after;
- corpus manifest: document count before/after.

This is intentionally more useful in a PR than a raw JSON diff.

## Co-change invariants

Change control fails closed on incomplete benchmark changes.

### Reviewed gold

A change that creates or modifies `reviewed` gold must include:

- `benchmark/corpus/provenance/registry.json`;
- a canonical consensus audit for the affected document.

Draft-to-draft annotation edits do not require consensus provenance.

### Reviewed baseline snapshots

Adding or modifying a reviewed baseline snapshot requires a baseline registry
change.

When the registry changes, every registered snapshot path and SHA-256 is
validated against the PR head revision.

An active baseline id must refer to a registered version.

## Approval policy

The repository policy is:

```text
benchmark/governance/change-control.json
```

Default independent approval requirements:

| Category | Approvals |
|---|---:|
| corpus manifest | 1 |
| review plan | 1 |
| gold | 1 |
| provenance | 1 |
| baseline snapshot/registry | 1 |
| review batch | 1 |
| governance policy | 2 |
| change-control policy | 2 |
| governance engine | 2 |

The requirement for a PR is the maximum requirement among its governed changes.

The PR author does not count as an independent approver.

If a reviewer first approves and later requests changes, only that reviewer's
latest review state counts.

## Base-policy rule

Approval requirements are resolved from the **PR base revision**, not the PR
head.

This prevents a PR from weakening its own approval policy and then benefiting
from the weaker rule in the same change.

The workflow falls back to the head policy only for the one-time bootstrap case
where the base branch predates Milestone 19.

## GitHub workflow

The dedicated workflow is:

```text
.github/workflows/benchmark-change-control.yml
```

It runs on:

- pull-request open/synchronize/reopen/ready-for-review;
- pull-request review submitted/dismissed.

The workflow:

1. checks out the exact PR head;
2. resolves the change-control policy from the base SHA;
3. generates the governed semantic change report;
4. fetches GitHub PR reviews;
5. checks independent approvals;
6. independently enforces a two-approval floor if governance-engine files
   changed;
7. updates a persistent PR comment;
8. uploads the report/reviews as 30-day CI evidence;
9. fails the gate on structural or approval violations.

Draft PRs are not gated until they are marked ready for review.

## PR comment

The workflow maintains a single bot comment marked with:

```text
<!-- ebookai-benchmark-change-control -->
```

The comment contains current governed changes, semantic summaries, warnings,
required approvals, current approvers, and blocking failures.

Review submission or dismissal reruns the workflow, so approval status in the
comment follows the current GitHub review state.

## Relationship to Milestone 18

Milestone 18 answers:

> Is the current checked-in benchmark internally trustworthy and free of parser
> accuracy regressions?

Milestone 19 answers:

> Is the proposed change to that benchmark complete, independently reviewed,
> and understandable before it is merged?

Both gates are required for a mature benchmark maintenance process.
