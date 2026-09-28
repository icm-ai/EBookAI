# Golden Corpus & End-to-End Regression Harness

Milestone 12 introduces a reproducible quality benchmark for the BookIR pipeline.

The goal is not to claim a universal PDF-to-book accuracy percentage. The golden
corpus measures regression against explicit expectations for representative
document classes and makes known capability gaps visible.

## Corpus policy

The initial corpus uses synthetic PDFs generated deterministically at test time.
This avoids committing copyrighted book pages or opaque binary fixtures while
still exercising real PDF parsing, reconstruction, Quality Engine analysis,
EPUB compilation, EPUB structural QA, and external EPUBCheck.

Initial categories:

- digital PDF
- footnote-heavy page
- multi-column layout
- table-like layout
- scanned/image-only PDF

Synthetic cases are a bootstrap benchmark, not a substitute for a later
rights-cleared real-world corpus.

## Per-case contract

Each JSON case defines:

- document category and deterministic fixture generator
- minimum expected BookIR node types
- required text fragments
- expected reading-order fragments
- required/forbidden quality issue codes
- minimum footnote-reference associations
- expected publication readiness
- regression thresholds
- explicit known gaps

A case passes only when all explicit assertions and thresholds pass.

## Metrics

The harness reports:

### Semantic structure

`semantic_score` is an expectation-conformance score built from declared node
type, text, reading-order, and footnote requirements. It is **not** a
probability of correctness and must not be presented as model accuracy.

### Text recall

Fraction of declared text fragments recovered in reconstructed BookIR.

### Reading order

Fraction of adjacent expected fragment pairs that appear in the expected order.

### Provenance coverage

Fraction of content-bearing BookIR nodes that retain at least one `SourceRef`.

### BBox coverage

Fraction of retained source references that carry concrete bounding boxes.

### EPUB text recall

Fraction of expected fragments that survive into generated EPUB XHTML.

### Reproducibility

The same BookIR is compiled twice and the EPUB bytes must be identical.

### Publication conformance

Built-in Publication QA runs for every case. In the dedicated CI gate,
EPUBCheck 5.4.0 also validates each generated EPUB when the case is expected to
be publishable.

## Render evidence

The first render-regression layer is browser-independent and deterministic. The
harness extracts the compiled EPUB XHTML and records:

- normalized XHTML/DOM digest
- block text-flow digest
- stylesheet digest
- section count

These signatures are uploaded as CI evidence and can be compared across runs.
They intentionally avoid pretending that DOM equality is pixel equality.

A later corpus expansion may add browser-engine raster screenshots, but such
evidence should be versioned by renderer/browser because font rasterization and
platform differences make raw pixel hashes unstable across environments.

## Known gaps

Known gaps are explicit metadata, not ignored failures.

The initial scanned fixture expects the lightweight PyMuPDF path to produce an
`empty_document` issue and records `ocr_required`. This verifies that an
image-only source is routed as a capability gap rather than falsely accepted.

The initial table fixture records `table_semantics`: current lightweight
reconstruction must retain text/provenance and produce valid EPUB, but the
baseline does not falsely require a semantic `TABLE` node before a
table-capable parser/reconstructor is integrated.

The multi-column fixture similarly records `multi_column_semantic_grouping`
while still gating text recovery, reading order, provenance, and publication
output.

When a capability improves, the workflow is:

1. strengthen the case expectations;
2. remove or narrow the corresponding known gap;
3. commit the new threshold/baseline in the same change;
4. require the stronger behavior from then on.

## CI evidence

The dedicated `Golden Corpus Regression Gate` writes
`artifacts/golden-regression/golden-report.json` and per-case artifacts, then
uploads them even when the gate fails.

This means a regression has inspectable evidence instead of a single red/green
number.
