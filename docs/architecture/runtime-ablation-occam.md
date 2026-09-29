# Milestone 21 — Runtime Ablation Pilot & Architecture Simplification

Milestone 21 is an explicit Occam checkpoint.

Its purpose is not to prove that the most complete EBookAI pipeline is best.
Its purpose is to determine which runtime layers earn the right to remain in
the default architecture.

## Decision question

For each added runtime layer, ask:

> Does this layer produce enough reviewed-gold quality improvement or enough
> human-review workload reduction to justify its latency, failure surface,
> dependencies, and maintenance complexity?

If the answer is no, the default direction is simplification.

## What is being ablated

The pilot compares exactly four cumulative variants:

| Variant | Runtime |
|---|---|
| A | PyMuPDF + deterministic reconstruction |
| B | A + Quality Engine + quality-aware parser routing / semantic fallback |
| C | B + deterministic Patch Engine repair |
| D | C + source-grounded AI repair |

The pairwise questions are intentionally simple:

```text
B - A = does parser orchestration earn its complexity?
C - B = does deterministic repair earn its complexity?
D - C = does AI repair earn its complexity?
```

Governance, provenance, Sigstore, review consensus, and change control are not
part of this accuracy ablation. They are trust controls rather than PDF parsing
algorithms.

## Difficulty-balanced pilot

The committed pilot is:

```text
benchmark/ablation/runtime-occam-v1.json
```

It contains 10 real review-plan pages spanning eight required buckets:

- form / vector-like layout;
- hierarchy;
- figure/caption;
- dense technical text;
- table;
- list;
- mixed layout;
- multilingual Japanese / non-Latin text.

The selected pages are:

| Document | PDF page index | Bucket |
|---|---:|---|
| nist-ballot-definition-prototype | 0 | form |
| nist-eel-sp1500-101-v1 | 8 | hierarchy |
| nist-eel-sp1500-101-v1 | 12 | figure |
| nist-eel-sp1500-101-v1 | 24 | dense_text |
| nist-ai-rmf-1-0 | 3 | list |
| nist-ai-rmf-1-0 | 25 | table |
| nist-sp1299-csf2-overview | 2 | mixed_layout |
| nist-sp1299-csf2-overview | 4 | list |
| nist-sp1299-csf2-overview-ja | 2 | multilingual |
| nist-sp1299-csf2-overview-ja | 4 | multilingual |

The first Milestone 20 target, EEL page index 8, is therefore useful evidence
for this pilot but is not enough on its own.

## Evidence floor

Architecture decisions are blocked until both conditions are true:

```text
reviewed pages >= 8
AND
all 8 required difficulty buckets have reviewed evidence
```

A corpus with eight easy text pages does not satisfy the pilot.

Every page must be canonical `reviewed` gold and have matching Milestone 18
consensus provenance.

Inspect readiness:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli ablation-status \
  benchmark/ablation/runtime-occam-v1.json
```

At the time Milestone 21 is introduced, the expected state is:

```text
state = waiting_for_review
reviewed_pages = 0
target_pages = 10
```

This is a valid CI state. It is not a failed experiment and it is not an
architecture conclusion.

## Metrics

Quality is a macro over only the reviewed tasks that exist on each selected
gold page:

- text F1;
- reading-order pair accuracy;
- headings F1;
- lists F1;
- tables F1;
- figures F1;
- captions F1;
- footnotes F1;
- formulas F1.

Missing/unannotated tasks are NA, not zero.

The pilot also tracks:

- failed/timeout page rate;
- elapsed seconds per reviewed page;
- deterministic/AI intervention count;
- Quality Engine review issues per reviewed page;
- human review minutes per page;
- AI cost per page.

A failed parser page is not silently dropped from the quality average. It
contributes zero quality for those pages and also increases failure rate.

## Local A/B/C runner

Once the evidence floor is met:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli ablation-run-local \
  benchmark/ablation/runtime-occam-v1.json \
  --variants A,B,C \
  --output artifacts/runtime-ablation/local
```

The runner:

- materializes exact SHA-pinned corpus bytes;
- evaluates only the evidence-ready pilot pages;
- runs each document/variant in a separate process with a timeout;
- writes BookIR and gold metrics per successful observation;
- preserves failed and timeout observations;
- records selected parser and intervention count.

### Variant A

Variant A deliberately keeps only:

```text
PyMuPDF
+ existing deterministic ReconstructionPipeline
```

Reconstruction is shared because removing it from A would confound the
orchestrator experiment with semantic reconstruction.

### Variant B

Variant B uses the existing ParserOrchestrator with:

```text
pymupdf -> mineru -> marker
```

according to current quality policy.

If PyMuPDF is rejected and the semantic fallbacks are not installed, the
observation is marked `invalid_for_decision`.

The experiment does not interpret a missing dependency as evidence that routing
is useless.

### Variant C

Variant C adds only one deterministic repair pass.

It applies existing Quality Engine `suggested_patch` objects through the
existing PatchEngine. It does not add a new repair algorithm or iterate until
the score looks good.

This keeps C-B attributable to the repair layer already implemented in EBookAI.

## Variant D is intentionally external

The local runner refuses D.

A valid D experiment must explicitly choose and record the real AI
provider/model, latency and cost, then emit the same
`AblationRunArtifact` observation schema.

This prevents CI mocks, canned model responses, or an unpriced API call from
being treated as evidence for keeping AI repair.

A D observation should populate at least:

```text
variant_id = D
document_id
page_indexes
status
elapsed_seconds
quality_macro / metric_values
review_issue_count
manual_review_minutes
ai_cost_usd
intervention_count
valid_for_decision
```

## Human workload is a final-decision requirement

Quality Engine issue count is only a proxy for review burden.

The committed policy has:

```text
require_human_minutes_for_final = true
```

Without measured human review minutes for both sides of a pairwise comparison,
the harness may emit a provisional verdict but:

```text
conclusion_ready = false
```

Do not delete architecture based only on a provisional verdict.

## Occam decision policy

Default thresholds:

```text
meaningful quality gain          >= +0.010
negligible quality gain          <= +0.002
maximum latency multiplier       <= 1.50x
maximum failure-rate increase    <= 0
meaningful review-burden cut     >= 10%
```

Pairwise behavior:

### KEEP

The new layer clears quality or workload benefit and does not violate latency
or failure guardrails.

### REMOVE_CANDIDATE

The new layer adds complexity but produces only negligible quality gain and no
meaningful workload reduction.

### OPTIONAL

There is some benefit, but it does not justify making the layer mandatory—for
example, quality improves while latency exceeds the default guardrail.

### INSUFFICIENT_EVIDENCE

Used when:

- the reviewed evidence floor is not met;
- paired variants do not cover the same evidence-ready pages;
- a result is missing;
- a required runtime dependency was unavailable.

The harness prefers no answer over a false precise answer.

## Analyze results

Combine one or more non-overlapping run artifacts:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli ablation-analyze \
  benchmark/ablation/runtime-occam-v1.json \
  --runs \
    artifacts/runtime-ablation/local/ablation-run.json \
    artifacts/runtime-ablation/ai/ablation-run.json \
  --output artifacts/runtime-ablation/report
```

The output contains:

```text
ablation-report.json
ablation-report.md
```

Duplicate variant/document observations across artifacts are rejected to avoid
cherry-picking the preferred run.

## Current CI behavior

GitHub Actions contains:

```text
Runtime Ablation Pilot Readiness
```

It performs two checks against the real repository:

1. inspect reviewed evidence readiness;
2. run the analyzer with no fake variant results.

Until real reviewed evidence exists, the expected output is:

```text
waiting_for_review
conclusion_ready = false

A -> B: insufficient_evidence
B -> C: insufficient_evidence
C -> D: insufficient_evidence
```

That is the correct Occam result today.

## Change control

The pilot JSON is a governed benchmark asset. Changing targets or lowering the
reviewed-page evidence floor requires independent PR approval.

The decision implementation itself:

```text
ablation.py
ablation_runner.py
```

belongs to the Milestone 19 `governance_engine` category and therefore keeps
the stronger two-independent-approval requirement.

## What happens after evidence exists

The desired output of Milestone 21 is not necessarily four KEEP decisions.

A perfectly successful result may be:

```text
A -> B: KEEP
B -> C: REMOVE_CANDIDATE
C -> D: OPTIONAL
```

That would imply a simpler default architecture and is a better outcome than
preserving every feature simply because it has already been implemented.
