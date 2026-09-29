import base64
import hashlib
import json
from pathlib import Path

import fitz
import pytest
from book.benchmark.baseline import ReviewedBaselineRegistry
from book.benchmark.campaign import (
    CampaignTarget,
    ReviewedGoldCampaign,
    activate_strict_baseline,
    create_campaign_batch,
    generate_review_packages,
    inspect_campaign,
)
from book.benchmark.consensus import GoldConsensusStore
from book.benchmark.governance import BenchmarkGovernancePolicy
from book.benchmark.leaderboard import LeaderboardPolicy
from book.benchmark.models import CorpusManifest
from book.benchmark.provenance import ConsensusProvenanceRegistry
from book.benchmark.review_batch import ReviewBatch
from book.benchmark.review_plan import ReviewPlan
from book.benchmark.review_workbench import GoldReviewStore


def _write_pdf(path: Path) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "1 Introduction")
    page.insert_text((72, 110), "Campaign fixture body text.")
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
                "notes": "campaign fixture",
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

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "campaign-fixture",
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

    plan_path = tmp_path / "review-plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "campaign-fixture",
                "targets": [
                    {
                        "document_id": "fixture",
                        "page_index": 0,
                        "tasks": ["headings", "reading_order"],
                        "difficulty_tags": ["heading"],
                        "priority": "high",
                        "rationale": "campaign fixture",
                    }
                ],
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

    baseline_dir = tmp_path / "baselines"
    baseline_dir.mkdir()
    baseline_registry_path = baseline_dir / "registry.json"
    baseline_registry_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "active_baseline_id": None,
                "baselines": [],
            }
        ),
        encoding="utf-8",
    )

    leaderboard_policy_path = tmp_path / "leaderboard-policy.json"
    leaderboard_policy_path.write_text(
        json.dumps(LeaderboardPolicy().to_dict()),
        encoding="utf-8",
    )

    governance_policy_path = tmp_path / "governance-policy.json"
    governance_policy_path.write_text(
        json.dumps(
            BenchmarkGovernancePolicy(
                ci_backends=("pymupdf",),
                minimum_reviewed_documents=1,
                minimum_reviewed_pages=1,
                minimum_eligible_ci_backends=1,
                minimum_metrics_per_backend=1,
                maximum_metric_regression=0.02,
            ).to_dict()
        ),
        encoding="utf-8",
    )

    campaign = ReviewedGoldCampaign(
        campaign_id="first-reviewed-fixture",
        corpus_id="campaign-fixture",
        targets=(
            CampaignTarget(
                document_id="fixture",
                page_index=0,
            ),
        ),
        review_backend="pymupdf",
        benchmark_backends=("pymupdf",),
        baseline_id="first-reviewed-fixture",
        baseline_filename="first-reviewed-fixture.json",
        description="fixture",
    )

    store = GoldReviewStore(
        manifest_path,
        plan_path,
        tmp_path / "cache",
        tmp_path / "workspace",
    )
    return {
        "campaign": campaign,
        "manifest_path": manifest_path,
        "plan_path": plan_path,
        "provenance_path": provenance_path,
        "baseline_registry_path": baseline_registry_path,
        "leaderboard_policy_path": leaderboard_policy_path,
        "governance_policy_path": governance_policy_path,
        "store": store,
    }


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


def _publish_from_packages(fixture, batch, tmp_path):
    packages = generate_review_packages(
        fixture["campaign"],
        batch,
        store=fixture["store"],
        output_dir=tmp_path / "packages",
    )
    assert packages["package_count"] == 2
    first_id = packages["packages"][0]["session_id"]
    second_id = packages["packages"][1]["session_id"]
    assert first_id != second_id
    assert (
        packages["packages"][0]["canonical_hash_at_open"]
        == packages["packages"][1]["canonical_hash_at_open"]
    )

    _confirm_all(fixture["store"], first_id, "alice")
    _confirm_all(fixture["store"], second_id, "bob")
    fixture["store"].promote(first_id, reviewer="alice")
    fixture["store"].promote(second_id, reviewer="bob")

    consensus = GoldConsensusStore(
        fixture["manifest_path"],
        fixture["store"],
        fixture["store"].workspace_dir,
    )
    bundle = consensus.create(first_id, second_id)
    consensus.publish(bundle.id)
    return packages


def test_repository_first_campaign_is_real_but_not_falsely_reviewed():
    root = Path(__file__).resolve().parents[2]
    campaign = ReviewedGoldCampaign.load(
        root / "benchmark" / "campaigns" / "first-reviewed-v1.json"
    )

    status = inspect_campaign(
        campaign,
        manifest_path=root / "benchmark" / "corpus" / "manifest.json",
        review_plan_path=root / "benchmark" / "corpus" / "review-plan.json",
        provenance_registry_path=(
            root / "benchmark" / "corpus" / "provenance" / "registry.json"
        ),
        baseline_registry_path=(
            root / "benchmark" / "leaderboard" / "baselines" / "registry.json"
        ),
        governance_policy_path=root / "benchmark" / "governance" / "policy.json",
    )

    assert campaign.campaign_id == "first-reviewed-v1"
    assert len(campaign.targets) == 1
    assert campaign.targets[0].document_id == "nist-eel-sp1500-101-v1"
    assert campaign.targets[0].page_index == 8
    assert status.ok is True
    assert status.state == "planned"
    assert status.reviewed_targets == 0
    assert status.targets[0]["annotation_status"] == "draft"
    assert status.active_baseline_id is None


def test_campaign_assignment_is_exact_and_requires_real_independent_reviewers(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = CorpusManifest.load(fixture["manifest_path"])
    plan = ReviewPlan.load(fixture["plan_path"])

    batch = create_campaign_batch(
        fixture["campaign"],
        manifest=manifest,
        plan=plan,
        created_by="maintainer",
        reviewer_a="alice",
        reviewer_b="bob",
        adjudicator="carol",
    )

    assert batch.batch_id == fixture["campaign"].campaign_id
    assert len(batch.assignments) == 1
    assert batch.assignments[0].reviewer_a == "alice"
    assert batch.assignments[0].reviewer_b == "bob"

    with pytest.raises(ValueError, match="must be distinct"):
        create_campaign_batch(
            fixture["campaign"],
            manifest=manifest,
            plan=plan,
            created_by="maintainer",
            reviewer_a="alice",
            reviewer_b="alice",
        )


def test_review_packages_create_independent_sessions_without_promoting_gold(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = CorpusManifest.load(fixture["manifest_path"])
    plan = ReviewPlan.load(fixture["plan_path"])
    batch = create_campaign_batch(
        fixture["campaign"],
        manifest=manifest,
        plan=plan,
        created_by="maintainer",
        reviewer_a="alice",
        reviewer_b="bob",
    )

    packages = generate_review_packages(
        fixture["campaign"],
        batch,
        store=fixture["store"],
        output_dir=tmp_path / "packages",
    )

    assert packages["package_count"] == 2
    assert {item["role"] for item in packages["packages"]} == {
        "reviewer_a",
        "reviewer_b",
    }
    assert (tmp_path / "packages" / "review-packages.json").is_file()
    for item in packages["packages"]:
        package_dir = (
            tmp_path
            / "packages"
            / "fixture"
            / "page-0000"
            / f"{item['role']}-{item['reviewer']}"
        )
        assert (package_dir / "source-page.png").is_file()
        assert (package_dir / "draft-gold.json").is_file()
        assert (package_dir / "parser-bookir.json").is_file()

    canonical = json.loads(
        (tmp_path / "gold" / "fixture.json").read_text(encoding="utf-8")
    )
    assert canonical["status"] == "draft"
    assert ConsensusProvenanceRegistry.load(fixture["provenance_path"]).records == []


def test_campaign_status_becomes_ready_only_after_real_consensus_publish(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = CorpusManifest.load(fixture["manifest_path"])
    plan = ReviewPlan.load(fixture["plan_path"])
    batch = create_campaign_batch(
        fixture["campaign"],
        manifest=manifest,
        plan=plan,
        created_by="maintainer",
        reviewer_a="alice",
        reviewer_b="bob",
    )

    assigned = inspect_campaign(
        fixture["campaign"],
        manifest_path=fixture["manifest_path"],
        review_plan_path=fixture["plan_path"],
        provenance_registry_path=fixture["provenance_path"],
        baseline_registry_path=fixture["baseline_registry_path"],
        governance_policy_path=fixture["governance_policy_path"],
        batch=batch,
    )
    assert assigned.state == "assigned"
    assert assigned.ready_for_activation is False

    _publish_from_packages(fixture, batch, tmp_path)

    ready = inspect_campaign(
        fixture["campaign"],
        manifest_path=fixture["manifest_path"],
        review_plan_path=fixture["plan_path"],
        provenance_registry_path=fixture["provenance_path"],
        baseline_registry_path=fixture["baseline_registry_path"],
        governance_policy_path=fixture["governance_policy_path"],
        batch=batch,
    )
    assert ready.ok is True
    assert ready.state == "ready_for_activation"
    assert ready.reviewed_targets == 1
    assert ready.targets[0]["reviewer_a"] == "alice"
    assert ready.targets[0]["reviewer_b"] == "bob"


def test_campaign_rejects_consensus_from_reviewers_outside_assignment(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = CorpusManifest.load(fixture["manifest_path"])
    plan = ReviewPlan.load(fixture["plan_path"])
    actual_batch = create_campaign_batch(
        fixture["campaign"],
        manifest=manifest,
        plan=plan,
        created_by="maintainer",
        reviewer_a="alice",
        reviewer_b="bob",
    )
    _publish_from_packages(fixture, actual_batch, tmp_path)

    wrong_batch = create_campaign_batch(
        fixture["campaign"],
        manifest=manifest,
        plan=plan,
        created_by="maintainer",
        reviewer_a="alice",
        reviewer_b="dave",
    )
    status = inspect_campaign(
        fixture["campaign"],
        manifest_path=fixture["manifest_path"],
        review_plan_path=fixture["plan_path"],
        provenance_registry_path=fixture["provenance_path"],
        baseline_registry_path=fixture["baseline_registry_path"],
        governance_policy_path=fixture["governance_policy_path"],
        batch=wrong_batch,
    )

    assert status.ok is False
    assert status.state == "blocked"
    assert "do not match campaign assignment" in status.failures[0]


def test_campaign_activation_creates_first_strict_reviewed_baseline(tmp_path):
    fixture = _fixture(tmp_path)
    manifest = CorpusManifest.load(fixture["manifest_path"])
    plan = ReviewPlan.load(fixture["plan_path"])
    batch = create_campaign_batch(
        fixture["campaign"],
        manifest=manifest,
        plan=plan,
        created_by="maintainer",
        reviewer_a="alice",
        reviewer_b="bob",
    )
    _publish_from_packages(fixture, batch, tmp_path)

    result = activate_strict_baseline(
        fixture["campaign"],
        batch,
        manifest_path=fixture["manifest_path"],
        review_plan_path=fixture["plan_path"],
        provenance_registry_path=fixture["provenance_path"],
        baseline_registry_path=fixture["baseline_registry_path"],
        leaderboard_policy_path=fixture["leaderboard_policy_path"],
        governance_policy_path=fixture["governance_policy_path"],
        cache_dir=tmp_path / "activation-cache",
        output_dir=tmp_path / "activation",
    )

    assert result.governance_status == "pass"
    assert result.governance_mode == "strict"
    assert result.reviewed_documents == 1
    assert result.reviewed_pages == 1
    registry = ReviewedBaselineRegistry.load(fixture["baseline_registry_path"])
    assert registry.active_baseline_id == fixture["campaign"].baseline_id
    assert (
        fixture["baseline_registry_path"].parent / fixture["campaign"].baseline_filename
    ).is_file()

    status = inspect_campaign(
        fixture["campaign"],
        manifest_path=fixture["manifest_path"],
        review_plan_path=fixture["plan_path"],
        provenance_registry_path=fixture["provenance_path"],
        baseline_registry_path=fixture["baseline_registry_path"],
        governance_policy_path=fixture["governance_policy_path"],
        batch=batch,
    )
    assert status.ok is True
    assert status.state == "strict"


def test_campaign_activation_rolls_back_if_strict_governance_rejects_baseline(
    tmp_path,
):
    fixture = _fixture(tmp_path)
    manifest = CorpusManifest.load(fixture["manifest_path"])
    plan = ReviewPlan.load(fixture["plan_path"])
    batch = create_campaign_batch(
        fixture["campaign"],
        manifest=manifest,
        plan=plan,
        created_by="maintainer",
        reviewer_a="alice",
        reviewer_b="bob",
    )
    _publish_from_packages(fixture, batch, tmp_path)

    fixture["governance_policy_path"].write_text(
        json.dumps(
            BenchmarkGovernancePolicy(
                ci_backends=("pymupdf",),
                minimum_reviewed_documents=1,
                minimum_reviewed_pages=2,
                minimum_eligible_ci_backends=1,
                minimum_metrics_per_backend=1,
                maximum_metric_regression=0.02,
            ).to_dict()
        ),
        encoding="utf-8",
    )
    registry_before = fixture["baseline_registry_path"].read_bytes()

    with pytest.raises(ValueError, match="Strict governance activation failed"):
        activate_strict_baseline(
            fixture["campaign"],
            batch,
            manifest_path=fixture["manifest_path"],
            review_plan_path=fixture["plan_path"],
            provenance_registry_path=fixture["provenance_path"],
            baseline_registry_path=fixture["baseline_registry_path"],
            leaderboard_policy_path=fixture["leaderboard_policy_path"],
            governance_policy_path=fixture["governance_policy_path"],
            cache_dir=tmp_path / "activation-cache",
            output_dir=tmp_path / "activation",
        )

    assert fixture["baseline_registry_path"].read_bytes() == registry_before
    assert (
        fixture["baseline_registry_path"].parent / fixture["campaign"].baseline_filename
    ).exists() is False
