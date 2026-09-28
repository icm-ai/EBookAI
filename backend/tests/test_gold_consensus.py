import base64
import hashlib
import json
from pathlib import Path

import fitz
import pytest
from book.benchmark.baseline import (
    ReviewedBaselineSnapshot,
    build_reviewed_baseline,
    load_baseline_leaderboard,
    write_reviewed_baseline,
)
from book.benchmark.consensus import GoldConsensusStore, compare_reviewed_pages
from book.benchmark.gold import GoldAnnotation
from book.benchmark.leaderboard import (
    LeaderboardPolicy,
    ParserLeaderboard,
    build_leaderboard,
)
from book.benchmark.models import BackendRunResult, BenchmarkReport
from book.benchmark.review_workbench import GoldReviewStore


def _write_pdf(path: Path) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "1 Introduction")
    page.insert_text((72, 110), "A short paragraph for consensus review.")
    document.save(path)
    document.close()
    return path.read_bytes()


def _fixture_store(tmp_path: Path) -> GoldReviewStore:
    pdf_bytes = _write_pdf(tmp_path / "source.pdf")
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    asset = tmp_path / "fixture.pdf.b64"
    asset.write_bytes(base64.b64encode(pdf_bytes))
    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    (gold_dir / "fixture.json").write_text(
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


def _confirm_all(store: GoldReviewStore, session_id: str, reviewer: str) -> None:
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


def _promoted_pair(tmp_path: Path, *, conflict: bool = False):
    store = _fixture_store(tmp_path)
    first = store.create("fixture", 0)
    second = store.create("fixture", 0)

    _confirm_all(store, first.id, reviewer="alice")
    store.promote(first.id, reviewer="alice")

    if conflict:
        store.upsert_element(
            second.id,
            {
                "id": "h1",
                "type": "heading",
                "text": "1 Introduction revised",
                "level": 1,
            },
        )
    _confirm_all(store, second.id, reviewer="bob")
    store.promote(second.id, reviewer="bob")
    consensus = GoldConsensusStore(
        store.manifest_path,
        store,
        tmp_path / "workspace",
    )
    return store, consensus, first.id, second.id


def test_identical_independent_reviews_form_consensus_without_adjudication(tmp_path):
    _, consensus, first_id, second_id = _promoted_pair(tmp_path)

    bundle = consensus.create(first_id, second_id)

    assert bundle.status == "consensus"
    assert bundle.conflicts == ()
    assert bundle.consensus_annotation is not None
    assert bundle.consensus_annotation.status == "reviewed"
    assert bundle.consensus_annotation.reviewed_by == "alice + bob"
    assert consensus.consensus_path(bundle.id).is_file()
    audit = json.loads(consensus.audit_path(bundle.id).read_text(encoding="utf-8"))
    assert audit["reviewer_a"] == "alice"
    assert audit["reviewer_b"] == "bob"
    assert audit["conflicts"] == []


def test_semantic_element_conflict_requires_independent_adjudicator(tmp_path):
    _, consensus, first_id, second_id = _promoted_pair(tmp_path, conflict=True)

    bundle = consensus.create(first_id, second_id)

    assert bundle.status == "conflicted"
    assert [item.id for item in bundle.conflicts] == ["element:h1"]
    assert bundle.unresolved_conflicts == ("element:h1",)
    assert bundle.consensus_annotation is None

    with pytest.raises(ValueError, match="independent"):
        consensus.adjudicate(
            bundle.id,
            conflict_id="element:h1",
            choice="b",
            adjudicator="alice",
        )

    resolved = consensus.adjudicate(
        bundle.id,
        conflict_id="element:h1",
        choice="b",
        adjudicator="carol",
        note="Compared both candidates against the pinned PDF.",
    )

    assert resolved.status == "consensus"
    assert resolved.unresolved_conflicts == ()
    assert resolved.consensus_annotation is not None
    page = resolved.consensus_annotation.pages[0]
    assert page.elements[0].text == "1 Introduction revised"
    assert "adjudicated by carol" in resolved.consensus_annotation.reviewed_by


def test_consensus_rejects_same_reviewer_and_canonical_revision_drift(tmp_path):
    store = _fixture_store(tmp_path)
    first = store.create("fixture", 0)
    second = store.create("fixture", 0)
    _confirm_all(store, first.id, reviewer="alice")
    _confirm_all(store, second.id, reviewer="alice")
    store.promote(first.id, reviewer="alice")
    store.promote(second.id, reviewer="alice")
    consensus = GoldConsensusStore(
        store.manifest_path,
        store,
        tmp_path / "workspace",
    )

    with pytest.raises(ValueError, match="distinct reviewer"):
        consensus.create(first.id, second.id)

    third = store.create("fixture", 0)
    _confirm_all(store, third.id, reviewer="bob")
    store.promote(third.id, reviewer="bob")
    canonical_path = tmp_path / "gold" / "fixture.json"
    payload = json.loads(canonical_path.read_text(encoding="utf-8"))
    payload["notes"] = "changed canonical revision"
    canonical_path.write_text(json.dumps(payload), encoding="utf-8")
    fourth = store.create("fixture", 0)
    _confirm_all(store, fourth.id, reviewer="carol")
    store.promote(fourth.id, reviewer="carol")

    with pytest.raises(ValueError, match="same canonical gold revision"):
        consensus.create(third.id, fourth.id)


def test_consensus_publish_is_explicit_and_detects_drift(tmp_path):
    _, consensus, first_id, second_id = _promoted_pair(tmp_path)
    bundle = consensus.create(first_id, second_id)
    canonical_path = tmp_path / "gold" / "fixture.json"

    assert GoldAnnotation.load(canonical_path).status == "draft"

    published = consensus.publish(bundle.id)

    assert published.status == "published"
    canonical = GoldAnnotation.load(canonical_path)
    assert canonical.status == "reviewed"
    assert canonical.reviewed_by == "alice + bob"

    second_root = tmp_path / "second"
    second_root.mkdir()
    store2 = _fixture_store(second_root)
    first2 = store2.create("fixture", 0)
    second2 = store2.create("fixture", 0)
    _confirm_all(store2, first2.id, reviewer="alice")
    _confirm_all(store2, second2.id, reviewer="bob")
    store2.promote(first2.id, reviewer="alice")
    store2.promote(second2.id, reviewer="bob")
    consensus2 = GoldConsensusStore(
        store2.manifest_path,
        store2,
        tmp_path / "second" / "workspace",
    )
    bundle2 = consensus2.create(first2.id, second2.id)
    canonical2 = tmp_path / "second" / "gold" / "fixture.json"
    payload = json.loads(canonical2.read_text(encoding="utf-8"))
    payload["notes"] = "concurrent edit"
    canonical2.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="changed since"):
        consensus2.publish(bundle2.id)


def test_compare_reviewed_pages_ignores_provenance_fields(tmp_path):
    store, _, first_id, second_id = _promoted_pair(tmp_path)
    first = store.get(first_id).promoted_annotation
    second = store.get(second_id).promoted_annotation

    assert first is not None
    assert second is not None
    assert first.reviewed_by != second.reviewed_by
    assert compare_reviewed_pages(first, second, 0) == ()


def _reviewed_leaderboard() -> ParserLeaderboard:
    report = BenchmarkReport(
        corpus_id="workbench-fixture",
        manifest_path="manifest.json",
        runs=[
            BackendRunResult(
                document_id="fixture",
                backend="pymupdf",
                status="success",
                elapsed_seconds=0.1,
                metrics={"quality_score": 0.9},
                gold_metrics={
                    "annotation_status": "reviewed",
                    "annotated_pages": [0],
                    "text": {"f1": 1.0},
                    "reading_order": {"pair_accuracy": 1.0},
                    "structures": {},
                },
            )
        ],
    )
    return build_leaderboard(
        report,
        policy=LeaderboardPolicy(
            minimum_annotated_documents=1,
            minimum_annotated_pages=1,
        ),
    )


def test_reviewed_baseline_requires_canonical_reviewed_gold(tmp_path):
    store = _fixture_store(tmp_path)
    board = _reviewed_leaderboard()

    with pytest.raises(ValueError, match="canonical reviewed gold"):
        build_reviewed_baseline(store.manifest_path, board)

    first = store.create("fixture", 0)
    second = store.create("fixture", 0)
    _confirm_all(store, first.id, reviewer="alice")
    _confirm_all(store, second.id, reviewer="bob")
    store.promote(first.id, reviewer="alice")
    store.promote(second.id, reviewer="bob")
    consensus = GoldConsensusStore(
        store.manifest_path,
        store,
        tmp_path / "workspace",
    )
    bundle = consensus.create(first.id, second.id)
    consensus.publish(bundle.id)

    snapshot = build_reviewed_baseline(store.manifest_path, board)
    path = write_reviewed_baseline(snapshot, tmp_path / "baseline.json")
    loaded = ReviewedBaselineSnapshot.load(path)

    assert loaded.corpus_id == "workbench-fixture"
    assert loaded.gold_sha256.keys() == {"fixture"}
    assert loaded.leaderboard.entries[0].eligible is True
    assert loaded.to_dict() == snapshot.to_dict()
    assert load_baseline_leaderboard(path).to_dict() == board.to_dict()


def test_reviewed_baseline_rejects_draft_leaderboard(tmp_path):
    store = _fixture_store(tmp_path)
    board = _reviewed_leaderboard()
    exploratory = type(board)(
        corpus_id=board.corpus_id,
        policy=LeaderboardPolicy(include_draft=True),
        entries=board.entries,
    )

    with pytest.raises(ValueError, match="cannot include draft"):
        build_reviewed_baseline(store.manifest_path, exploratory)
