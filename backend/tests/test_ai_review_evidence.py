"""Advisory review evidence must not substitute for GitHub governance approvals."""

from copy import deepcopy

import pytest

from book.review_evidence import main, summarize_reviews, validate_review


def _report():
    return {
        "schema_version": "1",
        "kind": "ai-advisory",
        "repository": "icm-ai/EBookAI",
        "pull_request": 8,
        "head_sha": "93d666839a8b4465f425a95066c5f2345364c715",
        "review_date": "2026-10-18",
        "reviewer": {
            "identity_type": "ai_agent",
            "agent_id": "agent-a",
            "provider": "provider-a",
            "model": "model-a",
            "execution_id": "execution-a",
        },
        "assessment": "no_blocking_findings",
        "summary": "Read-only diff review with provenance.",
        "human_approval_required": True,
        "checks": [
            {
                "name": "CI",
                "result": "pass",
                "evidence": (
                    "https://github.com/icm-ai/EBookAI/"
                    "actions/runs/39082216317"
                ),
            }
        ],
        "findings": [],
        "limitations": [
            "Review evidence is self-reported and does not prove independence."
        ],
    }


def test_review_evidence_validates_pinned_head():
    report = _report()
    validated = validate_review(
        report,
        expected_repo="icm-ai/EBookAI",
        expected_pr=8,
        expected_head=report["head_sha"],
    )
    assert validated is report


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("kind", "github-approval"),
        ("schema_version", "999"),
        ("human_approval_required", False),
        ("pull_request", True),
        ("head_sha", "short"),
        ("assessment", "APPROVED"),
        ("checks", []),
        ("limitations", []),
        ("review_date", "invalid-date"),
    ],
)
def test_review_evidence_rejects_invalid_core_fields(field, value):
    report = _report()
    report[field] = value
    with pytest.raises(ValueError):
        validate_review(report)


def test_review_evidence_rejects_mismatched_sha():
    with pytest.raises(ValueError, match="stale or mismatched"):
        validate_review(_report(), expected_head="a" * 40)


def test_review_evidence_rejects_missing_ai_identity():
    report = _report()
    report["reviewer"]["identity_type"] = "human"
    with pytest.raises(ValueError, match="identity_type"):
        validate_review(report)


def test_review_evidence_rejects_unacknowledged_critical_finding():
    report = _report()
    report["findings"] = [
        {
            "path": ".github/workflows/benchmark-change-control.yml",
            "severity": "critical",
            "description": "A serious issue remains.",
        }
    ]
    with pytest.raises(ValueError, match="High/critical"):
        validate_review(report)
    report["assessment"] = "needs_changes"
    assert validate_review(report) == report


def test_advisory_aggregate_never_claims_approval():
    first = _report()
    second = deepcopy(first)
    second["reviewer"].update(
        {
            "agent_id": "agent-b",
            "provider": "provider-b",
            "model": "model-b",
            "execution_id": "execution-b",
        }
    )
    result = summarize_reviews([first, second])
    assert result["advisory_report_count"] == 2
    assert result["declared_distinct_agents"] == 2
    assert result["independence_authenticated"] is False
    assert result["satisfies_governance_approval"] is False
    assert result["github_approvals_checked"] is False
    assert result["human_approval_required"] is True


@pytest.mark.parametrize("duplicate_field", ["agent_id", "execution_id"])
def test_aggregate_rejects_duplicate_declared_identity(duplicate_field):
    first = _report()
    second = deepcopy(first)
    second["reviewer"]["agent_id"] = "agent-b"
    second["reviewer"]["execution_id"] = "execution-b"
    second["reviewer"][duplicate_field] = first["reviewer"][duplicate_field]
    with pytest.raises(ValueError, match="Duplicate declared"):
        summarize_reviews([first, second])


def test_aggregate_rejects_other_commit_or_pr():
    first = _report()
    second = deepcopy(first)
    second["reviewer"]["agent_id"] = "agent-b"
    second["reviewer"]["execution_id"] = "execution-b"
    second["head_sha"] = "a" * 40
    with pytest.raises(ValueError, match="different PRs or head SHAs"):
        summarize_reviews([first, second])


def test_cli_validation_and_invalid_input(tmp_path, capsys):
    import json

    report = _report()
    file_path = tmp_path / "review.json"
    file_path.write_text(json.dumps(report), encoding="utf-8")

    exit_code = main(
        [
            "validate",
            str(file_path),
            "--repo",
            "icm-ai/EBookAI",
            "--pr",
            "8",
            "--head",
            report["head_sha"],
        ]
    )
    assert exit_code == 0
    assert '"satisfies_governance_approval": false' in capsys.readouterr().out

    assert main(["validate", str(file_path), "--head", "a" * 40]) == 2
    assert "stale or mismatched" in capsys.readouterr().err
