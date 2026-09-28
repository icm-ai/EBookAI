# Real-world Corpus & Multi-backend Parser Benchmark

Milestone 13 adds a second regression surface beside the synthetic golden corpus:

- **synthetic golden corpus**: deterministic fixtures with explicit semantic expectations;
- **real-world parser corpus**: rights-cleared PDFs used to compare parser behavior under the same bytes and runtime contract.

The real-world suite is intentionally parser-level. It does not compile EPUBs and it does
not treat one parser, majority agreement, or the longest extracted text as ground truth.

## Rights-cleared corpus policy

Every document in `benchmark/corpus/manifest.json` must record:

- canonical source URL;
- license/rights URL;
- a human-readable `rights_basis`;
- SHA-256 of the exact PDF bytes;
- document class, language, page count, and complexity tags;
- expected parser capabilities exercised by the document;
- whether EBookAI asserts that the exact bytes are redistributable;
- an optional future gold-annotation path.

A document may be checked into the repository only when
`redistributable=true` and the rights basis explicitly supports redistribution.
Otherwise the manifest is download-only and the fetched bytes stay in the local cache.

Do not add PDFs merely because they are publicly downloadable. Public availability alone
is not treated as redistribution permission.

## Initial corpus

| ID | Class | Pages | Materialization | Why it is useful |
|---|---|---:|---|---|
| `nist-ballot-definition-prototype` | technical prototype | 1 | checked-in base64, decoded to the original PDF for CI | Real form-like/vector PDF; small enough for deterministic offline smoke tests |
| `nist-eel-sp1500-101-v1` | technical standard | 32 | download + SHA-256 verification | Long hierarchical technical document with TOC, figures/UML diagrams, appendices, and dense text |

The NIST Ballot Definition repository carries a NIST notice that explicitly permits use,
copy, distribution, modification, and redistribution of NIST-developed material. The
small prototype PDF is therefore used as the offline CI sample.

The NIST SP 1500-101 item is deliberately **not vendored**. It is an official NIST
publication distributed from a public NIST repository, but this corpus keeps it
download-only rather than making a broader redistribution assertion for possible
third-party contributions.

## CLI

All commands use only the standard library plus the parser dependencies already selected
for the run.

### Fetch corpus

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli fetch \
  --manifest benchmark/corpus/manifest.json \
  --cache .cache/ebookai/corpus
```

Fetch only the offline NIST smoke sample:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli fetch \
  --documents nist-ballot-definition-prototype
```

### Verify pinned bytes

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli verify \
  --manifest benchmark/corpus/manifest.json
```

Any SHA-256 mismatch is a hard failure. A corrupted cached file is never silently accepted.

### Run all parser backends

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli run \
  --manifest benchmark/corpus/manifest.json \
  --cache .cache/ebookai/corpus \
  --backends pymupdf,mineru,marker \
  --timeout 300 \
  --output artifacts/parser-benchmark
```

Each backend receives an isolated copy of the same verified PDF. It runs in a separate
process with an isolated working/temp directory. The runner records:

- backend availability and version;
- success / skipped / failed / timeout;
- elapsed time;
- normalized BookIR output;
- warnings and errors;
- parser-level metrics and Quality Engine results.

If MinerU or Marker is not installed, that backend is `skipped`; it is not considered a
parser failure. Neither dependency is part of the default EBookAI install.

### Render a Markdown report

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli report \
  artifacts/parser-benchmark/benchmark-results.json \
  --output artifacts/parser-benchmark/report.md
```

## Metrics

### Direct engineering measurements

These measurements do not require manual ground truth:

- parser success / skip / failure / timeout;
- elapsed wall time;
- node count and BookIR node-type counts;
- normalized text character/token counts;
- pages with recovered content and manifest-relative page coverage;
- provenance coverage;
- bounding-box coverage;
- mean parser confidence axes;
- Quality Engine score, issue counts, and issue codes;
- recovery presence for expected structural features such as headings, tables,
  figures, formulas, and footnotes.

### Ground-truth-free proxies

The report labels the following explicitly as proxies:

- **reading-order proxy**: fraction of adjacent content nodes whose first source page
  index is nondecreasing;
- **relative text coverage**: extracted normalized text length divided by the largest
  successful backend result for that document;
- **text consensus Jaccard**: token-set agreement with the other successful parsers.

These are useful for differential testing but are not correctness scores. A parser can
agree with another parser and still be wrong; a longer extraction can include duplicated
headers, footers, or noise.

## Gold annotations

Milestone 14 now uses `gold_annotations_path` for sparse, source-pinned reference
annotations. Gold metrics are computed only for explicitly annotated pages/tasks and are
rendered separately from the ground-truth-free proxies above.

Annotations have a `draft` / `reviewed` lifecycle. Only reviewed annotations may
enforce absolute thresholds or baseline-regression gates. Matching is deterministic and
produces matched/unmatched evidence for audit.

See
[`gold-annotation-benchmark.md`](gold-annotation-benchmark.md)
for schema details, accuracy metrics, CLI usage, authoring workflow, and review policy.

## Adding a document

Before adding a new corpus entry:

1. confirm the source is a real PDF, not a generated fixture;
2. record a stable canonical source;
3. record the precise rights/license basis;
4. decide whether redistribution is actually permitted;
5. download the exact bytes and pin SHA-256;
6. record page count and factual complexity tags;
7. only vendor the bytes when redistribution is explicitly supported;
8. run at least PyMuPDF locally and inspect the generated BookIR;
9. if MinerU/Marker are available, run the same manifest item through all three;
10. do not add threshold gates that implicitly treat a proxy as ground truth.

## Optional parser installation

EBookAI deliberately does not make MinerU or Marker mandatory dependencies. Install them
in an isolated environment according to their upstream installation instructions, then
rerun the same benchmark command. Availability is discovered at runtime by the existing
parser adapters.

The benchmark layer calls only the EBookAI `BookParserAdapter` contract, so backend-specific
output remains normalized through BookIR rather than being compared as raw Markdown.
