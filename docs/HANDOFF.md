# EBookAI Engineering Handoff

Last updated: 2026-10-03

This document is the canonical handoff entry point for continuing the current EBookAI work.
Read this file first, then follow the referenced architecture documents and current GitHub state.

## 1. Current repository state

| Item | Current value |
|---|---|
| Repository | `icm-ai/EBookAI` |
| Active engineering branch | `milestone-21-runtime-ablation-pilot` |
| Branch HEAD before this handoff update | `73393db30cfa219a8f9903802b2df6b63bc6bbe7` |
| Milestone | **21 — Runtime Ablation Pilot & Architecture Simplification** |
| Operating principle | **Occam's razor: keep runtime complexity only when reviewed evidence justifies it** |
| Feature-development posture | Paused while Milestone 21 evidence is collected and analyzed |

A separate human-review branch/PR exists for the Milestone 21 evidence batch:

- PR: `#3` — `review(ablation): assign 陈明 and PDP to runtime Occam pilot`
- Base: `architecture/book-ir`
- Head: `review/runtime-occam-v1-human-batch`
- State: **open, draft**
- Review package workflow run: `36651219486`
- Review package artifact: `11070447476`

Do not confuse the engineering branch with the human-review PR branch.

## 2. What has been completed

Milestones 1–20 established the current BookIR-based conversion, quality, review, publication, benchmark, and governance stack. The implementation is present in the repository; Milestone 21 is not a new feature-expansion phase, but an evidence-driven simplification checkpoint.

### Core BookIR and conversion pipeline

Implemented areas include:

- BookIR domain models and EPUB compiler;
- deterministic reconstruction pipeline;
- PyMuPDF parser adapter;
- MinerU and Marker parser adapters;
- quality-aware parser orchestration and parser capability handling;
- legacy conversion compatibility paths required by the existing backend/API surface.

Primary code:

- `backend/src/book/domain/`
- `backend/src/book/reconstruction/`
- `backend/src/book/parsers/`
- `backend/src/book/orchestration/`
- `backend/src/book/compiler/`

### Quality and repair

Implemented areas include:

- Quality Engine and issue detectors;
- deterministic Patch Engine;
- source-grounded repair evidence;
- source-grounded AI repair proposals;
- reversible review/session mechanics.

Primary code:

- `backend/src/book/quality/`
- `backend/src/book/repair/`
- `backend/src/book/review/`

### Human review and publication QA

Implemented areas include:

- human review workbench/API/UI;
- reversible review state;
- publication QA;
- external EPUBCheck integration;
- release pipeline and provenance;
- release attestation;
- standalone release verification;
- native Sigstore support.

Primary code/docs:

- `backend/src/api/gold_review.py`
- `frontend/web/src/components/GoldReviewWorkbench.js`
- `backend/src/book/publication/`
- `docs/architecture/release-attestation.md`
- `docs/architecture/standalone-verifier-sigstore.md`

### Real-world benchmark, gold data, review, and governance

Milestones 13–20 moved validation away from synthetic-only fixtures toward rights-cleared real-world PDFs and a governed benchmark workflow.

Implemented areas include:

- real-world corpus manifest and provenance handling;
- PyMuPDF / MinerU / Marker parser-level comparison;
- gold annotations;
- independent reviewer workflow;
- multi-reviewer consensus;
- reviewed campaigns;
- benchmark leaderboard/baselines;
- governance policy and benchmark change control;
- CI readiness gates.

Key documents:

- `docs/architecture/real-world-parser-benchmark.md`
- `docs/architecture/golden-corpus.md`
- `docs/architecture/gold-annotation-benchmark.md`
- `docs/architecture/gold-review-workbench.md`
- `docs/architecture/multi-reviewer-consensus.md`
- `docs/architecture/first-reviewed-campaign.md`
- `docs/architecture/gold-corpus-leaderboard.md`
- `docs/architecture/benchmark-governance-ci.md`
- `docs/architecture/benchmark-change-control.md`

## 3. Current Milestone 21 objective

Milestone 21 is an explicit Occam checkpoint. Its purpose is to determine which runtime layers earn the right to remain in the default architecture.

Canonical design document:

- `docs/architecture/runtime-ablation-occam.md`

Canonical pilot configuration:

- `benchmark/ablation/runtime-occam-v1.json`

Exactly four cumulative runtime variants are compared:

| Variant | Runtime |
|---|---|
| A | PyMuPDF + deterministic reconstruction |
| B | A + Quality Engine + quality-aware parser routing / semantic fallback |
| C | B + deterministic Patch Engine repair |
| D | C + source-grounded AI repair |

The pairwise questions are:

```text
B - A = does parser orchestration earn its complexity?
C - B = does deterministic repair earn its complexity?
D - C = does AI repair earn its complexity?
```

Milestone 21 tooling is implemented in:

- `backend/src/book/benchmark/ablation.py`
- `backend/src/book/benchmark/ablation_runner.py`
- `backend/tests/test_runtime_ablation.py`

**Important:** implementation of the ablation harness does not mean the experiment is complete. No architecture KEEP/REMOVE conclusion is currently justified.

## 4. Evidence floor and current review state

The pilot contains 10 real review-plan pages spanning eight required difficulty buckets:

- form / vector-like layout;
- hierarchy;
- figure/caption;
- dense technical text;
- table;
- list;
- mixed layout;
- multilingual Japanese / non-Latin text.

Architecture decisions are blocked until both conditions are true:

```text
reviewed pages >= 8
AND
all 8 required difficulty buckets have reviewed evidence
```

Every decision page must be canonical `reviewed` gold with matching Milestone 18 consensus provenance.

### Human-review batch

PR #3 created the first real independent human-review batch:

- Reviewer A: 陈明
- Reviewer B: PDP
- Scope: 8 pages covering all 8 required buckets
- Reserve pages: intentionally excluded to minimize human workload
- Artifact: 16 independent reviewer packages plus persisted Gold Review workspace

Review procedure already agreed:

1. complete **EEL page index 8** first as the calibration page;
2. independently review the remaining seven pages;
3. keep 陈明 and PDP review boundaries independent;
4. do not copy or reconcile answers before the independent pass is complete;
5. do not modify GitHub review records unless the user explicitly authorizes it.

PR #3 remains a draft and explicitly claims **no reviewed gold or consensus provenance yet**.

## 5. Known review limitations

Two limitations were identified during the independent-review work:

1. **XFA form rendering is not visually available in the review package.**
2. **NIST AI RMF page index 25 does not contain the expected table content for the intended table bucket.**

The user chose the following handling rule:

> Keep the original review scope and record the limitations; do not silently swap pages or redesign the pilot.

Therefore:

- do not replace these pages without explicit approval;
- record the limitation in reviewer evidence;
- do not manufacture certainty for content that cannot be inspected;
- do not lower the eight-bucket evidence rule to make the pilot pass.

## 6. Backend technical-debt cleanup completed before handoff

Milestone 21 exposed legacy CI failures that were not introduced by the ablation work. These were repaired before continuing the experiment.

The cleanup covered, among other items:

- Black/isort/Flake8 debt;
- invalid `pdfplumber.Page` type usage;
- legacy conversion import compatibility;
- API/test contract drift;
- health, cleanup, batch, conversion, and integration test drift;
- async/event-loop and mock behavior;
- pytest configuration and marker handling;
- Docker dependency conflict (`httpx`/`httpcore`/`h11`);
- compatibility shims for old import paths used by the existing backend.

The cleanup was squashed into:

```text
73393db30cfa219a8f9903802b2df6b63bc6bbe7
fix(backend): retire legacy CI technical debt
```

Validation workflow run:

```text
36675576427 — Backend Debt Probe — success
```

That run verified:

- `black --check backend/`
- `isort --check-only backend/`
- `flake8 backend/ --max-line-length=100 --extend-ignore=E203,W503`
- full backend pytest suite with coverage invocation
- Docker build
- `python -m pip check` inside the built image

The temporary repair/probe workflow and repair script were removed after validation; they are not part of the final branch tree.

## 7. Important files for the next engineer/agent

Read these first:

1. `docs/HANDOFF.md` — this file
2. `docs/architecture/runtime-ablation-occam.md` — Milestone 21 design and decision policy
3. `benchmark/ablation/runtime-occam-v1.json` — governed pilot definition
4. `benchmark/corpus/review-plan.json` — review-plan source
5. `backend/src/book/benchmark/ablation.py` — evidence readiness and analysis logic
6. `backend/src/book/benchmark/ablation_runner.py` — local A/B/C execution
7. `backend/tests/test_runtime_ablation.py` — behavioral contract
8. PR #3 and run `36651219486` — independent human-review batch
9. `docs/architecture/multi-reviewer-consensus.md` — consensus requirements
10. `docs/architecture/benchmark-change-control.md` — governed-change constraints

## 8. Exact next actions

Continue in this order unless the user explicitly changes priorities.

### Step 1 — finish independent human review evidence

- Use the PR #3 reviewer packages.
- Start with EEL page index 8 calibration.
- Complete the remaining seven pages independently.
- Preserve the XFA and AI RMF p25 limitations as limitations, not silent substitutions.
- Maintain independence from PDP.
- Do not write review results back to GitHub unless explicitly asked.

### Step 2 — obtain the second independent review

PDP must complete the same scoped review independently.

Do not collapse two reviewers into one synthetic or AI-generated consensus.

### Step 3 — persist reviewed gold and consensus provenance when authorized

Only after the independent passes are available and the user authorizes repository writes for the review record:

- persist canonical reviewed gold;
- run/record consensus;
- preserve reviewer provenance;
- adjudicate only actual conflicts that require it.

### Step 4 — check the Milestone 21 evidence floor

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli ablation-status \
  benchmark/ablation/runtime-occam-v1.json
```

Do not run architectural conclusions while the state is `waiting_for_review` or while any required bucket lacks reviewed evidence.

### Step 5 — run local A/B/C ablation

Once evidence-ready:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli ablation-run-local \
  benchmark/ablation/runtime-occam-v1.json \
  --variants A,B,C \
  --output artifacts/runtime-ablation/local
```

Variant B must not treat unavailable semantic fallback dependencies as evidence that routing is useless; such observations are `invalid_for_decision`.

### Step 6 — run Variant D separately with a real AI provider

The local runner intentionally refuses D.

A valid D experiment must record the actual provider/model, latency, failures, intervention count, review workload, and cost in the common ablation artifact schema.

Do not use mocked/canned CI model output as evidence for keeping AI repair.

### Step 7 — analyze all valid observations

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli ablation-analyze \
  benchmark/ablation/runtime-occam-v1.json \
  --runs \
    artifacts/runtime-ablation/local/ablation-run.json \
    artifacts/runtime-ablation/ai/ablation-run.json \
  --output artifacts/runtime-ablation/report
```

Expected outputs:

- `ablation-report.json`
- `ablation-report.md`

### Step 8 — simplify only if evidence supports it

The desired result is not “keep every implemented layer.”

A successful Milestone 21 may conclude that a layer is:

- `KEEP`
- `REMOVE_CANDIDATE`
- `OPTIONAL`
- `INSUFFICIENT_EVIDENCE`

Do not delete or redesign architecture from a provisional result. Human review minutes are required for final pairwise conclusions under the committed policy.

## 9. Constraints and decisions already made

These should be treated as project decisions unless the user explicitly changes them:

- follow Occam's razor;
- do not resume milestone feature expansion before the ablation evidence is resolved;
- do not add new repair algorithms just to improve the pilot score;
- do not change pilot targets to avoid difficult evidence;
- do not interpret missing optional parser dependencies as negative quality evidence;
- do not treat unannotated tasks as zero;
- do not silently drop failed parser pages from quality averages;
- do not make final architecture deletion decisions from proxy-only or provisional evidence;
- keep reviewer independence intact;
- preserve governance, provenance, consensus, Sigstore, and change control as trust controls outside the runtime-accuracy ablation.

## 10. Resume checklist

Before changing code:

```bash
git checkout milestone-21-runtime-ablation-pilot
git pull --ff-only

git log -1 --oneline
```

Then verify the expected milestone state:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli ablation-status \
  benchmark/ablation/runtime-occam-v1.json
```

If the repository state differs from this handoff, inspect recent commits/PRs first rather than assuming this document is newer.

## 11. Suggested first instruction for a successor agent

> Read `docs/HANDOFF.md` first. Then inspect `docs/architecture/runtime-ablation-occam.md`, `benchmark/ablation/runtime-occam-v1.json`, and PR #3. Continue from the first incomplete item under “Exact next actions”. Preserve the existing Occam constraints and reviewer-independence boundary; do not redesign completed milestones or modify review records unless explicitly authorized.
