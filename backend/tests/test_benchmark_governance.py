import base64
import hashlib
import json
from pathlib import Path

import fitz
import pytest
from book.benchmark.baseline import (
    ReviewedBaselineRegistry,
    build_reviewed_baseline,
    load_active_reviewed_baseline,
    register_reviewed_baseline,
    write_reviewed_baseline,
)
from book.benchmark.consensus import GoldConsensusStore
from book.benchmark.governance import (
    BenchmarkGovernancePolicy,
    build_governance_release_manifest,
    evaluate_governance,
)
from book.benchmark.leaderboard import LeaderboardPolicy, build_leaderboard
from book.benchmark.models import BackendRunResult, BenchmarkReport
from book.benchmark.provenance import ConsensusProvenanceRegistry
from book.benchmark.review_workbench import GoldReviewStore


def _write_pdf(path: Path) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "1 Introduction")
    page.insert_text((72, 110), "Governed benchmark fixture.")
    document.save(path)
    document.close()
    return path.read_bytes()


def _fixture(tmp_path: Path):
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
                "notes": "governance fixture",
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
                "corpus_id": "governance-fixture",
                "documents": [
                    {
                        "id": "fixture",
                        "title": "Fixture",
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
    plan = tmp_path / "review-plan.json"
    plan.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "governance-fixture",
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
    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()
    registry_path = baseline_dir / "registry.json"
    registry_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "active_baseline_id": None,
                "baselines": [],
            }
        ),
        encoding="utf-8",
    )
    provenance_dir = tmp_path / "provenance"
    provenance_dir.mkdir()
    provenance_path = provenance_dir / "registry.json"
    provenance_path.write_text(
        json.dumps({"schema_version": "1", "records": []}),
        encoding="utf-8",
    )
    store = GoldReviewStore(
        manifest,
        plan,
        tmp_path / "cache",
        tmp_path / "workspace",
    )
    return store, registry_path, provenance_path


def _confirm_all(
    store: GoldReviewStore,
    session_id: str,
    reviewer: str,
) -> None:
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


def _publish_consensus(store: GoldReviewStore) -> GoldConsensusStore:
    first = store.create("fixture", 0)
    second = store.create("fixture", 0)
    _confirm_all(store, first.id, "alice")
    _confirm_all(store, second.id, "bob")
    store.promote(first.id, reviewer="alice")
    store.promote(second.id, reviewer="bob")
    consensus = GoldConsensusStore(
        store.manifest_path,
        store,
        store.workspace_dir,
    )
    bundle = consensus.create(first.id, second.id)
    consensus.publish(bundle.id)
    return consensus


def _leaderboard(
    *,
    text_f1: float = 1.0,
    pages=(0,),
    annotation_status: str = "reviewed",
):
    report = BenchmarkReport(
        corpus_id="governance-fixture",
        manifest_path="manifest.json",
        runs=[
            BackendRunResult(
                document_id="fixture",
                backend="pymupdf",
                status="success",
                elapsed_seconds=0.1,
                metrics={"quality_score": 0.9},
                gold_metrics={
                    "annotation_status": annotation_status,
                    "annotated_pages": list(pages),
                    "text": {"f1": text_f1},
                    "reading_order": {"pair_accuracy": 1.0},
                    "structures": {
                        "headings": {"f1": 1.0},
                        "lists": None,
                        "tables": None,
                        "figures": None,
                        "captions": None,
                        "footnotes": None,
                        "formulas": None,
                    },
                },
            )
        ],
    )
    return build_leaderboard(
        report,
        policy=LeaderboardPolicy(
            minimum_annotated_documents=1,
            minimum_annotated_pages=1,
            maximum_metric_regression=0.02,
        ),
    )


def _policy() -> BenchmarkGovernancePolicy:
    return BenchmarkGovernancePolicy(
        ci_backends=("pymupdf",),
        minimum_reviewed_documents=1,
        minimum_reviewed_pages=1,
        minimum_eligible_ci_backends=1,
        minimum_metrics_per_backend=1,
        maximum_metric_regression=0.02,
    )


def test_bootstrap_governance_passes_only_while_reviewed_gold_is_empty(tmp_path):
    store, registry_path, provenance_path = _fixture(tmp_path)

    report = evaluate_governance(
        store.manifest_path,
        _policy(),
        registry_path,
        provenance_registry_path=provenance_path,
    )

    assert report.ok is True
    assert report.mode == "bootstrap"
    assert report.reviewed_documents == 0
    assert report.active_baseline_id is None
    assert "accuracy execution is dormant" in report.warnings[0]


def test_consensus_publish_creates_canonical_provenance_and_requires_baseline(tmp_path):
    store, registry_path, _ = _fixture(tmp_path)
    _publish_consensus(store)
    provenance_path = tmp_path / "provenance" / "registry.json"
    registry = ConsensusProvenanceRegistry.load(provenance_path)

    record = registry.document("fixture")
    assert record is not None
    assert record.current_gold_sha256
    assert len(record.reviews) == 1
    audit_path = tmp_path / record.reviews[0].audit_path
    assert audit_path.is_file()

    report = evaluate_governance(
        store.manifest_path,
        _policy(),
        registry_path,
        provenance_registry_path=provenance_path,
    )

    assert report.ok is False
    assert report.reviewed_documents == 1
    assert report.reviewed_pages == 1
    assert report.failures == (
        "canonical reviewed gold exists but no active reviewed baseline is registered",
    )


def test_reviewed_gold_without_consensus_provenance_fails_closed(tmp_path):
    store, registry_path, provenance_path = _fixture(tmp_path)
    canonical = tmp_path / "gold" / "fixture.json"
    payload = json.loads(canonical.read_text(encoding="utf-8"))
    payload["status"] = "reviewed"
    payload["reviewed_by"] = "manual"
    canonical.write_text(json.dumps(payload), encoding="utf-8")

    report = evaluate_governance(
        store.manifest_path,
        _policy(),
        registry_path,
        provenance_registry_path=provenance_path,
    )

    assert report.ok is False
    assert (
        "reviewed document fixture has no consensus provenance record"
        in report.failures
    )


def test_versioned_baseline_activates_strict_governance(tmp_path):
    store, registry_path, _ = _fixture(tmp_path)
    _publish_consensus(store)
    provenance_path = tmp_path / "provenance" / "registry.json"
    board = _leaderboard()
    snapshot = build_reviewed_baseline(store.manifest_path, board)
    baseline_path = registry_path.parent / "v1.json"
    write_reviewed_baseline(snapshot, baseline_path)

    registry = register_reviewed_baseline(
        registry_path,
        baseline_path,
        "v1",
    )

    assert registry.active_baseline_id == "v1"
    assert load_active_reviewed_baseline(registry_path) is not None

    report = evaluate_governance(
        store.manifest_path,
        _policy(),
        registry_path,
        provenance_registry_path=provenance_path,
        current_leaderboard=board,
    )

    assert report.ok is True
    assert report.mode == "strict"
    assert report.active_baseline_id == "v1"
    assert report.tracked_ci_backends == ("pymupdf",)


def test_strict_governance_detects_metric_regression(tmp_path):
    store, registry_path, _ = _fixture(tmp_path)
    _publish_consensus(store)
    provenance_path = tmp_path / "provenance" / "registry.json"
    baseline_board = _leaderboard(text_f1=1.0)
    snapshot = build_reviewed_baseline(store.manifest_path, baseline_board)
    baseline_path = registry_path.parent / "v1.json"
    write_reviewed_baseline(snapshot, baseline_path)
    register_reviewed_baseline(registry_path, baseline_path, "v1")

    report = evaluate_governance(
        store.manifest_path,
        _policy(),
        registry_path,
        provenance_registry_path=provenance_path,
        current_leaderboard=_leaderboard(text_f1=0.9),
    )

    assert report.ok is False
    assert any("pymupdf:text.f1" in item for item in report.failures)


def test_registered_baseline_id_is_immutable(tmp_path):
    store, registry_path, _ = _fixture(tmp_path)
    _publish_consensus(store)
    board = _leaderboard()
    first = build_reviewed_baseline(store.manifest_path, board)
    first_path = registry_path.parent / "v1.json"
    write_reviewed_baseline(first, first_path)
    register_reviewed_baseline(registry_path, first_path, "v1")

    payload = json.loads(first_path.read_text(encoding="utf-8"))
    payload["created_at"] = "different-bytes"
    first_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="bytes changed"):
        load_active_reviewed_baseline(registry_path)


def test_governance_release_manifest_hashes_governed_assets(tmp_path):
    store, registry_path, provenance_path = _fixture(tmp_path)
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(json.dumps(_policy().to_dict()), encoding="utf-8")
    report = evaluate_governance(
        store.manifest_path,
        _policy(),
        registry_path,
        provenance_registry_path=provenance_path,
    )

    release = build_governance_release_manifest(
        report,
        manifest_path=store.manifest_path,
        policy_path=policy_path,
        baseline_registry_path=registry_path,
        provenance_registry_path=provenance_path,
    )

    assert release.manifest_sha256
    assert release.policy_sha256
    assert release.provenance_registry_sha256
    assert release.baseline_registry_sha256
    assert release.governance_report_sha256
    assert release.governance_mode == "bootstrap"


def test_repository_governance_policy_is_bootstrap_until_real_review():
    root = Path(__file__).resolve().parents[2]
    report = evaluate_governance(
        root / "benchmark" / "corpus" / "manifest.json",
        BenchmarkGovernancePolicy.load(
            root / "benchmark" / "governance" / "policy.json"
        ),
        root / "benchmark" / "leaderboard" / "baselines" / "registry.json",
        provenance_registry_path=(
            root / "benchmark" / "corpus" / "provenance" / "registry.json"
        ),
    )

    assert report.ok is True
    assert report.mode == "bootstrap"
    assert report.reviewed_documents == 0
    assert report.reviewed_pages == 0
