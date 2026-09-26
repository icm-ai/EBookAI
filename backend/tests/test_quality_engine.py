from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.quality import (
    HeadingHierarchyDetector,
    IssueSeverity,
    QualityEngine,
    QualityReport,
)


def _source(page=0):
    return SourceRef(
        page_index=page,
        bbox=(10.0, 20.0, 300.0, 400.0),
        parser="fixture",
        source_id="fixture-source",
    )


def test_quality_engine_reports_explainable_node_issues():
    book = Book(
        metadata=BookMetadata(title="Fixture"),
        nodes=[
            BookNode(
                id="raw",
                type=NodeType.TEXT_BLOCK,
                content="Unclassified",
                source=[_source()],
                confidence=Confidence(0.95, 0.30, 0.90),
            ),
            BookNode(
                id="missing-source",
                type=NodeType.PARAGRAPH,
                content="No provenance",
                confidence=Confidence(0.95, 0.90, 0.90),
            ),
            BookNode(
                id="empty",
                type=NodeType.PARAGRAPH,
                content="",
                source=[_source(1)],
                confidence=Confidence(1.0, 0.9, 0.9),
            ),
        ],
    )

    report = QualityEngine().analyze(book)

    codes = [issue.code for issue in report.issues]
    assert "unclassified_text_block" in codes
    assert "low_confidence" in codes
    assert "missing_provenance" in codes
    assert "empty_content" in codes
    assert report.counts[IssueSeverity.ERROR.value] >= 1
    assert 0.0 <= report.score < 1.0


def test_heading_hierarchy_detector_proposes_explicit_patch():
    book = Book(
        metadata=BookMetadata(title="Fixture"),
        nodes=[
            BookNode(
                id="h1",
                type=NodeType.HEADING,
                content="One",
                source=[_source()],
                attrs={"level": 1},
            ),
            BookNode(
                id="h3",
                type=NodeType.HEADING,
                content="Skipped",
                source=[_source()],
                attrs={"level": 3},
            ),
        ],
    )

    issues = HeadingHierarchyDetector().detect(book)

    assert len(issues) == 1
    issue = issues[0]
    assert issue.evidence["expected_level"] == 2
    assert issue.suggested_patch is not None
    assert issue.suggested_patch.payload == {"key": "level", "value": 2}


def test_quality_report_round_trip_is_deterministic():
    book = Book(
        metadata=BookMetadata(title="Fixture"),
        nodes=[
            BookNode(
                id="p1",
                type=NodeType.PARAGRAPH,
                content="Text",
                source=[_source()],
                confidence=Confidence(0.99, 0.95, 0.95),
            )
        ],
    )

    report = QualityEngine().analyze(book)
    restored = QualityReport.from_json(report.to_json())

    assert restored.to_dict() == report.to_dict()


def test_confidence_recalculation_returns_copy_and_caps_affected_axis():
    original = Book(
        metadata=BookMetadata(title="Fixture"),
        nodes=[
            BookNode(
                id="raw",
                type=NodeType.TEXT_BLOCK,
                content="Still raw",
                source=[_source()],
                confidence=Confidence(0.99, 0.95, 0.95),
            )
        ],
    )

    recalculated, report = QualityEngine().recalculate_confidence(original)

    assert original.nodes[0].confidence.structure == 0.95
    assert recalculated.nodes[0].confidence.structure == 0.45
    assert recalculated.nodes[0].confidence.extraction == 0.99
    assert recalculated.metadata.extra["quality"]["report"] == report.to_dict()
    assert recalculated.metadata.extra["quality"]["confidence_recalculated"] is True
