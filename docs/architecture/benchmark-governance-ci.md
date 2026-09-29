# Milestone 18 — Benchmark Governance & CI Accuracy Gate

Milestone 18 turns reviewed gold and parser baselines into governed benchmark
assets.

The project now has an automatic trust escalation model:

```text
no reviewed gold
  -> bootstrap governance
  -> consensus-reviewed canonical gold appears
  -> consensus provenance becomes mandatory
  -> active reviewed baseline becomes mandatory
  -> strict CI accuracy regression becomes automatic
```

There is no manual switch that a maintainer must remember to enable.

## Governance policy

The repository policy lives at:

```text
benchmark/governance/policy.json
```

The initial policy governs:

- CI parser backend: `pymupdf`;
- at least one reviewed document;
- at least one reviewed page;
- at least one eligible governed backend;
- at least one evaluated gold metric per governed backend;
- maximum per-metric regression: `0.02`;
- zero reviewed-document coverage loss;
- zero reviewed-page coverage loss;
- consensus provenance required;
- active baseline required as soon as canonical reviewed gold exists.

The coverage floors are intentionally low at bootstrap. They can be raised as
the human-reviewed corpus grows without changing code.

## Automatic modes

### Bootstrap mode

Bootstrap mode is valid only while canonical reviewed gold is empty and no
active reviewed baseline exists.

The CI gate still verifies:

- corpus manifest can be loaded;
- governance policy is valid;
- provenance registry is structurally valid;
- baseline registry is structurally valid;
- there is no stale active baseline pretending reviewed gold exists.

No real parser accuracy claim is made in this mode.

The report explicitly says that accuracy execution is dormant.

### Strict mode

Strict mode activates automatically when an active reviewed baseline is
registered.

The gate verifies:

1. canonical reviewed gold still matches the baseline's exact SHA-256 set;
2. the corpus manifest still matches the baseline manifest SHA-256;
3. every reviewed page has consensus provenance;
4. every provenance audit exists and matches its pinned SHA-256;
5. reviewer identities in provenance remain independent;
6. the baseline has enough eligible governed backends and coverage;
7. CI reruns the governed parser backend on the exact reviewed document set;
8. current coverage may not drop beyond the configured budget;
9. current gold metrics may not regress beyond the configured metric budget.

The current leaderboard is generated during the gate and preserved as CI
evidence.

## Consensus provenance registry

Canonical consensus provenance lives under:

```text
benchmark/corpus/provenance/
  registry.json
  <document-id>/
    page-<index>-<bundle-id>.consensus-audit.json
```

Milestone 17 workspace audits are useful review artifacts, but Milestone 18
promotes the final consensus audit into the corpus itself when consensus gold is
canonically published.

For each reviewed document the registry records:

- document id;
- source SHA-256;
- current canonical gold SHA-256;
- review records for each reviewed page.

Each page review records:

- consensus bundle id;
- canonical audit path and SHA-256;
- reviewer A and reviewer B;
- adjudicators, when needed;
- publication timestamp.

When another page is reviewed later, the document's current gold hash advances
while the prior page review history is retained.

A reviewed canonical page without registry provenance is a governance failure.

## Baseline version registry

Reviewed baseline snapshots are immutable versions.

The registry is:

```text
benchmark/leaderboard/baselines/registry.json
```

It contains an optional `active_baseline_id` and immutable version entries.

A version entry records:

- baseline id;
- snapshot path;
- snapshot SHA-256;
- snapshot creation time;
- manifest SHA-256;
- reviewed gold SHA-256 map.

Register a generated snapshot:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli baseline-register \
  benchmark/leaderboard/baselines/2026-10-initial.json \
  --id 2026-10-initial
```

Reusing the same baseline id for different bytes is rejected.

The registered snapshot file must remain inside the baseline registry
directory. Moving outside that directory is not accepted as a governed
baseline.

## Governance commands

Static governance inspection:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli governance-check \
  --manifest benchmark/corpus/manifest.json \
  --policy benchmark/governance/policy.json \
  --baseline-registry benchmark/leaderboard/baselines/registry.json \
  --provenance-registry benchmark/corpus/provenance/registry.json \
  --output artifacts/reviewed-accuracy-governance
```

CI-equivalent gate:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli governance-ci \
  --manifest benchmark/corpus/manifest.json \
  --policy benchmark/governance/policy.json \
  --baseline-registry benchmark/leaderboard/baselines/registry.json \
  --provenance-registry benchmark/corpus/provenance/registry.json \
  --cache .cache/ebookai/governance-corpus \
  --output artifacts/reviewed-accuracy-governance
```

In bootstrap mode this does not download the real corpus.

In strict mode it derives the exact reviewed documents and governed backends
from the active baseline, materializes the pinned corpus bytes, runs the parser
benchmark, creates a current reviewed-only leaderboard, and applies governance.

## CI job

GitHub Actions now contains:

```text
Reviewed Accuracy Governance Gate
```

The job installs only the stable governed parser dependency and calls
`governance-ci`.

Evidence is uploaded even when the gate fails.

The artifact contains:

```text
governance-report.json
governance-report.md
governance-release.json
```

Strict mode additionally contains:

```text
benchmark/
leaderboard/
```

## Governance release manifest

Every governance execution creates `governance-release.json`.

It pins:

- corpus manifest SHA-256;
- governance policy SHA-256;
- provenance registry SHA-256;
- baseline registry SHA-256;
- active baseline id and SHA-256;
- current reviewed gold SHA-256 map;
- governance report SHA-256;
- governance mode and status.

This is an audit manifest for the benchmark state itself. It is separate from
the EPUB publication release manifest because it answers a different question:
which exact benchmark assets and governance rules produced this accuracy gate?

## Failure examples

The gate fails closed when:

- a canonical annotation is changed to `reviewed` without consensus provenance;
- a consensus audit is missing or modified;
- canonical reviewed gold exists but no active baseline is registered;
- the corpus manifest changes without a new baseline;
- reviewed gold bytes change without a new baseline;
- the active baseline file is modified after registration;
- the governed backend loses reviewed page/document coverage;
- a governed metric drops more than the configured regression budget;
- the current governed parser run becomes ineligible or fails.

## Current repository state

The current real corpus still has zero canonical reviewed pages.

Therefore the repository is deliberately in:

```text
mode = bootstrap
status = pass
reviewed_documents = 0
reviewed_pages = 0
active_baseline = none
```

This is not an accuracy endorsement. It means the governance system correctly
recognizes that the project has not yet produced its first independently
reviewed benchmark truth.

Once the first Milestone 17 consensus is published, bootstrap can no longer
pass without creating and registering a reviewed baseline.

## First strict activation sequence

1. Two humans independently review the same real target.
2. Resolve any conflict through independent adjudication.
3. Publish consensus canonical gold.
4. Confirm the canonical consensus audit and provenance registry are committed.
5. Run the parser benchmark and reviewed-only leaderboard.
6. Create a reviewed baseline snapshot.
7. Register it with a new immutable baseline id.
8. Commit gold, provenance, baseline snapshot and baseline registry together.
9. CI automatically enters strict mode.
10. Future parser changes are governed by coverage and accuracy regression
   budgets.
