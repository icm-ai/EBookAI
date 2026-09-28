# Milestone 15 — Gold Corpus Expansion & Parser Leaderboard

Milestone 15 turns the sparse-gold evaluator from Milestone 14 into an
operational corpus-growth and parser-comparison workflow.

The milestone has four goals:

1. expand the real PDF corpus beyond the original two documents;
2. maintain an explicit queue of difficult pages that need human gold review;
3. aggregate reviewed-gold accuracy into a coverage-aware parser leaderboard;
4. keep latency and Quality Engine proxies visible without mixing them into the
   accuracy rank.

## Real corpus

The corpus now contains five SHA-256-pinned real PDFs:

| Document | Language | Pages | Role |
|---|---|---:|---|
| NIST Ballot Definition Prototype | en | 1 | form-like/vector smoke fixture |
| NIST SP 1500-101 Election Event Logging | en | 32 | long technical standard |
| NIST AI RMF 1.0 | en | 48 | long framework with TOC, tables and figures |
| NIST SP 1299 CSF 2.0 Resource & Overview Guide | en | 8 | short mixed-layout guide |
| NIST SP 1299 Japanese translation | ja | 8 | non-Latin translated guide |

The three Milestone 15 additions are download-only. Their exact byte counts,
page counts, and SHA-256 digests were obtained by a temporary CI probe against
the official NIST download endpoints before being committed to the corpus
manifest.

All remote PDFs remain integrity-pinned. A changed upstream file fails corpus
materialization rather than silently changing the benchmark.

## Review queue

`benchmark/corpus/review-plan.json` selects 25 pages across all five
documents.

The queue intentionally mixes:

- front matter and title pages;
- table of contents / hierarchy-heavy pages;
- dense technical text;
- tables;
- figures and captions;
- appendix/end matter;
- form-like layout;
- Japanese non-Latin text.

A review target is not gold. It becomes leaderboard evidence only after an
annotation for that document is explicitly marked `reviewed`.

The queue currently contains two draft annotations:

- NIST EEL PDF page index 8;
- NIST AI RMF PDF page index 3.

Both remain excluded from the formal leaderboard.

Validate and summarize the queue:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli review-plan \
  --manifest benchmark/corpus/manifest.json \
  --plan benchmark/corpus/review-plan.json \
  --output artifacts/gold-review-plan.md
```

The JSON summary includes counts for `unannotated`, `draft`, and
`reviewed`.

## Leaderboard policy

`benchmark/leaderboard/policy.json` defines the default leaderboard policy.

By default:

- only `reviewed` annotations are eligible;
- a backend must have at least one reviewed document and one reviewed page;
- each available gold accuracy dimension is macro-averaged across eligible
  runs;
- the overall accuracy macro is the unweighted mean of the available accuracy
  dimensions;
- latency and Quality Engine score are reported separately and do not alter
  accuracy rank;
- draft annotations can only be included by explicit opt-in;
- baseline comparison allows at most the configured per-metric regression.

The default accuracy dimensions are:

- text token F1;
- reading-order pair accuracy;
- heading F1;
- list F1;
- table F1;
- figure F1;
- caption F1;
- footnote F1;
- formula F1.

This prevents a fast parser with weak correctness from winning merely because
latency is low, and prevents a parser with one easy annotated page from looking
equivalent to a parser evaluated across broader coverage without exposing the
coverage difference.

## Build a leaderboard

After running the parser benchmark:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli leaderboard \
  artifacts/parser-benchmark/benchmark-results.json \
  --policy benchmark/leaderboard/policy.json \
  --output artifacts/parser-leaderboard
```

Outputs:

- `leaderboard.json`;
- `leaderboard.md`.

Until at least one annotation is human-reviewed, formal entries remain
ineligible and have no rank. This is intentional.

For exploratory work only, draft annotations can be included:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli leaderboard \
  artifacts/parser-benchmark/benchmark-results.json \
  --policy benchmark/leaderboard/policy.json \
  --include-draft \
  --output artifacts/parser-leaderboard-draft
```

The generated Markdown states whether the ranking is reviewed-only or includes
drafts.

## Baseline regression

A saved `leaderboard.json` can be used as a reviewed-gold baseline:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli leaderboard \
  artifacts/parser-benchmark/benchmark-results.json \
  --policy benchmark/leaderboard/policy.json \
  --baseline benchmark/leaderboard/baseline.json \
  --output artifacts/parser-leaderboard
```

The comparison is metric-based, not rank-based. A backend can change rank
because another backend improved without being considered a regression.

Only a drop in a directly comparable gold metric beyond the configured
allowance fails the comparison.

## Human review promotion

A reviewer should promote a draft annotation only after checking the exact
SHA-pinned PDF:

1. verify page index and source SHA-256;
2. verify every enabled task is complete for its intended page scope;
3. inspect matched/unmatched evidence from at least one parser;
4. correct text, semantic type, hierarchy level, bbox, and reading order as
   necessary;
5. set `status` to `reviewed`;
6. record `reviewed_by`;
7. rerun `gold-validate`, benchmark, and leaderboard.

No CLI command automatically promotes draft gold. Promotion is deliberately a
review decision rather than an automated state transition.

## Accuracy × latency × quality matrix

The leaderboard keeps three dimensions visible:

- **accuracy** — reviewed-gold metrics and accuracy macro;
- **latency** — mean successful parser runtime;
- **quality proxy** — mean Quality Engine score.

Only accuracy determines the leaderboard rank. The other columns remain
diagnostic engineering dimensions.

This separation is important because the Quality Engine is a heuristic proxy
and parser runtime is a resource/performance measurement, not a correctness
label.

## Current limitation

Milestone 15 completes the infrastructure and corpus selection, but it does not
claim that AI-authored draft labels are human-reviewed.

At the current repository state, the formal reviewed-only leaderboard is
expected to have no eligible ranked backend. The review queue makes the next
work explicit: review and promote the selected pages, then save the first
reviewed leaderboard baseline.
