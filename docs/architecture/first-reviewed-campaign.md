# Milestone 20 — First Real Reviewed Gold Campaign & Strict Baseline Activation

Milestone 20 turns the review/governance infrastructure from Milestones 14–19
into an executable first human-review campaign.

The implementation deliberately separates two things:

1. the real campaign target and activation rules, which can be committed now;
2. actual human reviewer identities and review decisions, which must not be
   invented.

The repository therefore contains a real campaign in `planned` state, not a
fabricated reviewed result.

## First campaign target

The checked-in campaign is:

```text
benchmark/campaigns/first-reviewed-v1.json
```

It selects one page:

```text
document_id = nist-eel-sp1500-101-v1
page_index  = 8
tasks       = headings, reading_order
```

This page was chosen because:

- it already has the Milestone 14 draft seed;
- the seed contains exactly three headings;
- the Milestone 15 review-plan tasks exactly match the seed tasks;
- it is small enough to complete the first independent-review loop without
  mixing in tables, figures, OCR, or task-schema changes;
- one reviewed page is sufficient to exercise the initial Milestone 18
  governance floor.

The existing seed remains:

```text
status = draft
annotated_by = ChatGPT-assisted visual seed
reviewed_by = ""
```

Milestone 20 does not alter those facts.

## Campaign state machine

The campaign engine is:

```text
backend/src/book/benchmark/campaign.py
```

The state model is:

```text
planned
  |
  | campaign-assign
  v
assigned
  |
  | independent A/B workbench review
  | promotion + consensus publication
  v
ready_for_activation
  |
  | campaign-activate
  v
strict
```

A partially completed campaign may also report `reviewing`. Structural
inconsistency reports `blocked`.

The state is derived from canonical repository evidence:

- campaign spec;
- review batch;
- canonical gold status;
- canonical consensus provenance;
- baseline registry;
- Milestone 18 governance.

There is no hand-edited `completed=true` field.

## Inspect current status

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli campaign-status \
  benchmark/campaigns/first-reviewed-v1.json \
  --output artifacts/first-reviewed-campaign
```

Current repository state is intentionally:

```text
state = planned
reviewed_targets = 0 / 1
active_baseline = none
```

The command exits successfully because the campaign is structurally valid.
Pending human work is reported separately from invariant failures.

## Assign real reviewers

When actual reviewer identities are known:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli campaign-assign \
  benchmark/campaigns/first-reviewed-v1.json \
  --created-by <maintainer> \
  --reviewer-a <reviewer-a> \
  --reviewer-b <reviewer-b> \
  --adjudicator <reviewer-c>
```

The default batch is:

```text
benchmark/review-batches/first-reviewed-v1.json
```

The exact campaign target set is enforced. Reviewer A and reviewer B must be
different identities. If an adjudicator is assigned, that identity must differ
from both reviewers.

## Independent review packages

Generate source-grounded packages after assignment:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli campaign-packages \
  benchmark/campaigns/first-reviewed-v1.json \
  benchmark/review-batches/first-reviewed-v1.json \
  --output artifacts/first-reviewed-review-packages
```

Two separate Gold Review workbench sessions are created from the same
canonical revision.

Each reviewer package contains:

```text
source-page.png
draft-gold.json
parser-bookir.json
package.json
README.md
```

The package records:

- campaign and batch id;
- reviewer identity and role;
- independent workbench session id;
- source SHA-256;
- canonical gold hash at session open;
- review backend;
- assigned tasks.

The package README explicitly instructs reviewers not to inspect the other
reviewer's annotation before promotion.

Generating packages does not change canonical gold or provenance.

## Consensus must match the campaign assignment

After the two workbench sessions are promoted, Milestone 17 consensus is used
normally.

Campaign readiness checks the resulting provenance identities against the
batch assignment.

For each campaign target:

```text
{provenance reviewer_a, reviewer_b}
        ==
{assigned reviewer_a, reviewer_b}
```

Order does not matter.

If adjudication occurred, the provenance adjudicator must match the assigned
adjudicator.

A consensus created by different people does not count toward this campaign.

## Strict activation

After canonical consensus publication, status becomes:

```text
ready_for_activation
```

Then run:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli campaign-activate \
  benchmark/campaigns/first-reviewed-v1.json \
  benchmark/review-batches/first-reviewed-v1.json \
  --output artifacts/first-reviewed-activation
```

Activation performs the complete first-baseline pipeline:

1. revalidate campaign and review-batch identities;
2. require every campaign target to be canonical `reviewed`;
3. require canonical consensus provenance;
4. enumerate the complete current reviewed corpus;
5. materialize exact SHA-pinned source PDFs;
6. run the campaign benchmark backend set;
7. build the reviewed-only leaderboard;
8. build a provenance-pinned baseline snapshot;
9. write `benchmark/leaderboard/baselines/first-reviewed-v1.json`;
10. register and activate `first-reviewed-v1`;
11. execute Milestone 18 governance with the freshly generated leaderboard;
12. require `mode=strict` and `status=pass`;
13. write benchmark, leaderboard, activation and governance evidence.

The first campaign uses `pymupdf`, matching the current governance CI backend.

## Full reviewed corpus, not campaign-only cherry-picking

The activation benchmark is not limited to campaign targets.

It discovers every canonical reviewed document in the manifest and benchmarks
all of them.

That matters once later campaigns add more reviewed pages: a new baseline may
not silently benchmark only the newest/easiest page while omitting existing
reviewed truth.

Milestone 18 full-reviewed-coverage rules remain authoritative.

## Transactional activation

Baseline activation changes tracked governance state:

```text
baseline snapshot
baseline registry
```

Milestone 20 backs up both before activation.

If final strict governance fails for any reason, including coverage floors or
metric eligibility, it restores the previous registry bytes and restores or
removes the candidate snapshot.

The repository is therefore not left in a half-activated state.

## What strict activation means

The first strict baseline is a regression reference, not an assertion that the
current parser is already excellent.

It says:

> these parser metrics were measured against independently reviewed,
> provenance-pinned truth, and future governed changes may not silently
> regress beyond the configured budget.

Absolute quality floors can be tightened later as the reviewed corpus expands.

## CI readiness gate

The main CI now contains:

```text
First Reviewed Campaign Readiness
```

It runs `campaign-status` against the real campaign and uploads:

```text
campaign-status.json
campaign-status.md
```

The job passes for legitimate in-progress states such as `planned`,
`assigned`, or `reviewing`.

It fails for structural inconsistency, such as:

- reviewed gold without provenance;
- provenance without reviewed canonical gold;
- consensus reviewer identities that differ from assignment;
- invalid active campaign baseline;
- strict governance failure.

Once the real campaign reaches strict state, the same job verifies that state
without a separate feature flag.

## Relationship to Milestone 19

Campaign specs are governed benchmark assets.

Changes under:

```text
benchmark/campaigns/
```

require independent PR approval.

The campaign orchestration implementation itself is part of the protected
`governance_engine`, so modifications require the Milestone 19 two-approval
floor.

## Current honest boundary

Milestone 20 implements and validates the complete transition to strict mode,
including an end-to-end test that performs independent sessions, consensus,
baseline generation and strict governance on a real PDF fixture.

The real NIST campaign is not activated yet because no real independent
reviewer identities or decisions have been supplied.

No AI-generated annotation is promoted merely to make the milestone appear
complete.
