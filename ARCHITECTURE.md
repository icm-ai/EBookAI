# EBookAI Next Architecture

EBookAI is evolving from a generic format converter into a **semantic book reconstruction engine**.

The core design goal is not merely to produce an EPUB file. It is to reconstruct an imperfect source document into a trustworthy, auditable, editable, and reflowable digital book.

## Architectural principles

1. **BookIR is the system of record.** Parser output is normalized into BookIR before reconstruction, repair, quality analysis, or publishing.
2. **Source provenance is never discarded.** Every reconstructed node can point back to its source page and bounding box.
3. **Parsers extract; reconstruction interprets.** Parser adapters must not silently perform book-level semantic rewriting.
4. **AI proposes patches; it does not rewrite the canonical book wholesale.** Repairs are explicit, reviewable, and reversible.
5. **Quality is node-level and actionable.** Low-confidence nodes can be routed through progressively more expensive repair stages.
6. **Compilers publish BookIR.** EPUB, HTML, and Markdown are outputs, not internal canonical representations.
7. **Backends are replaceable.** PyMuPDF, MinerU, Marker, Docling, PaddleOCR, and future parsers should converge on the same BookIR schema.

## Target pipeline

PDF/source document -> Parser Adapter -> BookIR -> reconstruction/quality/repair -> Book Compiler -> EPUB/HTML/Markdown

## BookIR v0.1

BookIR v0.1 is deliberately small. It establishes stable identity, semantic node types, provenance, confidence, patch history, and JSON round-tripping.

### Core entities

- Book: metadata, root nodes, schema version, patch history.
- BookNode: stable node id, node type, content, attributes, children.
- SourceRef: source id, zero-based page index, bounding box, parser name.
- Confidence: extraction, structure, and reading-order confidence in [0, 1].
- Patch: an explicit proposed/applied change against a BookNode.

### Provenance invariant

A parser-produced textual node retains page index, bounding box, parser identity, and a stable source id. No downstream pass should need to guess where extracted text came from.

### Patch invariant

Model-assisted repair must eventually be represented as an explicit patch rather than replacing an entire chapter with model output. BookIR v0.1 defines the patch envelope; deterministic patch application lands in a later milestone.

## Package layout

    backend/src/book/
    ├── domain/
    │   └── models.py
    ├── parsers/
    │   ├── base.py
    │   └── pymupdf.py
    ├── reconstruction/
    ├── repair/
    ├── quality/
    └── compiler/
        └── epub.py

The existing services/conversion/ pipeline remains intact during migration.

## Migration plan

### Milestone 1 — BookIR spine

- [x] Define BookIR v0.1.
- [x] JSON serialization/deserialization.
- [x] Add parser adapter interface.
- [x] Add PyMuPDF adapter preserving page/bbox/font provenance.
- [x] Add minimal dependency-light EPUB3 compiler.
- [x] Add focused tests.
- [ ] Wire the new pipeline to an opt-in API/CLI entry point.

### Milestone 2 — Structural reconstruction

- [x] Repeated header/footer removal using normalized text + margin geometry + page coverage.
- [x] Cross-page paragraph joining using page geometry, punctuation, font consistency, and language-aware joining.
- [x] Heading hierarchy inference using typography plus strong chapter/part patterns.
- [x] Footnote definition detection and same-page reference association.
- [x] Preserve provenance across merged paragraphs.
- [x] Preserve suppressed header/footer nodes as an audit trail in BookIR metadata.

The default deterministic pass order is:

    HeaderFooterRemovalPass
      -> HeadingInferencePass
      -> FootnoteAssociationPass
      -> ParagraphMergePass

This ordering intentionally classifies headings and footnotes before paragraph
merging so semantic blocks cannot be accidentally merged into body paragraphs.

#### Reconstruction rules

**Header/footer removal** only considers blocks inside configurable top/bottom
page margins. Repeated text is normalized with Unicode NFKC, whitespace
collapse, case folding, and digit normalization so changing page numbers can
still be recognized as one repeated footer pattern. Removed nodes are retained
under `metadata.extra.reconstruction.suppressed_nodes` with their original
source references.

**Paragraph merging** currently targets high-confidence adjacent-page
continuations. It requires a previous block near the bottom of page N, a next
block near the top of page N+1, compatible font sizes, and no terminal sentence
punctuation. Latin end-of-line hyphenation is repaired, while CJK boundaries
are concatenated without inserting an artificial space. A merged paragraph
retains all contributing `SourceRef` entries and records `merged_from`.

**Heading inference** uses strong chapter/part patterns and relative typography.
It annotates inferred headings with a semantic level and raises structure
confidence without altering source provenance.

**Footnote association** identifies marker-prefixed, small-font blocks in the
lower page region and records same-page body nodes containing the marker as
references. The text itself is not rewritten in this milestone.

### Milestone 3 — Quality and patch engine

- [x] Deterministic node-level quality detectors.
- [x] Evidence-backed `QualityIssue` and serializable `QualityReport`.
- [x] Review-priority severities and heuristic book quality score.
- [x] Explicit suggested patches for safe, deterministic repairs.
- [x] Confidence recalculation as a separate opt-in BookIR transformation.
- [x] Operation-specific patch validation.
- [x] Deterministic patch application with before-state audit data.
- [x] Apply/replace proposed patches in `Book.patches` without silent mutation.
- [x] Support replace-content, set-attribute, insert, delete, move, merge, and split.
- [x] Focused CI coverage for Quality Engine + Patch Engine.

#### Quality Engine contract

`QualityEngine.analyze(book)` is pure: it returns a report and never mutates the
book. The default detectors currently cover missing provenance, low confidence,
raw text blocks that remain after reconstruction, empty semantic nodes, orphan
footnotes, and heading hierarchy errors.

Every issue carries a deterministic id, code, severity, affected node ids,
confidence, evidence, and optionally a fully serialized suggested `Patch`.
The quality score is intentionally heuristic and review-oriented; it is not a
claim about semantic truth or publication correctness.

Confidence recalculation is explicitly separate:

    book, report = QualityEngine().recalculate_confidence(book)

It only lowers confidence according to documented issue-specific caps. It
never raises confidence and stores the report under
`metadata.extra.quality.report`.

#### Patch Engine contract

`PatchEngine.apply(book, patch)` validates the patch against the current
BookIR, clones the book, applies the operation, and records an applied patch
with `payload._audit` containing enough before-state for inspection and later
undo support. The input book is never mutated.

Supported operations in v0.1:

- `replace_content`
- `set_attribute`
- `insert_node`
- `delete_node`
- `move_node`
- `merge_nodes`
- `split_node`

Merge operations require contiguous siblings and preserve the union of all
source provenance. Move operations reject cycles. Insert operations reject id
collisions. Applied patch ids cannot be replayed accidentally.

### Milestone 4 — Additional parser adapters

Add MinerU and Marker first, then optionally Docling/PaddleOCR. Each backend must pass BookIR conformance tests.

### Milestone 5 — Human review UI

Reuse the existing React/FastAPI shell for source view, reconstructed book view, issue queue, source-aligned selection, patch review/undo, export, and quality reports.

## Legacy boundary

The current services/conversion/conversion_pipeline.py is a legacy converter pipeline and should not become the foundation of BookIR. It remains operational until the new pipeline reaches functional parity.

## Non-goals for v0.1

- training or maintaining an OCR model;
- replacing MinerU/Marker;
- perfect semantic reconstruction;
- frontend redesign;
- whole-book LLM rewriting;
- preserving PDF visual layout pixel-for-pixel.

The v0.1 success criterion is smaller: **a source document can be parsed into BookIR without losing provenance and compiled into a reflowable EPUB skeleton.**
