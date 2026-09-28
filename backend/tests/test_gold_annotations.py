import json
from pathlib import Path

import pytest
from book.benchmark import (
    BackendRunResult,
    BenchmarkReport,
    CorpusManifest,
    GoldAnnotation,
    GoldValidationError,
    evaluate_gold,
    evaluate_gold_gate,
    load_gold_annotation,
    validate_gold_against_spec,
)
from book.benchmark.models import CorpusDocumentSpec
from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)

ROOT = Path(__file__).resolve().parents[2]
REAL_MANIFEST = ROOT / "benchmark" / "corpus" / "manifest.json"


def _source(page: int, parser: str = "fixture") -> SourceRef:
    return SourceRef(
        page_index=page,
        bbox=(10.0, 10.0, 200.0, 40.0),
        parser=parser,
        source_id="source",
    )


def _annotation(status: str = "reviewed") -> GoldAnnotation:
    reviewed_by = "Human Reviewer" if status == "reviewed" else ""
    return GoldAnnotation.from_dict(
        {
            "schema_version": "1",
            "document_id": "fixture",
            "source_sha256": "a" * 64,
            "status": status,
            "annotated_by": "Annotator",
            "reviewed_by": reviewed_by,
            "pages": [
                {
                    "page_index": 0,
                    "tasks": ["text", "reading_order", "headings"],
                    "elements": [
                        {
                            "id": "h1",
                            "type": "heading",
                            "text": "Heading",
                            "level": 1,
                        },
                        {
                            "id": "p1",
                            "type": "paragraph",
                            "text": "Alpha beta",
                        },
                        {
                            "id": "h2",
                            "type": "heading",
                            "text": "Next",
                            "level": 2,
                        },
                    ],
                    "reading_order": ["h1", "p1", "h2"],
                }
            ],
        }
    )


def _book() -> Book:
    return Book(
        metadata=BookMetadata(title="Fixture"),
        nodes=[
            BookNode(
                id="node-h1",
                type=NodeType.HEADING,
                content="Heading",
                source=[_source(0)],
                confidence=Confidence(1.0, 1.0, 1.0),
                attrs={"level": 1},
            ),
            BookNode(
                id="node-p1",
                type=NodeType.PARAGRAPH,
                content="Alpha beta",
                source=[_source(0)],
                confidence=Confidence(1.0, 1.0, 1.0),
            ),
            BookNode(
                id="node-h2",
                type=NodeType.HEADING,
                content="Next",
                source=[_source(0)],
                confidence=Confidence(1.0, 1.0, 1.0),
                attrs={"level": 2},
            ),
            BookNode(
                id="node-extra",
                type=NodeType.HEADING,
                content="Noise",
                source=[_source(0)],
                confidence=Confidence(1.0, 1.0, 1.0),
                attrs={"level": 2},
            ),
        ],
    )


def test_gold_sparse_tasks_compute_only_annotated_accuracy():
    result = evaluate_gold(_book(), _annotation())

    assert result.metrics["text"]["recall"] == 1.0
    assert result.metrics["text"]["precision"] == 0.8
    assert result.metrics["text"]["f1"] == 0.8889
    assert result.metrics["reading_order"]["pair_accuracy"] == 1.0
    assert result.metrics["reading_order"]["element_match_recall"] == 1.0

    headings = result.metrics["structures"]["headings"]
    assert headings["precision"] == 0.6667
    assert headings["recall"] == 1.0
    assert headings["f1"] == 0.8
    assert headings["level_accuracy"] == 1.0

    assert result.metrics["structures"]["tables"] is None
    assert result.metrics["structures"]["figures"] is None
    assert result.evidence["structures"]["headings"]["pages"][0]["unmatched_predictions"]


def test_gold_reading_order_penalizes_reversed_parser_order():
    book = _book()
    book.nodes[0], book.nodes[2] = book.nodes[2], book.nodes[0]

    result = evaluate_gold(book, _annotation())

    assert result.metrics["reading_order"]["pair_accuracy"] < 1.0
    assert result.metrics["reading_order"]["expected_pairs"] == 3


def test_gold_source_sha_and_page_range_are_strictly_validated():
    spec = CorpusDocumentSpec(
        id="fixture",
        title="Fixture",
        source_url="https://example.invalid/fixture.pdf",
        license_url="https://example.invalid/license",
        rights_basis="Test fixture.",
        sha256="a" * 64,
        document_class="test",
        language="en",
        page_count=1,
    )
    validate_gold_against_spec(_annotation(), spec)

    drifted = GoldAnnotation.from_dict(
        {
            **_annotation().to_dict(),
            "source_sha256": "b" * 64,
        }
    )
    with pytest.raises(GoldValidationError, match="source SHA-256"):
        validate_gold_against_spec(drifted, spec)

    bad_page = GoldAnnotation.from_dict(
        {
            **_annotation().to_dict(),
            "pages": [
                {
                    **_annotation().pages[0].to_dict(),
                    "page_index": 1,
                }
            ],
        }
    )
    with pytest.raises(GoldValidationError, match="outside"):
        validate_gold_against_spec(bad_page, spec)


def test_reviewed_gold_thresholds_and_baselines_gate_deterministically():
    metrics = evaluate_gold(_book(), _annotation()).metrics

    failures, deltas = evaluate_gold_gate(
        metrics,
        thresholds={
            "text.recall_min": 0.99,
            "reading_order.pair_accuracy_min": 1.0,
            "structures.headings.f1_min": 0.75,
        },
        baselines={"structures.headings.f1": 0.85},
        max_regression={"structures.headings.f1": 0.06},
    )

    assert failures == []
    assert deltas == {"structures.headings.f1": -0.05}

    failures, _ = evaluate_gold_gate(
        metrics,
        thresholds={"structures.headings.f1_min": 0.9},
    )
    assert failures == [
        "structures.headings.f1: expected >= 0.9, got 0.8"
    ]


def test_draft_gold_cannot_be_used_as_regression_gate():
    metrics = evaluate_gold(_book(), _annotation(status="draft")).metrics

    failures, deltas = evaluate_gold_gate(
        metrics,
        thresholds={"reading_order.pair_accuracy_min": 0.5},
    )

    assert failures == ["gold regression gates require annotation_status=reviewed"]
    assert deltas == {}


def test_real_nist_seed_is_source_pinned_and_sparse():
    manifest = CorpusManifest.load(REAL_MANIFEST)
    spec = manifest.select(["nist-eel-sp1500-101-v1"])[0]
    annotation = load_gold_annotation(REAL_MANIFEST, spec)

    assert annotation is not None
    assert annotation.status == "draft"
    assert annotation.source_sha256 == spec.sha256
    assert [page.page_index for page in annotation.pages] == [8]
    assert set(annotation.pages[0].tasks) == {"headings", "reading_order"}
    assert len(annotation.pages[0].elements) == 3


def test_real_nist_seed_matches_parser_text_blocks_for_order_but_not_heading_type():
    manifest = CorpusManifest.load(REAL_MANIFEST)
    spec = manifest.select(["nist-eel-sp1500-101-v1"])[0]
    annotation = load_gold_annotation(REAL_MANIFEST, spec)
    assert annotation is not None

    book = Book(
        metadata=BookMetadata(title="NIST"),
        nodes=[
            BookNode(
                id=f"node-{index}",
                type=NodeType.TEXT_BLOCK,
                content=element.text,
                source=[_source(8, parser="pymupdf")],
                confidence=Confidence(1.0, 0.25, 0.8),
            )
            for index, element in enumerate(annotation.pages[0].elements)
        ],
    )

    result = evaluate_gold(book, annotation)

    assert result.metrics["reading_order"]["pair_accuracy"] == 1.0
    assert result.metrics["reading_order"]["element_match_recall"] == 1.0
    assert result.metrics["structures"]["headings"]["recall"] == 0.0


def test_milestone_13_report_json_remains_loadable_without_gold_fields(tmp_path):
    payload = {
        "schema_version": "1",
        "corpus_id": "legacy",
        "manifest_path": "manifest.json",
        "documents": [{"id": "doc"}],
        "runs": [
            {
                "document_id": "doc",
                "backend": "pymupdf",
                "status": "success",
                "elapsed_seconds": 0.1,
                "metrics": {"quality_score": 1.0},
            }
        ],
    }
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    report = BenchmarkReport.load(path)

    assert report.runs[0].gold_metrics == {}
    assert report.runs[0].gold_evidence == {}
    assert report.runs[0].gold_gate_failures == []
    assert BackendRunResult.from_dict(payload["runs"][0]).to_dict()["gold_metrics"] == {}
