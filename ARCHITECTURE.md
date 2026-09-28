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

### Milestone 8 — Reversible review and publication QA

- [x] Applied patches record an explicit `undone` state without deleting their audit history.
- [x] PatchEngine derives structured before/after diff views from `payload._audit`.
- [x] All seven BookIR patch operations are reversible from recorded before-state.
- [x] Undo is deliberately LIFO-only: only the latest active applied patch can be reversed.
- [x] Undo never reconstructs prior state heuristically; it restores recorded content,
  attributes, node snapshots, parent/index positions, merged siblings, or split source nodes.
- [x] Undo re-runs Quality Engine and persists the resulting review state.
- [x] Accepted AI proposals whose patch is undone are marked `undone`.
- [x] Review sessions derive issue resolution states: `open`, `resolved`, `waived`,
  and `reopened`.
- [x] Human Review UI exposes patch history, before/after diff, reversible state,
  and a guarded Undo control.
- [x] Publication QA combines current QualityReport, human resolution state, and the
  actually compiled EPUB package.
- [x] Error-severity quality findings always block release, even when a reviewer
  rejected/waived the corresponding issue.
- [x] Review-severity findings block release until resolved or explicitly waived.
- [x] Publication QA validates EPUB mimetype ordering/compression/value, required
  files, container rootfile, XML well-formedness, manifest resources, and spine idrefs.
- [x] Publication reports persist in the review session and are invalidated by any
  subsequent review mutation.
- [x] Human Review UI shows release-ready/blocked status and detailed publication findings.

#### Reversible patch contract

Patch history is append-preserving. Undo changes the current BookIR state but does
not erase the original applied patch or its before-state audit. Instead the patch
remains historically applied and is marked `undone=true`.

Milestone 8 intentionally supports only stack-safe undo:

    active patch A
      -> active patch B
      -> active patch C

    allowed: undo C
    then:    undo B
    then:    undo A

Attempting to undo A while B or C is still active is rejected. This prevents an
older structural rollback from invalidating later patches that may depend on its
node ids, hierarchy, or content.

Undo restoration uses operation-specific audit data:

    replace_content -> before_content
    set_attribute   -> before_value + attribute_existed
    insert_node     -> inserted_node_id
    delete_node     -> before_node + parent_id + index
    move_node       -> before_parent_id + before_index
    merge_nodes     -> before_nodes
    split_node      -> before_node + created_node_ids

After every undo, Quality Engine runs again. Historical human decisions are not
deleted; the derived issue-resolution view can therefore show a previously fixed
issue as `reopened`.

#### Issue resolution contract

Resolution is derived from current QualityReport plus immutable review decisions
and patch state rather than stored as an independent source of truth.

- `open`: issue currently exists and has not been successfully cleared.
- `resolved`: an accepted issue no longer exists in the current QualityReport.
- `waived`: reviewer explicitly rejected the proposed repair while retaining the issue.
- `reopened`: the accepted patch was undone and the issue is present again.

A waived state is a human review decision, not proof that the underlying document
is valid.

#### Publication QA contract

Publication QA compiles the current reviewed BookIR through `EpubCompiler` and
validates that exact artifact. Release readiness is then evaluated using both
semantic review state and EPUB package structure.

The default release policy is conservative:

    current ERROR issue   -> always blocks
    current REVIEW issue  -> blocks unless explicitly waived
    INFO issue            -> informational
    structural EPUB error -> blocks

The built-in EPUB validator is dependency-light structural QA. It verifies core
ZIP/XML/package invariants but is not presented as a substitute for the complete
external EPUBCheck conformance suite. A future release pipeline may run EPUBCheck
as an additional gate when the Java/runtime dependency is available.

### Milestone 9 — Release Pipeline and external EPUBCheck

- [x] EPUB compilation is deterministic when no explicit identifier is supplied.
- [x] Generated EPUB ZIP entries use fixed metadata timestamps and permissions so
  identical BookIR produces byte-identical EPUB output.
- [x] External EPUBCheck is integrated as an optional process-level validator
  without adding Java or EPUBCheck to EBookAI's base runtime dependencies.
- [x] EPUBCheck discovery supports an explicit command, a PATH executable, or
  `EPUBCHECK_JAR` plus Java.
- [x] External validation consumes EPUBCheck JSON output rather than parsing
  human-readable stderr.
- [x] External validation records a stable normalized result: availability,
  execution state, pass/fail, version, counts, messages, and source locations.
- [x] Release policy can require EPUBCheck; unavailable required validation blocks
  release instead of silently degrading.
- [x] If EPUBCheck is available and reports errors, release is blocked even when
  external validation was configured as optional.
- [x] Release bundles include the source document, BookIR JSON, compiled EPUB,
  Publication QA report, normalized EPUBCheck report, and release manifest.
- [x] Every release artifact is bound by SHA-256, byte size, and media type.
- [x] `release_id` is deterministically derived from artifact hashes and release
  policy rather than timestamps or random identifiers.
- [x] Release bundle ZIP entries use deterministic metadata and stored bytes so
  identical release state produces byte-identical bundles.
- [x] Bundles can be independently verified without re-running parsers or AI:
  verifier checks every artifact size/hash and recomputes the release id.
- [x] Review sessions persist the latest release manifest and invalidate/remove it
  after any review mutation or a new standalone Publication QA run.
- [x] Review API exposes release build, release bundle verification, and ZIP export.
- [x] Human Review UI separates Publication QA from Release state and exposes
  release policy, release id, external EPUBCheck status/version, artifact hashes,
  bundle verification, and release ZIP download.
- [x] CI has a lightweight focused release suite plus a separate real EPUBCheck
  integration gate pinned to EPUBCheck 5.4.0.

#### Reproducibility contract

A release is a content-addressed snapshot, not merely a downloadable EPUB.

The EPUB compiler therefore avoids runtime entropy. When BookIR has no explicit
publication identifier, EBookAI derives a stable UUID from semantic publication
content. ZIP entry timestamps and permission bits are fixed. For the same
publication state, the compiler must emit the same EPUB bytes.

The release pipeline then snapshots:

    source/source.<ext>
    book/bookir.json
    publication/book.epub
    reports/publication-qa.json
    reports/epubcheck.json
    manifest.json

The first five files are represented as `ReleaseArtifact` records containing
their path, SHA-256 digest, byte size, and media type. `manifest.json` binds
those records to the release policy and derives:

    release_id = sha256(
      artifact descriptors
      + require_epubcheck policy
      + release readiness
      + EPUBCheck status
    )

No wall-clock timestamp participates in release identity.

#### External EPUBCheck contract

EPUBCheck remains an external conformance tool. EBookAI does not vendor its Java
runtime or libraries into the Python core.

Runtime discovery order is:

    explicit runner command
      -> EPUBCHECK_COMMAND
      -> epubcheck executable on PATH
      -> EPUBCHECK_JAR + java
      -> unavailable

The runner invokes EPUBCheck with a JSON report and normalizes stable data only.
Runtime paths, elapsed times, and checker wall-clock timestamps are deliberately
excluded from the persisted normalized report because they would make otherwise
identical releases non-reproducible.

Release readiness policy is:

    built-in Publication QA fails
      -> blocked

    EPUBCheck available + passes
      -> external gate satisfied

    EPUBCheck available + fails/errors
      -> blocked

    EPUBCheck unavailable + optional
      -> allowed, manifest records unavailable

    EPUBCheck unavailable + required
      -> blocked

The current CI integration pins EPUBCheck 5.4.0. The application runner itself
does not hard-code a version and records the actual checker version returned by
the external tool.

#### Independent verification contract

Bundle verification does not trust the session database and does not need the
source parser, reconstruction engine, AI provider, or EPUBCheck runtime.

The verifier opens the ZIP, reads `manifest.json`, verifies every declared
artifact's byte size and SHA-256 digest, then recomputes `release_id`. Any
missing or modified artifact fails verification.

This verifies release integrity and provenance binding. It does not re-prove the
semantic correctness of the source reconstruction; that evidence remains in the
BookIR, review history, QA report, and external conformance report.

### Milestone 10 — Signed Provenance and Release Attestation

- [x] Release bundles include integrity-protected deterministic toolchain
  provenance under `provenance/toolchain.json`.
- [x] Provenance records runtime/package versions, parser route, BookIR/
  reconstruction identity, AI repair provider/model metadata, compiler identity,
  EPUBCheck status/version, and optional build revision.
- [x] Secret material, signing commands, private keys, tokens, runtime paths, and
  timestamps are excluded from provenance and release identity.
- [x] External detached signing is optional and policy-controlled.
- [x] Required signing fails closed when no signer/key id is configured.
- [x] A configured signer failure aborts release creation instead of silently
  degrading to unsigned output.
- [x] `attestation.json` signs the exact canonical `manifest.json` bytes and
  remains outside the manifest artifact hash list to avoid circular signing.
- [x] Manifest schema v0.2 declares signed/unsigned state, public key id,
  algorithm, and `require_signature` policy.
- [x] External verification supports command templates with `{payload}` and
  `{signature}` placeholders for OpenSSL/GPG/SSH/KMS-style integrations.
- [x] Verification distinguishes integrity, cryptographic validity, and trust.
- [x] Trusted signer policy uses an explicit non-secret key-id allowlist.
- [x] A release requiring signatures cannot verify successfully without an
  available cryptographic verifier.
- [x] Review API and UI expose signature policy, signing identity, algorithm,
  cryptographic verification, and trust state.
- [x] Focused tests prove signing command/private material is not persisted.
- [x] CI exercises a real ephemeral Ed25519 detached signature through OpenSSL.
- [x] Sigstore is documented as a future native adapter rather than falsely
  claiming Rekor/Fulcio semantics through the generic signature envelope.

#### Trust model

Milestone 9 answers:

    Do these bundle bytes match the declared release?

Milestone 10 additionally answers:

    Was this exact manifest cryptographically authorized?
    Do I trust the identity that authorized it?

These are independent checks. Artifact hashes and `release_id` establish
content integrity. The detached signature establishes cryptographic
authenticity. Local trust policy decides whether the public `key_id` is an
accepted signer.

A valid signature from an untrusted key is therefore reported as
cryptographically valid but not trusted.

#### Detached signing boundary

The signed payload is the exact canonical byte representation of
`manifest.json`. The signature envelope is stored separately:

    manifest.json
         │
         ├── SHA-256 payload binding
         │
         ▼
    attestation.json
         ├── algorithm
         ├── key_id
         ├── signature
         └── payload_sha256

The private key never enters EBookAI's persisted domain model.

This boundary allows signing to be delegated to operating-system key stores,
HSMs, KMS wrappers, OpenSSL, GPG, SSH signing, or future dedicated signing
adapters without coupling BookIR to a cryptographic provider.

#### Provenance boundary

`provenance/toolchain.json` is itself a normal release artifact and is covered
by `release_id`. It describes how the release was produced without trying to
capture secrets or unstable machine-local state.

The optional `EBOOKAI_BUILD_REVISION` allows deployment pipelines to bind a
release to a source revision without requiring the application to shell out to
Git at runtime.

See `docs/architecture/release-attestation.md` for configuration and verifier
semantics.

### Milestone 11 — Standalone Release Verifier and Native Sigstore

- [x] Release verification is exposed as a reusable standalone library that does
  not depend on FastAPI, review-session persistence, parser execution, or AI
  providers.
- [x] A portable `ebookai-verify` CLI entry module validates release ZIPs and
  returns process exit status suitable for CI/CD policy gates.
- [x] CLI supports JSON output, required-signature policy, generic trusted key
  ids, external verifier commands, native Cosign configuration, key-based
  Sigstore verification, keyless certificate identity/OIDC issuer constraints,
  regular-expression identity policy, and custom Sigstore TrustedRoot files.
- [x] Native Sigstore signing uses `cosign sign-blob --bundle` on the exact
  canonical `manifest.json`.
- [x] Native Sigstore bundles are preserved byte-for-byte at
  `sigstore/manifest.sigstore.json`; certificate/public-key material,
  timestamps, and transparency-log evidence are not flattened into the generic
  M10 attestation envelope.
- [x] Manifest schema v0.3 binds `signature_provider` into release identity,
  distinguishing `none`, generic `external`, and native `sigstore`.
- [x] Sigstore keyless signing is explicit rather than triggered merely because
  Cosign exists on PATH.
- [x] Keyless verification fails closed without an expected certificate identity
  and OIDC issuer policy.
- [x] Native Sigstore verification normalizes verdict/evidence for the UI while
  retaining the untouched native bundle as the authoritative evidence.
- [x] Evidence summary reports bundle media type, verification-material class,
  transparency-log entry count, RFC3161 timestamp count, verification mode,
  expected identity/issuer, and Cosign version.
- [x] Server-side verification and standalone CLI use the same release verifier
  semantics.
- [x] M9 manifest v0.1 and M10 manifest v0.2 release-id formulas remain
  verifiable; M11 does not force historical releases to be republished.
- [x] Human Review UI allows selecting external / Sigstore / none signature
  providers and surfaces provider, identity, issuer, and transparency-log
  evidence in verification results.
- [x] Focused tests cover native bundle preservation, keyless identity-policy
  fail-closed behavior, standalone CLI parity, and historical manifest
  compatibility.
- [x] A dedicated Native Sigstore Release Gate pins Cosign 3.1.3 and performs
  real local-key `sign-blob --bundle` plus `verify-blob --bundle`.
- [x] CI does not perform public keyless signing on every pull request, avoiding
  unnecessary public transparency-log entries while the adapter still supports
  ambient OIDC keyless operation.

#### Portable verification contract

A release verifier receives only:

    release-bundle.zip
    + local trust policy

It must not require the original review session, source parser, reconstruction
pipeline, AI provider, publication server, or database.

The verification order is:

    ZIP + manifest parse
      -> artifact size / SHA-256
      -> schema-specific release_id
      -> signature provider dispatch
           none
           external detached signature
           native Sigstore bundle
      -> cryptographic verification
      -> identity/key trust policy
      -> final verdict

The CLI uses exit code 0 only for a valid release under the supplied policy.

#### Native Sigstore boundary

Sigstore is not represented as a generic base64 signature. The native bundle is
the verification artifact:

    manifest.json
         │
         └── cosign sign-blob --bundle
                   │
                   ▼
    sigstore/manifest.sigstore.json

For keyless flows the verifier requires both expected certificate identity and
OIDC issuer (or explicit regexp variants). Cosign then verifies the signed
manifest, Fulcio certificate semantics, signed timestamp, and transparency-log
proof carried by the bundle according to Sigstore's own verification rules.

For key/KMS flows the verifier uses the configured public key/KMS reference and
still consumes the native bundle.

See `docs/architecture/standalone-verifier-sigstore.md`.

### Milestone 12 — Golden Corpus and End-to-End Regression Harness

- [x] Add a reusable `book.regression` package for corpus specifications,
  metrics, evaluation, and render-oriented evidence.
- [x] Define JSON per-case expectations and threshold policy instead of relying
  on ad-hoc assertions.
- [x] Bootstrap a deterministic rights-safe synthetic corpus covering digital,
  scanned/image-only, multi-column, table-like, and footnote-heavy sources.
- [x] Execute the real PyMuPDF adapter, deterministic reconstruction pipeline,
  Quality Engine, EPUB compiler, Publication QA, and optional external
  EPUBCheck for corpus cases.
- [x] Measure BookIR semantic expectation score, text recall, reading-order
  conformance, provenance coverage, bbox coverage, EPUB text recall, quality
  findings, publication readiness, and EPUB byte reproducibility.
- [x] Record deterministic XHTML/DOM, text-flow, stylesheet, and section-count
  render evidence for every generated EPUB.
- [x] Model current OCR/table/multi-column limitations as explicit `known_gaps`
  rather than silently relaxing failures.
- [x] Require the scanned/image-only fixture to surface `empty_document` and
  remain publication-blocked on the lightweight parser path.
- [x] Require the table fixture to preserve text/provenance/publication
  correctness while explicitly tracking missing table semantics.
- [x] Add a dedicated Golden Corpus Regression Gate with EPUBCheck 5.4.0.
- [x] Upload the complete regression report and per-case evidence even on gate
  failure for post-mortem comparison.
- [x] Keep metric semantics explicit: scores are regression/expectation
  conformance, not claims of universal reconstruction accuracy.

#### Regression philosophy

A green golden test means:

    this pipeline still satisfies the explicit expectations
    for this declared fixture and threshold set

It does not mean:

    arbitrary PDFs are reconstructed with the same percentage accuracy

Golden thresholds are versioned product contracts. Improvements should tighten
expectations and remove known gaps in the same change that improves the
pipeline.

#### Initial corpus

    digital-basic
      -> headings, paragraphs, repeated header/footer suppression,
         cross-page paragraph continuity, provenance, EPUB

    footnote
      -> footnote classification + same-page reference association

    multi-column
      -> text recovery + reading-order baseline + provenance
         known gap: semantic column grouping

    table-like
      -> cell text recovery + reading-order baseline + provenance
         known gap: semantic TABLE reconstruction

    scanned-image
      -> image-only source must not be falsely accepted
         expected gap: OCR required / empty_document

#### Render evidence boundary

Milestone 12 captures deterministic render-tree evidence from EPUB XHTML and
CSS. This is useful for stable CI comparison without tying the core suite to a
specific browser/font rasterizer.

Pixel-level screenshots can be added later as a renderer-versioned evidence
layer; they should not replace semantic/provenance regression metrics.

See `docs/architecture/golden-corpus.md`.

## Legacy boundary

The current services/conversion/conversion_pipeline.py is a legacy converter pipeline and should not become the foundation of BookIR. It remains operational until the new pipeline reaches functional parity.

## Non-goals for v0.1

- training or maintaining an OCR model;
- replacing MinerU/Marker;
- perfect semantic reconstruction;
- frontend redesign;
- whole-book LLM rewriting;
- preserving PDF visual layout pixel-for-pixel.

The v0.1 success criterion is now end-to-end: **a source document can be reconstructed into source-grounded BookIR, reviewed through reversible patches, compiled into a conformant reflowable EPUB, and packaged as a content-addressed release bundle whose integrity can be independently verified.**
