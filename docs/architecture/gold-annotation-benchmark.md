# Gold Annotation & Benchmark Intelligence

Milestone 14 extends the Milestone 13 real-world parser benchmark with sparse,
source-pinned reference annotations and accuracy metrics.

The design goal is to add real correctness signals without pretending that every
page or every structure type has been exhaustively annotated.

## Annotation lifecycle

Every gold file has a `status`:

- `draft`: seed/reference annotation. It may be evaluated and reported, but it
  cannot enforce regression gates.
- `reviewed`: a human reviewer has explicitly checked the annotation against
  the exact pinned PDF bytes. Only this state may enforce thresholds or
  baseline-regression gates.

A reviewed annotation must record `reviewed_by`. Moving an annotation from
`draft` to `reviewed` is therefore an explicit review action, not an automatic
side effect of running a parser.

## Source binding

Each annotation records both:

- `document_id`;
- `source_sha256`.

The evaluator also checks every annotated page against the corpus `page_count`.
If the PDF bytes change, the annotation is rejected before any metric is
computed. This prevents stale labels from silently evaluating a new revision of
the document.

## Sparse annotation schema

A document does not need to be fully annotated.

Each page declares the tasks that are actually covered:

```json
{
  "page_index": 8,
  "tasks": ["headings", "reading_order"],
  "elements": [
    {
      "id": "p8-h1",
      "type": "heading",
      "text": "1 Introduction",
      "level": 1
    }
  ],
  "reading_order": ["p8-h1"]
}
```

Supported tasks are:

- `text`
- `reading_order`
- `headings`
- `lists`
- `tables`
- `figures`
- `captions`
- `footnotes`
- `formulas`

If a task is not listed for a page, its metric is `null` / `NA`; it is never
implicitly scored as zero.

This is important for practical corpus growth. A reviewer can first annotate
only heading hierarchy on representative pages, later add tables, and later add
complete-page text without rewriting the existing annotation.

## Element representation

An element has:

- stable annotation-local `id`;
- semantic `type`, using BookIR node type names;
- optional normalized source `text`;
- optional PDF-coordinate `bbox`;
- optional heading `level`;
- optional task-specific `attrs`.

Text and bbox are both optional because some structures are best identified
spatially while others are best identified by text.

Element ids must be unique across the whole document. This makes
`reading_order` and review evidence unambiguous.

## Deterministic matching

The evaluator does not use an LLM or embedding model to align parser output with
gold.

For each annotated page it considers BookIR nodes whose provenance references
that page. Matching is deterministic:

1. page equality is mandatory;
2. for structural metrics, BookIR node type must match the annotated type;
3. normalized text similarity is based on token F1 and deterministic sequence
   similarity;
4. when both sides have bounding boxes, bbox IoU contributes a small spatial
   term;
5. candidates below the fixed acceptance threshold are discarded;
6. remaining candidates are greedily assigned in descending score order with
   stable gold-id/node-id tie breaking.

The report stores matched and unmatched evidence so a reviewer can inspect why a
score changed.

For reading-order evaluation, type equality is intentionally not required.
This allows a low-level parser such as PyMuPDF to receive reading-order credit
for correctly ordered text blocks even when it does not classify them as
headings.

## Accuracy metrics

### Text

Text metrics are calculated only on pages whose task list includes `text`.

The current evaluator reports:

- token precision;
- token recall;
- token F1;
- exact-page rate;
- mean normalized character-sequence similarity.

For a `text` page, the annotation is expected to represent the complete text
scope being evaluated. Do not mark `text` when only a few anchor phrases have
been transcribed.

### Reading order

For `reading_order`, the evaluator matches annotated elements to parser nodes
and evaluates every ordered pair.

It reports:

- pair accuracy;
- correct pair count;
- expected pair count;
- element match recall.

An unmatched element makes every order pair involving that element incorrect.
This prevents a parser from receiving perfect order accuracy after dropping
content.

### Structural precision / recall / F1

The following tasks receive explicit detection metrics:

- headings;
- list items;
- tables;
- figures;
- captions;
- footnotes;
- formulas.

Each metric is scoped only to pages that explicitly enable that task.

Heading evaluation additionally reports `level_accuracy` for matched headings
that have an annotated level.

## Proxy metrics versus gold metrics

Milestone 13 proxy metrics remain useful:

- relative text coverage;
- cross-backend text consensus;
- reading-order page monotonicity proxy;
- Quality Engine score;
- structural presence heuristics.

They answer engineering questions such as "did this backend suddenly emit much
less text?" or "do the parsers disagree strongly?".

Milestone 14 gold metrics answer a different question: "against a reviewed
reference for these specific pages/tasks, how accurate was this parser?".

The Markdown report therefore renders Gold Accuracy in a separate section.
Cross-backend agreement is never promoted into a correctness score.

## Thresholds and baselines

The corpus manifest can define per-backend gates:

```json
{
  "gold_thresholds": {
    "pymupdf": {
      "reading_order.pair_accuracy_min": 0.95
    }
  },
  "gold_baselines": {
    "pymupdf": {
      "text.f1": 0.98
    }
  },
  "gold_max_regression": {
    "pymupdf": {
      "text.f1": 0.01
    }
  }
}
```

Threshold names are dotted paths into `gold_metrics`. A trailing `_min` is
accepted for readability.

Baselines fail when the current value drops more than the corresponding
`gold_max_regression` allowance.

These gates are deliberately disabled for `draft` annotations. MinerU and
Marker remain optional dependencies; an unavailable backend is still reported
as `skipped`, not as an accuracy failure.

## CLI

Validate all linked annotations:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli gold-validate \
  --manifest benchmark/corpus/manifest.json
```

Evaluate an existing BookIR output without re-running its parser:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli gold-evaluate \
  artifacts/parser-benchmark/nist-eel-sp1500-101-v1/pymupdf/bookir.json \
  --manifest benchmark/corpus/manifest.json \
  --document nist-eel-sp1500-101-v1 \
  --backend pymupdf
```

Normal benchmark runs automatically evaluate gold when
`gold_annotations_path` is present.

## Authoring workflow

For a new annotation:

1. verify the corpus item first with the existing SHA-256 materialization flow;
2. create the annotation while looking at the pinned PDF revision;
3. annotate only tasks that are complete enough to score;
4. prefer representative difficult pages over broad but low-quality labeling;
5. use PDF page indexes starting at zero;
6. use short, stable element ids;
7. add bbox only when it materially helps matching;
8. run `gold-validate`;
9. run at least one parser and inspect `gold-evidence.json`;
10. keep the status `draft` until a separate human reviewer checks the labels;
11. after review, record `reviewed_by`, change status to `reviewed`, and only
    then add or tighten regression gates.

## Review checklist

A human reviewer should verify:

- the annotation points to the exact SHA-256 listed in the corpus manifest;
- page indexes correspond to the PDF, not printed page numbers;
- every enabled task is complete for the intended evaluation scope;
- text is not silently normalized in a way that changes meaning;
- heading levels represent hierarchy rather than visual font size alone;
- list items, captions, footnotes, formulas, figures, and tables are not
  double-counted;
- reading order reflects intended human reading order, especially on
  multi-column pages;
- matching evidence does not reveal a systematically ambiguous annotation.

## Initial seed annotation

`nist-eel-sp1500-101-v1` currently contains a sparse draft annotation for PDF
page index 8 covering heading detection/hierarchy and reading order.

It is intentionally still `draft`: it was created as a Milestone 14 seed and
must receive explicit human review before it becomes a regression gate.

This distinction is part of the benchmark's provenance model rather than a
documentation convention.
