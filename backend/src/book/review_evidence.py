"""Validate advisory AI code-review evidence without authorizing a GitHub merge.

Evidence fields are self-reported. Passing this validation is NOT equivalent
to trusted agent identity, independent review, or a GitHub APPROVED review.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_VERSION = "1"
KIND = "ai-advisory"
ASSESSMENTS = {"no_blocking_findings", "needs_changes", "inconclusive"}
SEVERITIES = {"info", "low", "medium", "high", "critical"}
CHECK_RESULTS = {"pass", "fail", "not_run"}
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path} must be a non-empty string")
    return value.strip()


def _record(value: Any, path: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return value


def _items(value: Any, path: str, *, nonempty: bool = False) -> List[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ValueError(f"{path} must be a {'non-empty ' if nonempty else ''}list")
    return value


def validate_review(
    value: Any,
    *,
    expected_repo: Optional[str] = None,
    expected_pr: Optional[int] = None,
    expected_head: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate syntax, declared provenance and optional PR/head pin.

    This cannot authenticate providers, models, human review, or actual
    independence of separately claimed agent executions.
    """
    report = _record(value, "report")
    if report.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported advisory review schema_version")
    if report.get("kind") != KIND:
        raise ValueError("kind must be ai-advisory (not a GitHub approval)")

    repository = _text(report.get("repository"), "repository")
    if repository.count("/") != 1:
        raise ValueError("repository must be owner/name")
    number = report.get("pull_request")
    if isinstance(number, bool) or not isinstance(number, int) or number < 1:
        raise ValueError("pull_request must be a positive integer")
    head = _text(report.get("head_sha"), "head_sha")
    if not SHA_PATTERN.fullmatch(head):
        raise ValueError("head_sha must be a lowercase 40-character git SHA")
    if expected_repo is not None and repository != expected_repo:
        raise ValueError("repository does not match requested PR")
    if expected_pr is not None and number != expected_pr:
        raise ValueError("pull_request does not match requested PR")
    if expected_head is not None and head != expected_head:
        raise ValueError("stale or mismatched head_sha")

    day = _text(report.get("review_date"), "review_date")
    try:
        date.fromisoformat(day)
    except ValueError as exc:
        raise ValueError("review_date must be YYYY-MM-DD") from exc

    reviewer = _record(report.get("reviewer"), "reviewer")
    for key in ("agent_id", "provider", "model", "execution_id"):
        _text(reviewer.get(key), f"reviewer.{key}")
    if reviewer.get("identity_type") != "ai_agent":
        raise ValueError("reviewer.identity_type must be ai_agent")
    if report.get("human_approval_required") is not True:
        raise ValueError("human_approval_required must be true")

    assessment = _text(report.get("assessment"), "assessment")
    if assessment not in ASSESSMENTS:
        raise ValueError("Unknown advisory assessment")
    _text(report.get("summary"), "summary")

    findings = _items(report.get("findings"), "findings")
    severe = False
    for index, raw in enumerate(findings):
        finding = _record(raw, f"findings[{index}]")
        severity = _text(finding.get("severity"), f"findings[{index}].severity")
        if severity not in SEVERITIES:
            raise ValueError("Unknown finding severity")
        _text(finding.get("description"), f"findings[{index}].description")
        _text(finding.get("path"), f"findings[{index}].path")
        severe |= severity in {"high", "critical"}
    if severe and assessment == "no_blocking_findings":
        raise ValueError("High/critical findings cannot be marked no_blocking_findings")

    checks = _items(report.get("checks"), "checks", nonempty=True)
    for index, raw in enumerate(checks):
        check = _record(raw, f"checks[{index}]")
        _text(check.get("name"), f"checks[{index}].name")
        result = _text(check.get("result"), f"checks[{index}].result")
        if result not in CHECK_RESULTS:
            raise ValueError("Unknown check result")
        _text(check.get("evidence"), f"checks[{index}].evidence")
    for index, limitation in enumerate(
        _items(report.get("limitations"), "limitations", nonempty=True)
    ):
        _text(limitation, f"limitations[{index}]")

    return report


def summarize_reviews(reports: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate same-SHA advisory reports; never produce an approval count."""
    reports = [validate_review(value) for value in reports]
    if not reports:
        raise ValueError("At least one AI advisory review is required")
    first = reports[0]
    identities = set()
    executions = set()
    for report in reports:
        if (report["repository"], report["pull_request"], report["head_sha"]) != (
            first["repository"],
            first["pull_request"],
            first["head_sha"],
        ):
            raise ValueError("Cannot combine reviews for different PRs or head SHAs")
        reviewer = report["reviewer"]
        agent = reviewer["agent_id"].strip()
        execution = reviewer["execution_id"].strip()
        if agent in identities or execution in executions:
            raise ValueError("Duplicate declared agent or execution ID")
        identities.add(agent)
        executions.add(execution)
    return {
        "kind": KIND,
        "repository": first["repository"],
        "pull_request": first["pull_request"],
        "head_sha": first["head_sha"],
        "advisory_report_count": len(reports),
        "assessments": [item["assessment"] for item in reports],
        "declared_distinct_agents": len(identities),
        "independence_authenticated": False,
        "github_approvals_checked": False,
        "satisfies_governance_approval": False,
        "human_approval_required": True,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "aggregate"))
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--repo")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--head")
    args = parser.parse_args(argv)
    if args.command == "validate" and len(args.files) != 1:
        parser.error("validate requires exactly one file")
    try:
        reports = [
            validate_review(
                json.loads(path.read_text(encoding="utf-8")),
                expected_repo=args.repo,
                expected_pr=args.pr,
                expected_head=args.head,
            )
            for path in args.files
        ]
        if args.command == "aggregate":
            output = summarize_reviews(reports)
        else:
            review = reports[0]
            output = {
                "valid": True,
                "kind": KIND,
                "repository": review["repository"],
                "pull_request": review["pull_request"],
                "head_sha": review["head_sha"],
                "assessment": review["assessment"],
                "satisfies_governance_approval": False,
            }
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"AI review evidence invalid: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
