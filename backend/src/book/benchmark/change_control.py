"""PR-oriented change control for governed benchmark assets."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

CHANGE_CONTROL_SCHEMA_VERSION = "1"

GOVERNED_PREFIXES: Tuple[str, ...] = (
    "benchmark/corpus/gold/",
    "benchmark/corpus/provenance/",
    "benchmark/governance/history/",
    "benchmark/leaderboard/baselines/",
    "benchmark/review-batches/",
)
GOVERNANCE_ENGINE_FILES: Tuple[str, ...] = (
    ".github/workflows/benchmark-change-control.yml",
    ".github/workflows/ci.yml",
    "backend/src/book/benchmark/baseline.py",
    "backend/src/book/benchmark/change_control.py",
    "backend/src/book/benchmark/consensus.py",
    "backend/src/book/benchmark/governance.py",
    "backend/src/book/benchmark/provenance.py",
)

GOVERNED_FILES: Tuple[str, ...] = (
    "benchmark/corpus/manifest.json",
    "benchmark/corpus/review-plan.json",
    "benchmark/governance/policy.json",
    "benchmark/governance/change-control.json",
    *GOVERNANCE_ENGINE_FILES,
)


def _sha256(value: Optional[bytes]) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(value).hexdigest()


def classify_governed_path(path: str) -> Optional[str]:
    normalized = path.replace("\\", "/")
    if normalized in GOVERNANCE_ENGINE_FILES:
        return "governance_engine"
    if normalized == "benchmark/corpus/manifest.json":
        return "corpus_manifest"
    if normalized == "benchmark/corpus/review-plan.json":
        return "review_plan"
    if normalized.startswith("benchmark/corpus/gold/") and normalized.endswith(".json"):
        return "gold"
    if normalized == "benchmark/corpus/provenance/registry.json":
        return "provenance_registry"
    if normalized.startswith("benchmark/corpus/provenance/"):
        return "provenance_audit"
    if normalized == "benchmark/leaderboard/baselines/registry.json":
        return "baseline_registry"
    if normalized.startswith(
        "benchmark/leaderboard/baselines/"
    ) and normalized.endswith(".json"):
        return "baseline_snapshot"
    if normalized == "benchmark/governance/policy.json":
        return "governance_policy"
    if normalized == "benchmark/governance/change-control.json":
        return "change_control_policy"
    if normalized.startswith("benchmark/governance/history/") and normalized.endswith(
        ".json"
    ):
        return "change_history"
    if normalized.startswith("benchmark/review-batches/") and normalized.endswith(
        ".json"
    ):
        return "review_batch"
    return None


@dataclass(frozen=True)
class ChangeControlPolicy:
    required_approvals: Dict[str, int]
    require_provenance_for_reviewed_gold: bool = True
    require_baseline_registry_for_snapshot: bool = True
    exclude_pr_author_approval: bool = True
    schema_version: str = CHANGE_CONTROL_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != CHANGE_CONTROL_SCHEMA_VERSION:
            raise ValueError("Unsupported benchmark change-control policy schema")
        if any(value < 0 for value in self.required_approvals.values()):
            raise ValueError("Required approval counts must be >= 0")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ChangeControlPolicy":
        return cls(
            schema_version=str(value.get("schema_version", "")),
            required_approvals={
                str(key): int(count)
                for key, count in dict(value.get("required_approvals", {})).items()
            },
            require_provenance_for_reviewed_gold=bool(
                value.get("require_provenance_for_reviewed_gold", True)
            ),
            require_baseline_registry_for_snapshot=bool(
                value.get("require_baseline_registry_for_snapshot", True)
            ),
            exclude_pr_author_approval=bool(
                value.get("exclude_pr_author_approval", True)
            ),
        )

    @classmethod
    def load(cls, path: Path) -> "ChangeControlPolicy":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Change-control policy root must be an object")
        return cls.from_dict(payload)

    def approvals_for(self, category: str) -> int:
        return int(self.required_approvals.get(category, 0))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "required_approvals": dict(sorted(self.required_approvals.items())),
            "require_provenance_for_reviewed_gold": (
                self.require_provenance_for_reviewed_gold
            ),
            "require_baseline_registry_for_snapshot": (
                self.require_baseline_registry_for_snapshot
            ),
            "exclude_pr_author_approval": self.exclude_pr_author_approval,
        }


@dataclass(frozen=True)
class ChangeInput:
    path: str
    status: str
    before: Optional[bytes]
    after: Optional[bytes]


@dataclass(frozen=True)
class GovernedChange:
    path: str
    status: str
    category: str
    before_sha256: Optional[str]
    after_sha256: Optional[str]
    required_approvals: int
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "category": self.category,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
            "required_approvals": self.required_approvals,
            "details": self.details,
        }


@dataclass(frozen=True)
class ChangeControlReport:
    base_ref: str
    head_ref: str
    changes: Tuple[GovernedChange, ...]
    required_approvals: int
    failures: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()
    schema_version: str = CHANGE_CONTROL_SCHEMA_VERSION

    @property
    def changed(self) -> bool:
        return bool(self.changes)

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "changed": self.changed,
            "required_approvals": self.required_approvals,
            "changes": [item.to_dict() for item in self.changes],
            "failures": list(self.failures),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class ChangeHistoryRecord:
    change_id: str
    merged_commit: str
    base_ref: str
    head_ref: str
    report_sha256: str
    governance_release_sha256: Optional[str]
    governed_paths: Tuple[str, ...]
    categories: Tuple[str, ...]
    approvers: Tuple[str, ...]
    recorded_by: str
    recorded_at: str
    schema_version: str = CHANGE_CONTROL_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "change_id": self.change_id,
            "merged_commit": self.merged_commit,
            "base_ref": self.base_ref,
            "head_ref": self.head_ref,
            "report_sha256": self.report_sha256,
            "governance_release_sha256": self.governance_release_sha256,
            "governed_paths": list(self.governed_paths),
            "categories": list(self.categories),
            "approvers": list(self.approvers),
            "recorded_by": self.recorded_by,
            "recorded_at": self.recorded_at,
        }


@dataclass(frozen=True)
class ApprovalCheck:
    required: int
    approvers: Tuple[str, ...]
    failures: Tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "required": self.required,
            "approvers": list(self.approvers),
            "failures": list(self.failures),
        }


def _json(value: Optional[bytes]) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    try:
        payload = json.loads(value.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _semantic_details(
    category: str, before: Optional[bytes], after: Optional[bytes]
) -> Dict[str, Any]:
    left = _json(before)
    right = _json(after)
    if category == "gold":
        return {
            "document_id": (right or left or {}).get("document_id"),
            "before_status": (left or {}).get("status"),
            "after_status": (right or {}).get("status"),
            "before_pages": [
                item.get("page_index") for item in (left or {}).get("pages", [])
            ],
            "after_pages": [
                item.get("page_index") for item in (right or {}).get("pages", [])
            ],
            "before_reviewed_by": (left or {}).get("reviewed_by"),
            "after_reviewed_by": (right or {}).get("reviewed_by"),
        }
    if category == "baseline_registry":
        return {
            "before_active": (left or {}).get("active_baseline_id"),
            "after_active": (right or {}).get("active_baseline_id"),
            "before_versions": len((left or {}).get("baselines", [])),
            "after_versions": len((right or {}).get("baselines", [])),
        }
    if category in {"governance_policy", "change_control_policy"}:
        left = left or {}
        right = right or {}
        keys = sorted(set(left) | set(right))
        return {
            "changed_keys": [key for key in keys if left.get(key) != right.get(key)]
        }
    if category == "review_plan":
        return {
            "before_targets": len((left or {}).get("targets", [])),
            "after_targets": len((right or {}).get("targets", [])),
        }
    if category == "review_batch":
        return {
            "batch_id": (right or left or {}).get("batch_id"),
            "before_assignments": len((left or {}).get("assignments", [])),
            "after_assignments": len((right or {}).get("assignments", [])),
        }
    if category == "corpus_manifest":
        return {
            "before_documents": len((left or {}).get("documents", [])),
            "after_documents": len((right or {}).get("documents", [])),
        }
    return {}


def _reviewed_gold_document(change: ChangeInput) -> Optional[str]:
    before = _json(change.before) or {}
    after = _json(change.after) or {}
    if before.get("status") != "reviewed" and after.get("status") != "reviewed":
        return None
    return (
        str(after.get("document_id") or before.get("document_id") or "").strip() or None
    )


def build_change_control_report(
    inputs: Sequence[ChangeInput],
    *,
    policy: ChangeControlPolicy,
    base_ref: str,
    head_ref: str,
    head_loader: Optional[Callable[[str], Optional[bytes]]] = None,
) -> ChangeControlReport:
    changes: List[GovernedChange] = []
    relevant_inputs: List[ChangeInput] = []
    for item in inputs:
        category = classify_governed_path(item.path)
        if category is None:
            continue
        relevant_inputs.append(item)
        changes.append(
            GovernedChange(
                path=item.path,
                status=item.status,
                category=category,
                before_sha256=_sha256(item.before),
                after_sha256=_sha256(item.after),
                required_approvals=policy.approvals_for(category),
                details=_semantic_details(category, item.before, item.after),
            )
        )

    failures: List[str] = []
    warnings: List[str] = []
    changed_paths = {item.path.replace("\\", "/") for item in relevant_inputs}
    categories = {change.category for change in changes}

    if policy.require_provenance_for_reviewed_gold:
        for item in relevant_inputs:
            if classify_governed_path(item.path) != "gold":
                continue
            document_id = _reviewed_gold_document(item)
            if document_id is None:
                continue
            if "benchmark/corpus/provenance/registry.json" not in changed_paths:
                failures.append(
                    f"{item.path}: reviewed gold change requires provenance registry change"
                )
            audit_prefix = f"benchmark/corpus/provenance/{document_id}/"
            if not any(
                path.startswith(audit_prefix) and path.endswith(".consensus-audit.json")
                for path in changed_paths
            ):
                failures.append(
                    f"{item.path}: reviewed gold change requires a canonical consensus audit"
                )

    if (
        policy.require_baseline_registry_for_snapshot
        and "baseline_snapshot" in categories
        and "benchmark/leaderboard/baselines/registry.json" not in changed_paths
    ):
        failures.append(
            "reviewed baseline snapshot change requires baseline registry change"
        )

    if "baseline_registry" in categories and head_loader is not None:
        raw_registry = head_loader("benchmark/leaderboard/baselines/registry.json")
        registry = _json(raw_registry)
        if registry is None:
            failures.append("baseline registry is not valid JSON")
        else:
            entries = {
                str(item.get("baseline_id")): item
                for item in registry.get("baselines", [])
                if isinstance(item, dict)
            }
            active = registry.get("active_baseline_id")
            if active is not None and str(active) not in entries:
                failures.append(
                    f"active baseline {active!r} is not present in baseline registry"
                )
            for baseline_id, entry in entries.items():
                path = str(entry.get("path", ""))
                expected = str(entry.get("sha256", ""))
                if not path or not expected:
                    failures.append(
                        f"baseline registry entry {baseline_id!r} is incomplete"
                    )
                    continue
                full_path = f"benchmark/leaderboard/baselines/{path}"
                payload = head_loader(full_path)
                if payload is None:
                    failures.append(
                        f"baseline registry entry {baseline_id!r} points to missing {full_path}"
                    )
                    continue
                actual = hashlib.sha256(payload).hexdigest()
                if actual != expected:
                    failures.append(
                        f"baseline registry entry {baseline_id!r} SHA does not match {full_path}"
                    )

    if "governance_policy" in categories:
        warnings.append(
            "governance policy changed: regression or coverage budgets may be altered"
        )
    if "change_control_policy" in categories:
        warnings.append(
            "change-control policy changed: approval requirements may be altered"
        )
    if "corpus_manifest" in categories:
        warnings.append(
            "corpus manifest changed: source inventory or source pins require review"
        )

    required = max((change.required_approvals for change in changes), default=0)
    return ChangeControlReport(
        base_ref=base_ref,
        head_ref=head_ref,
        changes=tuple(sorted(changes, key=lambda item: item.path)),
        required_approvals=required,
        failures=tuple(sorted(set(failures))),
        warnings=tuple(sorted(set(warnings))),
    )


def check_pr_approvals(
    report: ChangeControlReport,
    *,
    reviews: Iterable[Dict[str, Any]],
    pr_author: str,
    exclude_pr_author: bool = True,
) -> ApprovalCheck:
    latest: Dict[str, Dict[str, Any]] = {}
    for review in reviews:
        user = review.get("user")
        login = str(user.get("login", "") if isinstance(user, dict) else "").strip()
        if not login:
            continue
        current = latest.get(login)
        review_id = int(review.get("id", 0) or 0)
        current_id = int(current.get("id", 0) or 0) if current is not None else -1
        if current is None or review_id >= current_id:
            latest[login] = review

    approvers = []
    for login, review in latest.items():
        if exclude_pr_author and login == pr_author:
            continue
        if str(review.get("state", "")).upper() == "APPROVED":
            approvers.append(login)
    approvers.sort()
    failures: List[str] = []
    if len(approvers) < report.required_approvals:
        failures.append(
            f"independent approvals {len(approvers)} < required {report.required_approvals}"
        )
    return ApprovalCheck(
        required=report.required_approvals,
        approvers=tuple(approvers),
        failures=tuple(failures),
    )


def _git(repo_root: Path, arguments: Sequence[str], *, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise ValueError(
            "git command failed: "
            + result.stderr.decode("utf-8", errors="replace").strip()
        )
    return result.stdout


def _git_show(repo_root: Path, ref: str, path: str) -> Optional[bytes]:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def collect_git_change_inputs(
    repo_root: Path,
    *,
    base_ref: str,
    head_ref: str,
) -> Tuple[ChangeInput, ...]:
    repo_root = Path(repo_root).resolve()
    pathspecs = list(GOVERNED_FILES) + list(GOVERNED_PREFIXES)
    output = _git(
        repo_root,
        [
            "diff",
            "--name-status",
            "--find-renames",
            base_ref,
            head_ref,
            "--",
            *pathspecs,
        ],
    ).decode("utf-8")
    changes: List[ChangeInput] = []
    for raw_line in output.splitlines():
        if not raw_line.strip():
            continue
        parts = raw_line.split("\t")
        code = parts[0]
        if code.startswith("R") and len(parts) >= 3:
            old_path, new_path = parts[1], parts[2]
            if classify_governed_path(old_path) is not None:
                changes.append(
                    ChangeInput(
                        path=old_path,
                        status="deleted",
                        before=_git_show(repo_root, base_ref, old_path),
                        after=None,
                    )
                )
            if classify_governed_path(new_path) is not None:
                changes.append(
                    ChangeInput(
                        path=new_path,
                        status="added",
                        before=None,
                        after=_git_show(repo_root, head_ref, new_path),
                    )
                )
            continue
        if len(parts) < 2:
            continue
        path = parts[1]
        if classify_governed_path(path) is None:
            continue
        status = {
            "A": "added",
            "D": "deleted",
            "M": "modified",
        }.get(code[:1], "modified")
        changes.append(
            ChangeInput(
                path=path,
                status=status,
                before=(
                    None if status == "added" else _git_show(repo_root, base_ref, path)
                ),
                after=(
                    None
                    if status == "deleted"
                    else _git_show(repo_root, head_ref, path)
                ),
            )
        )
    return tuple(changes)


def build_git_change_control_report(
    repo_root: Path,
    *,
    base_ref: str,
    head_ref: str,
    policy: ChangeControlPolicy,
) -> ChangeControlReport:
    repo_root = Path(repo_root).resolve()
    inputs = collect_git_change_inputs(
        repo_root,
        base_ref=base_ref,
        head_ref=head_ref,
    )

    def head_loader(path: str) -> Optional[bytes]:
        return _git_show(repo_root, head_ref, path)

    return build_change_control_report(
        inputs,
        policy=policy,
        base_ref=base_ref,
        head_ref=head_ref,
        head_loader=head_loader,
    )


def render_change_control_markdown(
    report: ChangeControlReport,
    *,
    approval: Optional[ApprovalCheck] = None,
) -> str:
    lines = [
        "<!-- ebookai-benchmark-change-control -->",
        "# Benchmark Change Control",
        "",
        f"- Base: `{report.base_ref}`",
        f"- Head: `{report.head_ref}`",
        f"- Governed changes: {len(report.changes)}",
        f"- Required independent approvals: **{report.required_approvals}**",
    ]
    if approval is not None:
        approver_text = ", ".join(f"`{item}`" for item in approval.approvers) or "none"
        lines.extend(
            [
                f"- Current approvers: {approver_text}",
                f"- Approval status: **{'pass' if approval.ok else 'fail'}**",
            ]
        )
    lines.append("")

    if report.failures:
        lines.extend(["## Blocking invariant failures", ""])
        lines.extend(f"- {item}" for item in report.failures)
        lines.append("")
    if approval is not None and approval.failures:
        lines.extend(["## Approval failures", ""])
        lines.extend(f"- {item}" for item in approval.failures)
        lines.append("")
    if report.warnings:
        lines.extend(["## Review warnings", ""])
        lines.extend(f"- {item}" for item in report.warnings)
        lines.append("")

    if not report.changes:
        lines.extend(
            [
                "No governed benchmark assets changed in this PR.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "## Governed changes",
            "",
            "| Path | Category | Status | Approvals | Semantic summary |",
            "|---|---|---|---:|---|",
        ]
    )
    for change in report.changes:
        details = ", ".join(
            f"{key}={value}"
            for key, value in change.details.items()
            if value not in (None, [], "")
        )
        lines.append(
            "| "
            + " | ".join(
                [
                    f"`{change.path}`",
                    change.category,
                    change.status,
                    str(change.required_approvals),
                    (details or "—").replace("|", "\\|"),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def write_change_control_report(
    report: ChangeControlReport,
    output_dir: Path,
) -> Tuple[Path, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "change-report.json"
    markdown_path = output_dir / "change-report.md"
    json_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_change_control_markdown(report),
        encoding="utf-8",
    )
    return json_path, markdown_path


def build_change_history_record(
    *,
    report: ChangeControlReport,
    approval: ApprovalCheck,
    report_bytes: bytes,
    merged_commit: str,
    recorded_by: str,
    governance_release_bytes: Optional[bytes] = None,
) -> ChangeHistoryRecord:
    if not report.ok:
        raise ValueError(
            "Cannot record change history for a structurally invalid report"
        )
    if not approval.ok:
        raise ValueError("Cannot record change history without required approvals")
    if not merged_commit.strip():
        raise ValueError("Merged commit must not be empty")
    if not recorded_by.strip():
        raise ValueError("History recorded_by must not be empty")
    report_sha = hashlib.sha256(report_bytes).hexdigest()
    governance_sha = (
        hashlib.sha256(governance_release_bytes).hexdigest()
        if governance_release_bytes is not None
        else None
    )
    change_id = f"{merged_commit[:12]}-{report_sha[:12]}"
    return ChangeHistoryRecord(
        change_id=change_id,
        merged_commit=merged_commit,
        base_ref=report.base_ref,
        head_ref=report.head_ref,
        report_sha256=report_sha,
        governance_release_sha256=governance_sha,
        governed_paths=tuple(change.path for change in report.changes),
        categories=tuple(sorted({change.category for change in report.changes})),
        approvers=approval.approvers,
        recorded_by=recorded_by,
        recorded_at=datetime.now(timezone.utc).isoformat(),
    )


def write_change_history_record(
    record: ChangeHistoryRecord,
    path: Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n"
    if path.is_file():
        existing = path.read_text(encoding="utf-8")
        if existing != content:
            raise ValueError(f"Change history record is immutable: {path}")
        return path
    path.write_text(content, encoding="utf-8")
    return path
