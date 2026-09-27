from pathlib import Path

from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.orchestration import (
    AttemptStatus,
    OrchestratorPolicy,
    ParserOrchestrator,
    QualityGate,
    StopReason,
)
from book.parsers import (
    BookParserAdapter,
    ParserBackendError,
    ParserCapabilities,
    ParserRegistry,
)


class FakeAdapter(BookParserAdapter):
    supported_extensions = frozenset({".pdf"})

    def __init__(
        self,
        name,
        book,
        *,
        capabilities=None,
        available=True,
        error=None,
    ):
        self.name = name
        self._book = book
        self.capabilities = capabilities or ParserCapabilities()
        self._available = available
        self._error = error
        self.parse_calls = 0

    def is_available(self):
        return self._available

    def parse(self, path):
        self.parse_calls += 1
        if self._error is not None:
            raise self._error
        return Book.from_dict(self._book.to_dict())


def _book(
    parser,
    *,
    extraction=0.99,
    structure=0.95,
    reading_order=0.95,
    node_type=NodeType.PARAGRAPH,
):
    return Book(
        metadata=BookMetadata(
            title=f"{parser} fixture",
            extra={"page_count": 1, "parser": parser},
        ),
        nodes=[
            BookNode(
                id=f"{parser}-node",
                type=node_type,
                content="Readable content.",
                source=[
                    SourceRef(
                        page_index=0,
                        bbox=(10.0, 10.0, 100.0, 40.0),
                        parser=parser,
                        source_id="fixture-source",
                    )
                ],
                confidence=Confidence(
                    extraction=extraction,
                    structure=structure,
                    reading_order=reading_order,
                ),
            )
        ],
    )


def _semantic_capabilities(**overrides):
    values = {
        "native_text": True,
        "ocr": True,
        "layout": True,
        "reading_order": True,
        "headings": True,
        "footnotes": True,
        "tables": True,
        "formulas": True,
        "bbox": True,
        "semantic_output": True,
    }
    values.update(overrides)
    return ParserCapabilities(**values)


def test_low_structure_quality_escalates_to_semantic_backend():
    cheap = FakeAdapter(
        "cheap",
        _book("cheap", structure=0.30),
        capabilities=ParserCapabilities(native_text=True, bbox=True),
    )
    semantic = FakeAdapter(
        "semantic",
        _book("semantic"),
        capabilities=_semantic_capabilities(),
    )
    registry = ParserRegistry([cheap, semantic])
    policy = OrchestratorPolicy(parser_priority=("cheap", "semantic"))

    result = ParserOrchestrator(registry, policy=policy).run(Path("book.pdf"))

    assert result.accepted is True
    assert result.selected_parser == "semantic"
    assert result.stop_reason == StopReason.QUALITY_ACCEPTED
    assert [attempt.status for attempt in result.attempts] == [
        AttemptStatus.REJECTED,
        AttemptStatus.ACCEPTED,
    ]
    assert "layout" in result.attempts[1].required_features
    assert "semantic_output" in result.attempts[1].required_features
    assert cheap.parse_calls == 1
    assert semantic.parse_calls == 1


def test_unavailable_candidate_is_audited_without_consuming_parse_budget():
    cheap = FakeAdapter(
        "cheap",
        _book("cheap", structure=0.30),
        capabilities=ParserCapabilities(native_text=True, bbox=True),
    )
    unavailable = FakeAdapter(
        "semantic-a",
        _book("semantic-a"),
        capabilities=_semantic_capabilities(),
        available=False,
    )
    fallback = FakeAdapter(
        "semantic-b",
        _book("semantic-b"),
        capabilities=_semantic_capabilities(),
    )
    registry = ParserRegistry([cheap, unavailable, fallback])
    policy = OrchestratorPolicy(
        parser_priority=("cheap", "semantic-a", "semantic-b"),
        max_attempts=2,
    )

    result = ParserOrchestrator(registry, policy=policy).run(Path("book.pdf"))

    assert result.accepted is True
    assert result.selected_parser == "semantic-b"
    assert [attempt.status for attempt in result.attempts] == [
        AttemptStatus.REJECTED,
        AttemptStatus.UNAVAILABLE,
        AttemptStatus.ACCEPTED,
    ]
    assert unavailable.parse_calls == 0


def test_backend_error_falls_through_to_next_candidate():
    failing = FakeAdapter(
        "broken",
        _book("broken"),
        capabilities=ParserCapabilities(native_text=True),
        error=ParserBackendError("decoder crashed"),
    )
    healthy = FakeAdapter(
        "healthy",
        _book("healthy"),
        capabilities=ParserCapabilities(native_text=True),
    )
    registry = ParserRegistry([failing, healthy])
    policy = OrchestratorPolicy(parser_priority=("broken", "healthy"))

    result = ParserOrchestrator(registry, policy=policy).run(Path("book.pdf"))

    assert result.accepted is True
    assert result.selected_parser == "healthy"
    assert result.attempts[0].status == AttemptStatus.FAILED
    assert result.attempts[0].error_type == "ParserBackendError"


def test_required_features_filter_candidates_before_first_parse():
    cheap = FakeAdapter(
        "cheap",
        _book("cheap"),
        capabilities=ParserCapabilities(native_text=True),
    )
    formula = FakeAdapter(
        "formula",
        _book("formula"),
        capabilities=_semantic_capabilities(),
    )
    registry = ParserRegistry([cheap, formula])
    policy = OrchestratorPolicy(parser_priority=("cheap", "formula"))

    result = ParserOrchestrator(registry, policy=policy).run(
        Path("book.pdf"),
        required_features=("formulas",),
    )

    assert result.accepted is True
    assert result.selected_parser == "formula"
    assert cheap.parse_calls == 0
    assert result.attempts[0].required_features == ("formulas",)


def test_exhausted_route_returns_best_rejected_result_for_review():
    better = FakeAdapter(
        "better",
        _book("better", structure=0.50),
        capabilities=_semantic_capabilities(),
    )
    worse = FakeAdapter(
        "worse",
        _book("worse", extraction=0.20),
        capabilities=_semantic_capabilities(),
    )
    registry = ParserRegistry([better, worse])
    policy = OrchestratorPolicy(
        parser_priority=("better", "worse"),
        max_attempts=2,
        gate=QualityGate(
            minimum_score=1.0,
            max_error_issues=0,
            max_review_ratio=0.0,
        ),
    )

    result = ParserOrchestrator(registry, policy=policy).run(Path("book.pdf"))

    assert result.accepted is False
    assert result.selected_parser == "better"
    assert result.stop_reason == StopReason.MAX_ATTEMPTS
    assert result.quality_report is not None
    assert result.quality_report.score == 0.92


def test_orchestration_audit_is_written_to_selected_book():
    adapter = FakeAdapter(
        "semantic",
        _book("semantic"),
        capabilities=_semantic_capabilities(),
    )
    registry = ParserRegistry([adapter])
    policy = OrchestratorPolicy(parser_priority=("semantic",))

    result = ParserOrchestrator(registry, policy=policy).run(Path("book.pdf"))

    assert result.book is not None
    audit = result.book.metadata.extra["orchestration"]
    assert audit["accepted"] is True
    assert audit["selected_parser"] == "semantic"
    assert audit["stop_reason"] == "quality_accepted"
    assert audit["attempts"][0]["status"] == "accepted"
    assert result.book.metadata.extra["quality"]["report"]["score"] == 1.0


def test_no_capable_parser_returns_explicit_no_candidates_result():
    adapter = FakeAdapter(
        "text-only",
        _book("text-only"),
        capabilities=ParserCapabilities(native_text=True),
    )
    registry = ParserRegistry([adapter])
    policy = OrchestratorPolicy(parser_priority=("text-only",))

    result = ParserOrchestrator(registry, policy=policy).run(
        Path("book.pdf"),
        required_features=("tables",),
    )

    assert result.accepted is False
    assert result.book is None
    assert result.quality_report is None
    assert result.selected_parser is None
    assert result.stop_reason == StopReason.NO_CANDIDATES
    assert result.attempts == []
