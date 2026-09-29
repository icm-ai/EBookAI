import json
import subprocess
from pathlib import Path

import pytest
from book.benchmark.change_control import (
    ChangeControlPolicy,
    ChangeInput,
    build_change_control_report,
    build_git_change_control_report,
    check_pr_approvals,
    classify_governed_path,
)
from book.benchmark.models import CorpusManifest
from book.benchmark.provenance import (
    ConsensusProvenanceRegistry,
    ConsensusReviewRecord,
    DocumentProvenanceRecord,
)
from book.benchmark.review_batch import (
    ReviewBatch,
    ReviewerAssignment,
    create_review_batch,
    review_batch_progress,
    validate_review_batch,
)
from book.benchmark.review_plan import ReviewPlan


def _policy() -> ChangeControlPolicy:
    return ChangeControlPolicy(
        required_approvals={
            "gold": 1,
            "provenance_registry": 1,
            "provenance_audit": 1,
            "baseline_snapshot": 1,
            "baseline_registry": 1,
            "governance_policy": 2,
            "change_control_policy": 2,
            "review_batch": 1,
        }
    )


def _gold(status: str, text: str = "Heading") -> bytes:
    return json.dumps(
        {
            "schema_version": "1",
            "document_id": "doc",
            "source_sha256": "a" * 64,
            "status": status,
            "annotated_by": "seed",
            "reviewed_by": "alice + bob" if status == "reviewed" else "",
            "notes": "",
            "pages": [
                {
                    "page_index": 0,
                    "tasks": ["headings"],
                    "elements": [
                        {
                            "id": "h1",
                            "type": "heading",
                            "text": text,
                            "level": 1,
                        }
                    ],
                }
            ],
        }
    ).encode()


def _manifest_and_plan(tmp_path: Path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "fixture",
                "documents": [
                    {
                        "id": "doc",
                        "title": "Fixture",
                        "source_url": "https://example.invalid/doc.pdf",
                        "license_url": "https://example.invalid/license",
                        "rights_basis": "test",
                        "sha256": "a" * 64,
                        "document_class": "test",
                        "language": "en",
                        "page_count": 3,
                        "complexity_tags": ["heading"],
                        "expected_capabilities": ["native_text"],
                        "redistributable": False,
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
                "corpus_id": "fixture",
                "targets": [
                    {
                        "document_id": "doc",
                        "page_index": 0,
                        "tasks": ["headings"],
                        "difficulty_tags": ["heading"],
                        "priority": "high",
                        "rationale": "first",
                    },
                    {
                        "document_id": "doc",
                        "page_index": 1,
                        "tasks": ["text"],
                        "difficulty_tags": ["dense"],
                        "priority": "medium",
                        "rationale": "second",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return CorpusManifest.load(manifest_path), ReviewPlan.load(plan_path)


def test_reviewer_assignment_requires_independent_identities():
    with pytest.raises(ValueError, match="must be distinct"):
        ReviewerAssignment(
            document_id="doc",
            page_index=0,
            reviewer_a="alice",
            reviewer_b="alice",
        )

    with pytest.raises(ValueError, match="Adjudicator"):
        ReviewerAssignment(
            document_id="doc",
            page_index=0,
            reviewer_a="alice",
            reviewer_b="bob",
            adjudicator="bob",
        )


def test_review_batch_creation_filters_targets_and_reports_progress(tmp_path):
    manifest, plan = _manifest_and_plan(tmp_path)
    batch = create_review_batch(
        batch_id="batch-1",
        created_by="maintainer",
        reviewer_a="alice",
        reviewer_b="bob",
        adjudicator="carol",
        priorities=["high"],
        plan=plan,
        manifest=manifest,
    )

    assert len(batch.assignments) == 1
    assert batch.assignments[0].page_index == 0
    validate_review_batch(batch, plan, manifest)

    registry = ConsensusProvenanceRegistry(
        records=[
            DocumentProvenanceRecord(
                document_id="doc",
                source_sha256="a" * 64,
                current_gold_sha256="b" * 64,
                reviews=[
                    ConsensusReviewRecord(
                        page_index=0,
                        consensus_bundle_id="bundle",
                        audit_path="provenance/doc/audit.json",
                        audit_sha256="c" * 64,
                        reviewer_a="alice",
                        reviewer_b="bob",
                        adjudicators=("carol",),
                        published_at="2026-09-29T00:00:00+00:00",
                    )
                ],
            )
        ]
    )
    progress = review_batch_progress(batch, provenance_registry=registry)
    assert progress["reviewed"] == 1
    assert progress["assigned"] == 0
    assert progress["completion_ratio"] == 1.0


def test_review_batch_rejects_target_outside_review_plan(tmp_path):
    manifest, plan = _manifest_and_plan(tmp_path)
    batch = ReviewBatch(
        batch_id="bad",
        corpus_id="fixture",
        assignments=(
            ReviewerAssignment(
                document_id="doc",
                page_index=2,
                reviewer_a="alice",
                reviewer_b="bob",
            ),
        ),
        created_by="maintainer",
        created_at="2026-09-29T00:00:00+00:00",
    )

    with pytest.raises(ValueError, match="not in the review plan"):
        validate_review_batch(batch, plan, manifest)


@pytest.mark.parametrize(
    ("path", "category"),
    [
        ("benchmark/corpus/gold/doc.json", "gold"),
        ("benchmark/corpus/provenance/registry.json", "provenance_registry"),
        (
            "benchmark/corpus/provenance/doc/page.consensus-audit.json",
            "provenance_audit",
        ),
        (
            "benchmark/leaderboard/baselines/registry.json",
            "baseline_registry",
        ),
        (
            "benchmark/leaderboard/baselines/v1.json",
            "baseline_snapshot",
        ),
        ("benchmark/governance/policy.json", "governance_policy"),
        ("benchmark/governance/change-control.json", "change_control_policy"),
        ("benchmark/review-batches/batch-1.json", "review_batch"),
    ],
)
def test_governed_path_classification(path, category):
    assert classify_governed_path(path) == category


def test_draft_gold_change_does_not_require_consensus_provenance():
    report = build_change_control_report(
        [
            ChangeInput(
                path="benchmark/corpus/gold/doc.json",
                status="modified",
                before=_gold("draft", "Before"),
                after=_gold("draft", "After"),
            )
        ],
        policy=_policy(),
        base_ref="base",
        head_ref="head",
    )

    assert report.ok is True
    assert report.required_approvals == 1
    assert report.changes[0].details["after_status"] == "draft"


def test_reviewed_gold_change_requires_registry_and_canonical_audit():
    gold_change = ChangeInput(
        path="benchmark/corpus/gold/doc.json",
        status="modified",
        before=_gold("draft"),
        after=_gold("reviewed"),
    )
    report = build_change_control_report(
        [gold_change],
        policy=_policy(),
        base_ref="base",
        head_ref="head",
    )
    assert report.ok is False
    assert len(report.failures) == 2

    passing = build_change_control_report(
        [
            gold_change,
            ChangeInput(
                path="benchmark/corpus/provenance/registry.json",
                status="modified",
                before=b'{"schema_version":"1","records":[]}',
                after=b'{"schema_version":"1","records":[{}]}',
            ),
            ChangeInput(
                path=(
                    "benchmark/corpus/provenance/doc/"
                    "page-0000-bundle.consensus-audit.json"
                ),
                status="added",
                before=None,
                after=b"{}",
            ),
        ],
        policy=_policy(),
        base_ref="base",
        head_ref="head",
    )
    assert passing.ok is True


def test_baseline_snapshot_requires_registry_change():
    report = build_change_control_report(
        [
            ChangeInput(
                path="benchmark/leaderboard/baselines/v1.json",
                status="added",
                before=None,
                after=b"{}",
            )
        ],
        policy=_policy(),
        base_ref="base",
        head_ref="head",
    )

    assert report.ok is False
    assert report.failures == (
        "reviewed baseline snapshot change requires baseline registry change",
    )


def test_baseline_registry_validates_active_snapshot_hash():
    snapshot = b'{"schema_version":"1","payload":"stable"}'
    digest = __import__("hashlib").sha256(snapshot).hexdigest()
    registry = json.dumps(
        {
            "schema_version": "1",
            "active_baseline_id": "v1",
            "baselines": [
                {
                    "baseline_id": "v1",
                    "path": "v1.json",
                    "sha256": digest,
                    "created_at": "2026-09-29T00:00:00+00:00",
                    "manifest_sha256": "m",
                    "gold_sha256": {},
                }
            ],
        }
    ).encode()

    def loader(path: str):
        if path.endswith("registry.json"):
            return registry
        if path.endswith("v1.json"):
            return snapshot
        return None

    report = build_change_control_report(
        [
            ChangeInput(
                path="benchmark/leaderboard/baselines/registry.json",
                status="modified",
                before=b"{}",
                after=registry,
            ),
            ChangeInput(
                path="benchmark/leaderboard/baselines/v1.json",
                status="added",
                before=None,
                after=snapshot,
            ),
        ],
        policy=_policy(),
        base_ref="base",
        head_ref="head",
        head_loader=loader,
    )
    assert report.ok is True


def test_governance_policy_change_requires_two_independent_approvals():
    report = build_change_control_report(
        [
            ChangeInput(
                path="benchmark/governance/policy.json",
                status="modified",
                before=b'{"maximum_metric_regression":0.02}',
                after=b'{"maximum_metric_regression":0.03}',
            )
        ],
        policy=_policy(),
        base_ref="base",
        head_ref="head",
    )

    assert report.required_approvals == 2
    assert "regression or coverage budgets" in report.warnings[0]

    reviews = [
        {"id": 1, "state": "APPROVED", "user": {"login": "author"}},
        {"id": 2, "state": "APPROVED", "user": {"login": "alice"}},
        {"id": 3, "state": "APPROVED", "user": {"login": "bob"}},
    ]
    approval = check_pr_approvals(
        report,
        reviews=reviews,
        pr_author="author",
        exclude_pr_author=True,
    )
    assert approval.ok is True
    assert approval.approvers == ("alice", "bob")


def test_latest_review_state_controls_approval_and_author_is_excluded():
    report = build_change_control_report(
        [
            ChangeInput(
                path="benchmark/review-batches/batch.json",
                status="added",
                before=None,
                after=b"{}",
            )
        ],
        policy=_policy(),
        base_ref="base",
        head_ref="head",
    )
    approval = check_pr_approvals(
        report,
        reviews=[
            {"id": 1, "state": "APPROVED", "user": {"login": "alice"}},
            {"id": 2, "state": "CHANGES_REQUESTED", "user": {"login": "alice"}},
            {"id": 3, "state": "APPROVED", "user": {"login": "author"}},
        ],
        pr_author="author",
    )

    assert approval.ok is False
    assert approval.approvers == ()
    assert "0 < required 1" in approval.failures[0]


def test_git_change_report_reads_exact_base_and_head_bytes(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, stdout=subprocess.PIPE)
    subprocess.run(
        ["git", "config", "user.email", "test@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=repo,
        check=True,
    )
    policy_dir = repo / "benchmark" / "governance"
    policy_dir.mkdir(parents=True)
    policy_file = policy_dir / "policy.json"
    policy_file.write_text(
        '{"schema_version":"1","maximum_metric_regression":0.02}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "base"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    policy_file.write_text(
        '{"schema_version":"1","maximum_metric_regression":0.03}\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", "head"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    ).stdout.strip()

    report = build_git_change_control_report(
        repo,
        base_ref=base,
        head_ref=head,
        policy=_policy(),
    )

    assert len(report.changes) == 1
    assert report.changes[0].category == "governance_policy"
    assert report.changes[0].before_sha256 != report.changes[0].after_sha256
    assert report.required_approvals == 2
