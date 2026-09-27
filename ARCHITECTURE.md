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
    ├── orchestration/
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

**Paragraph merging** also promotes remaining parser-level `TEXT_BLOCK` nodes
to body paragraphs after headings and footnotes have had a chance to claim
them. That promotion raises structure confidence conservatively to 0.70 rather
than leaving native-PDF blocks permanently at parser-level confidence. This
allows simple digital PDFs to finish on the lightweight path while still
routing genuinely low-confidence structure to a semantic parser.

Cross-page paragraph merging currently targets high-confidence adjacent-page
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
book. The default detectors currently cover empty parser results, missing
provenance, low confidence, raw text blocks that remain after reconstruction,
empty semantic nodes, orphan footnotes, and heading hierarchy errors.

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

### Milestone 4 — Parser backend adapters

- [x] Explicit parser capability model.
- [x] Parser profiles expose format support, optional-runtime availability, and semantic capabilities.
- [x] Capability-aware parser registry without automatic routing policy.
- [x] MinerU 4.x adapter using the public Python SDK lazily.
- [x] MinerU Structured Content -> BookIR normalization.
- [x] Marker adapter using the public Python converter surface lazily.
- [x] Marker JSON Page/Block tree -> BookIR normalization.
- [x] Deterministic EBookAI node identities independent of backend block ids.
- [x] Preserve backend block type/id/HTML or structured metadata as attributes.
- [x] Preserve page and bbox provenance for MinerU and Marker.
- [x] Conformance tests shared across optional parser backends.
- [x] Optional parser packages remain outside EBookAI's base requirements.

#### Capability contract

Each adapter declares `ParserCapabilities` rather than relying on hard-coded
backend names. Current capability dimensions include native text, OCR, layout,
reading order, headings, footnotes, tables, formulas, images, bbox,
multi-column support, semantic output, and named quality modes.

`ParserRegistry.candidates(...)` can filter by file extension and required
features, but Milestone 4 intentionally does **not** choose a winner. Routing
policy belongs above the adapter layer so later quality-aware scheduling can
consider cost, hardware, prior quality reports, and fallback state.

#### MinerU contract

`MinerUAdapter.parse()` lazily imports the MinerU 4.x public SDK and calls the
document parser, then consumes `ParseResult.structured_content()`. The adapter
does not depend on temporary CLI artifact naming or backend-specific model
output. Structured Content page/block semantics are mapped into BookIR while
preserving source page/bbox and relevant attributes such as heading level,
anchor, image source, captions, and footnotes.

#### Marker contract

`MarkerAdapter.parse()` lazily imports Marker and requests JSON renderer
output through its public converter/configuration surface. Page and semantic
block trees are normalized into BookIR. Marker polygons are converted to
BookIR bounding boxes; Marker block ids are retained only as backend metadata,
while EBookAI generates deterministic canonical node ids.

MinerU and Marker are optional integrations. EBookAI does not install their
model stacks or weights as base dependencies. This keeps the core lightweight
and avoids coupling BookIR to backend-specific runtime/licensing constraints.

#### Conformance invariant

For any parser adapter output used by EBookAI:

- BookIR schema must be valid.
- canonical node ids must be unique and deterministic for stable input.
- content-bearing semantic nodes must retain at least one `SourceRef`.
- every source reference identifies the parser and source document.
- backend-specific ids and payload details may be retained in `attrs`, but
  downstream reconstruction/quality/compiler layers must not require them.

### Milestone 5 — Quality-aware Parser Orchestrator

- [x] Separate quality acceptance from parser selection.
- [x] Configurable `QualityGate` using score, error count, review burden, and blocking issue codes.
- [x] Issue-driven `EscalationPolicy` maps quality failures to parser capabilities.
- [x] Low extraction confidence escalates toward OCR-capable parsers.
- [x] Low structure confidence escalates toward layout + semantic parsers.
- [x] Low reading-order confidence escalates toward layout + reading-order capability.
- [x] Configurable parser priority keeps cost/order policy above adapters.
- [x] Runtime-unavailable backends are skipped and audited without consuming parse budget.
- [x] Known backend failures fall through to the next candidate.
- [x] Explicit user/task-required capabilities filter candidates before the first parse.
- [x] Every successful parse runs deterministic reconstruction and Quality Engine analysis.
- [x] Accepted results stop early; rejected results can trigger stronger capability requirements.
- [x] Exhausted routes return the best available rejected BookIR for human review rather than discarding work.
- [x] Final BookIR stores the orchestration policy, attempt trail, final quality report, and stop reason.
- [x] Focused CI covers success, escalation, unavailable runtimes, backend failure, capability filtering, exhaustion, and no-candidate paths.

#### Quality gate

The gate is deliberately independent from backend names. The default acceptance
contract currently requires:

- quality score >= 0.97;
- zero error-severity issues;
- review+error burden <= 5% of BookIR nodes;
- no `empty_document` or `missing_provenance` issue.

These numbers are policy defaults, not claims that the heuristic score is a
probability of correctness. Applications can provide a different
`QualityGate` without changing parser code.

#### Issue-driven escalation

Quality issues are translated into **required capabilities**, not concrete
backend names. Examples:

    empty document            -> ocr
    low extraction confidence -> ocr
    low structure confidence  -> layout + semantic_output
    low reading order         -> layout + reading_order
    unclassified text block   -> layout + semantic_output
    orphan footnote           -> footnotes
    heading hierarchy         -> headings

A zero-node parse is therefore never interpreted as a perfect parse: it emits
an `empty_document` error and explicitly requests an OCR-capable next hop.

The registry then filters the remaining untried parsers by those capabilities.
The default parser priority is `pymupdf -> mineru -> marker`, but this ordering
is isolated in `OrchestratorPolicy` and can be replaced for different
hardware, cost, privacy, or deployment constraints.

#### Attempt and fallback semantics

Unavailable optional runtimes are recorded as `unavailable` and skipped.
A known `ParserBackendError` is recorded as `failed` and allows fallback.
A parsed result that fails the quality gate is recorded as `rejected` with
its score, issue counts, issue codes, gate reason, and the capability snapshot
that led to that attempt.

The orchestrator does not silently discard rejected work. If all candidates are
exhausted or the maximum parse-attempt budget is reached, it returns the best
rejected BookIR by the same heuristic report ordering and marks the result
`accepted=false`. That document can enter a later human-review queue.

The final selected BookIR records the complete attempt trail under
`metadata.extra.orchestration` and stores the final QualityReport under
`metadata.extra.quality.report`.

### Milestone 6 — Human review UI

- [x] Disk-backed review sessions preserve source PDF, BookIR, QualityReport, and decisions.
- [x] The frontend remembers the latest review session id and restores it after refresh.
- [x] Review upload runs the quality-aware parser orchestrator instead of the legacy converter.
- [x] Source PDF endpoint supports browser-native page navigation.
- [x] Review session response exposes BookIR nodes, provenance, quality issues, and orchestration attempts.
- [x] Accepting a suggested patch uses PatchEngine and immediately re-runs Quality Engine analysis.
- [x] Rejecting an issue preserves BookIR and records an auditable human decision.
- [x] Human decisions are embedded under `metadata.extra.review` so BookIR exports remain self-describing.
- [x] BookIR JSON and EPUB export endpoints publish the current reviewed state.
- [x] React review workspace provides source, reconstructed BookIR, issue queue, provenance, and orchestration trail.
- [x] Selecting an issue or BookIR node navigates the source PDF to the relevant page and shows bbox coordinates.
- [x] Focused tests cover persistent sessions, patch acceptance, quality re-analysis, and rejection audit.

#### Review session contract

A review session is persisted under a UUID-scoped directory and contains the
source PDF plus an atomically written `session.json`. Browser refreshes do not
discard decisions. The source filename is retained for display/export while the
canonical source hash/provenance remains in BookIR.

Patch acceptance is intentionally not a frontend mutation:

    issue.suggested_patch
      -> PatchEngine.apply()
      -> new BookIR
      -> QualityEngine.analyze()
      -> persist session

Rejection records the complete issue snapshot, optional reason, patch id when
present, and timestamp without changing BookIR content.

#### Source alignment

The v0.1 review UI uses the browser's native PDF viewer rather than introducing
a PDF.js dependency. Provenance selection navigates to the 1-based PDF page via
the viewer fragment and displays the exact BookIR bbox alongside the selected
node/issue. Pixel-level bbox overlays are deferred to a later UI iteration.

#### Export boundary

The review API can export the current reviewed BookIR JSON directly and compile
that same BookIR through the dependency-light EPUB compiler. Review decisions
and applied patch history therefore travel with the auditable JSON artifact,
while EPUB remains a publication output.

### Milestone 7 — Source-grounded AI repair proposals

- [x] Provider-neutral AI proposal model and validator under `book/repair`.
- [x] Grounding context includes the current quality issue, target node, bounded
  neighboring BookIR nodes, confidence, and full source page/bbox/parser/source-id
  provenance.
- [x] Grounding context is SHA-256 hashed and the hash is stored with every
  proposal for audit.
- [x] Model output is untrusted JSON and must pass BookIR-aware validation before
  it can enter a review session.
- [x] AI operations are deliberately allowlisted to `replace_content` and
  `set_attribute`; the latter may only change heading `level` in v0.1.
- [x] Invented node ids, invented source ids, out-of-scope targets, malformed
  payloads, no-op replacements, oversized replacements, and unsupported
  operations are rejected.
- [x] Book-level issues without source-grounded target nodes cannot request AI
  repair.
- [x] AI proposals are persisted with provider, model, rationale, confidence,
  cited evidence, patch, status, and timestamps.
- [x] Proposal lifecycle is explicit: `pending -> accepted|rejected`; accepting
  one proposal supersedes other pending proposals for the same issue.
- [x] Acceptance still goes through `PatchEngine`, followed by a fresh
  `QualityEngine` analysis; generation alone never mutates canonical BookIR.
- [x] Optional vision grounding renders issue-target PDF bbox regions as
  transient PNG crops.
- [x] Source crop bytes are sent only for the current provider request and are
  not persisted in `session.json`; only auditable source-image reference labels
  are retained.
- [x] OpenAI-compatible and Anthropic transports support the same source-image
  evidence envelope.
- [x] Human Review UI exposes configured providers, an explicit source-crop
  toggle, proposal evidence/confidence/patch, accept/reject controls, and
  proposal history.
- [x] Focused CI covers grounding validation, hallucinated provenance rejection,
  operation restrictions, proposal persistence/review lifecycle, PDF crop
  rendering, and vision audit metadata.

#### Grounding contract

AI repair is a constrained transformation proposal, not a second parser and not
a whole-book rewriting stage:

    QualityIssue
      + target BookIR node
      + bounded BookIR neighbors
      + SourceRef(page, bbox, parser, source_id)
      + optional rendered source crop
        -> provider model
        -> untrusted JSON
        -> AIRepairProposalGenerator
        -> PatchValidator
        -> pending AIRepairProposal
        -> Human Review
        -> PatchEngine
        -> QualityEngine

Text-only proposals can reason over the extracted BookIR context and its exact
provenance metadata. They must not be described as having visually inspected
the PDF. When the reviewer explicitly enables source-crop grounding, EBookAI
renders up to three bbox-aligned PNG crops and sends them through a
vision-capable provider transport. The persisted proposal records
`input_mode=text|vision` and the source-image reference labels used for that
request.

The first AI repair allowlist is intentionally narrow. `replace_content`
supports source-grounded OCR/text correction. `set_attribute` is restricted
to heading `level` so model output cannot arbitrarily rewrite internal BookIR
attributes. Structural operations such as merge, split, move, insert, and
delete remain deterministic/human-controlled until stronger multi-node
grounding and validation rules are defined.

#### Proposal persistence and review

A generated proposal is stored alongside the review session but does not enter
`Book.patches` until a human accepts it. Rejection changes only proposal
status. Acceptance validates the patch against the current BookIR again, applies
it through the normal Patch Engine, re-runs quality analysis, records the human
decision, and marks competing pending proposals for the same issue as
`superseded`.

This separation preserves the core invariant:

    model output != canonical BookIR mutation

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
