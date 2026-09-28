import base64
import hashlib
import json
from pathlib import Path

import fitz
import pytest

from book.benchmark.gold import GoldAnnotation
from book.benchmark.review_workbench import GoldReviewStore


def _write_pdf(path: Path) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "1 Introduction")
    page.insert_text((72, 110), "A short paragraph for gold review.")
    document.save(path)
    document.close()
    return path.read_bytes()


def _fixture_store(tmp_path: Path) -> GoldReviewStore:
    pdf_path = tmp_path / "source.pdf"
    pdf_bytes = _write_pdf(pdf_path)
    digest = hashlib.sha256(pdf_bytes).hexdigest()

    asset = tmp_path / "fixture.pdf.b64"
    asset.write_bytes(base64.b64encode(pdf_bytes))

    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    gold_path = gold_dir / "fixture.json"
    gold_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "document_id": "fixture",
                "source_sha256": digest,
                "status": "draft",
                "annotated_by": "seed",
                "reviewed_by": "",
                "notes": "fixture draft",
                "pages": [
                    {
                        "page_index": 0,
                        "tasks": ["headings", "reading_order"],
                        "elements": [
                            {
                                "id": "h1",
                                "type": "heading",
                                "text": "1 Introduction",
                                "level": 1,
                            }
                        ],
                        "reading_order": ["h1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "workbench-fixture",
                "documents": [
                    {
                        "id": "fixture",
                        "title": "Fixture PDF",
                        "source_url": "https://example.invalid/fixture.pdf",
                        "license_url": "https://example.invalid/license",
                        "rights_basis": "Test fixture",
                        "sha256": digest,
                        "document_class": "test",
                        "language": "en",
                        "page_count": 1,
                        "complexity_tags": ["heading"],
                        "expected_capabilities": ["native_text"],
                        "redistributable": True,
                        "embedded_base64_path": asset.name,
                        "gold_annotations_path": "gold/fixture.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    review_plan = tmp_path / "review-plan.json"
    review_plan.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "workbench-fixture",
                "targets": [
                    {
                        "document_id": "fixture",
                        "page_index": 0,
                        "tasks": ["headings", "reading_order"],
                        "difficulty_tags": ["heading"],
                        "priority": "high",
                        "rationale": "fixture",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    return GoldReviewStore(
        manifest,
        review_plan,
        tmp_path / "cache",
        tmp_path / "workspace",
    )


def _confirm_all(store: GoldReviewStore, session_id: str, reviewer: str = "alice"):
    session = store.get(session_id)
    page = session.annotation.pages[0]
    for element in page.elements:
        store.confirm(
            session_id,
            subject="element",
            subject_id=element.id,
            reviewer=reviewer,
        )
    for task in page.tasks:
        store.confirm(
            session_id,
            subject="task",
            subject_id=task,
            reviewer=reviewer,
        )


def test_queue_exposes_annotation_status_and_source_pin(tmp_path):
    store = _fixture_store(tmp_path)

    queue = store.queue()

    assert queue["corpus_id"] == "workbench-fixture"
    assert queue["target_count"] == 1
    assert queue["items"][0]["annotation_status"] == "draft"
    assert len(queue["items"][0]["source_sha256"]) == 64


def test_create_session_materializes_source_and_parser_overlay(tmp_path):
    store = _fixture_store(tmp_path)

    session = store.create("fixture", 0)
    payload = session.to_dict()

    assert session.annotation.status == "draft"
    assert Path(session.source_path).is_file()
    assert payload["page"]["width"] > 0
    assert payload["page"]["height"] > 0
    assert payload["parser_nodes"]
    assert payload["preflight"]["ready"] is False
    assert payload["preflight"]["missing_elements"] == ["h1"]
    assert set(payload["preflight"]["missing_tasks"]) == {
        "headings",
        "reading_order",
    }


def test_page_renderer_returns_png(tmp_path):
    store = _fixture_store(tmp_path)
    session = store.create("fixture", 0)

    image = store.render_page(session.id, scale=1.0)

    assert image.startswith(b"\x89PNG\r\n\x1a\n")


def test_edit_resets_confirmation_and_promotion_requires_full_review(tmp_path):
    store = _fixture_store(tmp_path)
    session = store.create("fixture", 0)

    _confirm_all(store, session.id)
    ready = store.get(session.id)
    assert ready.preflight()["ready"] is True

    edited = store.upsert_element(
        session.id,
        {
            "id": "h1",
            "type": "heading",
            "text": "1 Introduction corrected",
            "level": 1,
        },
    )
    assert edited.preflight()["ready"] is False
    assert edited.preflight()["missing_elements"] == ["h1"]

    with pytest.raises(ValueError, match="promotion blocked"):
        store.promote(session.id, reviewer="alice")

    store.confirm(
        session.id,
        subject="element",
        subject_id="h1",
        reviewer="alice",
    )
    promoted = store.promote(
        session.id,
        reviewer="alice",
        note="Checked against rendered PDF page.",
    )

    assert promoted.promoted_annotation is not None
    assert promoted.promoted_annotation.status == "reviewed"
    assert promoted.promoted_annotation.reviewed_by == "alice"
    assert "Review:" in promoted.promoted_annotation.notes
    assert store.promoted_path(session.id).is_file()
    audit_path = store.audit_path(session.id)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    assert audit["source_sha256"] == promoted.source_sha256
    assert audit["reviewed_by"] == "alice"
    assert audit["published_at"] is None
    assert len(audit["decisions"]) == 3


def test_promotion_reviewer_must_participate_in_confirmations(tmp_path):
    store = _fixture_store(tmp_path)
    session = store.create("fixture", 0)
    _confirm_all(store, session.id, reviewer="alice")

    with pytest.raises(ValueError, match="must have confirmed"):
        store.promote(session.id, reviewer="bob")


def test_publish_is_explicit_and_detects_canonical_drift(tmp_path):
    store = _fixture_store(tmp_path)
    session = store.create("fixture", 0)
    _confirm_all(store, session.id)
    promoted = store.promote(session.id, reviewer="alice")

    canonical_path = tmp_path / "gold" / "fixture.json"
    before = GoldAnnotation.load(canonical_path)
    assert before.status == "draft"

    published = store.publish(session.id)
    after = GoldAnnotation.load(canonical_path)

    assert published.published_at
    assert after.status == "reviewed"
    assert after.reviewed_by == "alice"
    audit = json.loads(store.audit_path(session.id).read_text(encoding="utf-8"))
    assert audit["published_at"] == published.published_at

    second = store.create("fixture", 0)
    _confirm_all(store, second.id, reviewer="carol")
    store.promote(second.id, reviewer="carol")

    payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    payload["notes"] = "concurrent canonical edit"
    canonical_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="changed since this review session opened"):
        store.publish(second.id)


def test_unannotated_target_stages_empty_draft_page(tmp_path):
    store = _fixture_store(tmp_path)
    manifest = json.loads(store.manifest_path.read_text(encoding="utf-8"))
    manifest["documents"][0]["gold_annotations_path"] = ""
    store.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    fresh = GoldReviewStore(
        store.manifest_path,
        store.review_plan_path,
        tmp_path / "cache2",
        tmp_path / "workspace2",
    )
    session = fresh.create("fixture", 0)

    assert session.annotation.status == "draft"
    assert session.annotation.pages[0].elements == ()
    assert session.annotation.pages[0].tasks == ("headings", "reading_order")
    with pytest.raises(ValueError, match="gold_annotations_path"):
        _confirm_all(fresh, session.id)
        fresh.promote(session.id, reviewer="alice")
        fresh.publish(session.id)


def test_other_draft_pages_block_single_page_promotion(tmp_path):
    store = _fixture_store(tmp_path)
    canonical_path = tmp_path / "gold" / "fixture.json"
    payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    payload["pages"].append(
        {
            "page_index": 0,
            "tasks": ["headings"],
            "elements": [],
        }
    )
    # Duplicate page indexes are invalid, so instead make the fixture manifest two pages
    # and move the added draft annotation to page 1.
    payload["pages"][1]["page_index"] = 1
    canonical_path.write_text(json.dumps(payload), encoding="utf-8")

    manifest = json.loads(store.manifest_path.read_text(encoding="utf-8"))
    manifest["documents"][0]["page_count"] = 2
    store.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    fresh = GoldReviewStore(
        store.manifest_path,
        store.review_plan_path,
        tmp_path / "cache3",
        tmp_path / "workspace3",
    )
    session = fresh.create("fixture", 0)
    _confirm_all(fresh, session.id)

    assert session.blocking_draft_pages == (1,)
    with pytest.raises(ValueError, match="other draft pages require review first"):
        fresh.promote(session.id, reviewer="alice")
