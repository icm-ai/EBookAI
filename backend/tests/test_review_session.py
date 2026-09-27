from pathlib import Path

import fitz
from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)
from book.orchestration import OrchestrationResult, StopReason
from book.quality import QualityEngine
from book.review import ReviewSessionStore


class FakeOrchestrator:
    def __init__(self, result):
        self.result = result

    def run(self, path):
        return self.result


def _write_pdf(path: Path, text: str = "A normal body paragraph.") -> None:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def _source():
    return SourceRef(
        page_index=0,
        bbox=(10.0, 20.0, 300.0, 400.0),
        parser="fixture",
        source_id="fixture-source",
    )


def _issue_book():
    return Book(
        metadata=BookMetadata(title="Fixture"),
        nodes=[
            BookNode(
                id="empty",
                type=NodeType.PARAGRAPH,
                content="",
                source=[_source()],
                confidence=Confidence(0.95, 0.95, 0.95),
            )
        ],
    )


def test_review_session_persists_real_pymupdf_result(tmp_path):
    source = tmp_path / "fixture.pdf"
    _write_pdf(source)
    store = ReviewSessionStore(tmp_path / "sessions")

    session = store.create(source, "fixture.pdf")
    restored = store.get(session.id)

    assert restored.source_filename == "fixture.pdf"
    assert restored.book.metadata.source_path == "fixture.pdf"
    assert restored.book.metadata.extra["orchestration"]["selected_parser"] == "pymupdf"
    assert restored.quality_report.score == 1.0
    assert store.source_path(session.id).is_file()


def test_accept_issue_applies_patch_reanalyzes_and_persists_decision(tmp_path):
    book = _issue_book()
    report = QualityEngine().analyze(book)
    result = OrchestrationResult(
        book=book,
        quality_report=report,
        accepted=False,
        selected_parser="fixture",
        stop_reason=StopReason.EXHAUSTED,
        attempts=[],
        required_features=(),
    )
    source = tmp_path / "fixture.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    store = ReviewSessionStore(
        tmp_path / "sessions",
        orchestrator=FakeOrchestrator(result),
    )

    session = store.create(source, "fixture.pdf")
    issue = next(
        item for item in session.quality_report.issues if item.code == "empty_content"
    )
    updated = store.accept_issue(session.id, issue.id)
    restored = store.get(session.id)

    assert updated.book.find_node("empty") is None
    assert updated.book.patches[0].applied is True
    assert updated.decisions[issue.id].decision == "accepted"
    assert updated.decisions[issue.id].patch_id == issue.suggested_patch.id
    assert [item.code for item in updated.quality_report.issues] == ["empty_document"]
    assert restored.decisions[issue.id].decision == "accepted"
    assert (
        restored.book.metadata.extra["review"]["decisions"][0]["issue_id"] == issue.id
    )


def test_reject_issue_keeps_book_and_records_reason(tmp_path):
    book = _issue_book()
    report = QualityEngine().analyze(book)
    result = OrchestrationResult(
        book=book,
        quality_report=report,
        accepted=False,
        selected_parser="fixture",
        stop_reason=StopReason.EXHAUSTED,
        attempts=[],
        required_features=(),
    )
    source = tmp_path / "fixture.pdf"
    source.write_bytes(b"%PDF-1.4\n")
    store = ReviewSessionStore(
        tmp_path / "sessions",
        orchestrator=FakeOrchestrator(result),
    )

    session = store.create(source, "fixture.pdf")
    issue = next(
        item for item in session.quality_report.issues if item.code == "empty_content"
    )
    updated = store.reject_issue(
        session.id,
        issue.id,
        reason="Keep intentional blank paragraph",
    )

    assert updated.book.find_node("empty") is not None
    assert updated.book.patches == []
    assert updated.decisions[issue.id].decision == "rejected"
    assert updated.decisions[issue.id].reason == "Keep intentional blank paragraph"
