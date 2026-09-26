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

Implement deterministic passes for cross-page paragraph joining, repeated header/footer removal, heading hierarchy reconstruction, and footnote association.

### Milestone 3 — Quality and patch engine

Add node-level issue detectors, confidence recalculation, patch schema validation, deterministic patch application, and a quality report.

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
