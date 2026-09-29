"""Provenance-pinned snapshots for reviewed-only parser leaderboard baselines."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from book.benchmark.gold import load_gold_annotation
from book.benchmark.leaderboard import ParserLeaderboard
from book.benchmark.models import CorpusManifest

BASELINE_SCHEMA_VERSION = "1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ReviewedBaselineSnapshot:
    corpus_id: str
    manifest_sha256: str
    gold_sha256: Dict[str, str]
    leaderboard: ParserLeaderboard
    created_at: str
    schema_version: str = BASELINE_SCHEMA_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "created_at": self.created_at,
            "manifest_sha256": self.manifest_sha256,
            "gold_sha256": dict(sorted(self.gold_sha256.items())),
            "leaderboard": self.leaderboard.to_dict(),
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewedBaselineSnapshot":
        if str(value.get("schema_version", "")) != BASELINE_SCHEMA_VERSION:
            raise ValueError("Unsupported reviewed baseline schema")
        return cls(
            corpus_id=str(value["corpus_id"]),
            manifest_sha256=str(value["manifest_sha256"]),
            gold_sha256={
                str(key): str(digest)
                for key, digest in dict(value.get("gold_sha256", {})).items()
            },
            leaderboard=ParserLeaderboard.from_dict(value["leaderboard"]),
            created_at=str(value["created_at"]),
        )

    @classmethod
    def load(cls, path: Path) -> "ReviewedBaselineSnapshot":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Reviewed baseline root must be an object")
        return cls.from_dict(payload)


def build_reviewed_baseline(
    manifest_path: Path,
    leaderboard: ParserLeaderboard,
) -> ReviewedBaselineSnapshot:
    """Freeze an eligible reviewed-only leaderboard with exact gold provenance."""

    if leaderboard.policy.include_draft:
        raise ValueError("Reviewed baseline cannot include draft gold")
    if not any(entry.eligible for entry in leaderboard.entries):
        raise ValueError("Reviewed baseline requires at least one eligible backend")

    manifest_path = Path(manifest_path).resolve()
    manifest = CorpusManifest.load(manifest_path)
    if manifest.corpus_id != leaderboard.corpus_id:
        raise ValueError("Leaderboard corpus_id does not match the corpus manifest")

    root = manifest_path.parent
    gold_sha256: Dict[str, str] = {}
    for spec in manifest.documents:
        annotation = load_gold_annotation(manifest_path, spec)
        if annotation is None or annotation.status != "reviewed":
            continue
        if not spec.gold_annotations_path:
            continue
        path = (root / spec.gold_annotations_path).resolve()
        gold_sha256[spec.id] = _sha256(path)

    if not gold_sha256:
        raise ValueError("Reviewed baseline requires canonical reviewed gold")

    return ReviewedBaselineSnapshot(
        corpus_id=manifest.corpus_id,
        manifest_sha256=_sha256(manifest_path),
        gold_sha256=gold_sha256,
        leaderboard=leaderboard,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def write_reviewed_baseline(
    snapshot: ReviewedBaselineSnapshot,
    path: Path,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(snapshot.to_json() + "\n", encoding="utf-8")
    return path


def load_baseline_leaderboard(path: Path) -> ParserLeaderboard:
    """Load either a Milestone 15 leaderboard or Milestone 17 baseline snapshot."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Baseline root must be an object")
    if "leaderboard" in payload:
        return ReviewedBaselineSnapshot.from_dict(payload).leaderboard
    return ParserLeaderboard.from_dict(payload)


BASELINE_REGISTRY_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class ReviewedBaselineVersion:
    baseline_id: str
    path: str
    sha256: str
    created_at: str
    manifest_sha256: str
    gold_sha256: Dict[str, str]

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReviewedBaselineVersion":
        return cls(
            baseline_id=str(value["baseline_id"]),
            path=str(value["path"]),
            sha256=str(value["sha256"]),
            created_at=str(value["created_at"]),
            manifest_sha256=str(value["manifest_sha256"]),
            gold_sha256={
                str(key): str(digest)
                for key, digest in dict(value.get("gold_sha256", {})).items()
            },
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "path": self.path,
            "sha256": self.sha256,
            "created_at": self.created_at,
            "manifest_sha256": self.manifest_sha256,
            "gold_sha256": dict(sorted(self.gold_sha256.items())),
        }


@dataclass
class ReviewedBaselineRegistry:
    active_baseline_id: Optional[str] = None
    baselines: List[ReviewedBaselineVersion] = field(default_factory=list)
    schema_version: str = BASELINE_REGISTRY_SCHEMA_VERSION

    @classmethod
    def load(cls, path: Path) -> "ReviewedBaselineRegistry":
        path = Path(path)
        if not path.is_file():
            return cls()
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Reviewed baseline registry root must be an object")
        if str(payload.get("schema_version", "")) != BASELINE_REGISTRY_SCHEMA_VERSION:
            raise ValueError("Unsupported reviewed baseline registry schema")
        registry = cls(
            active_baseline_id=(
                str(payload["active_baseline_id"])
                if payload.get("active_baseline_id") is not None
                else None
            ),
            baselines=[
                ReviewedBaselineVersion.from_dict(item)
                for item in payload.get("baselines", [])
            ],
        )
        if registry.active_baseline_id is not None:
            registry.get(registry.active_baseline_id)
        return registry

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active_baseline_id": self.active_baseline_id,
            "baselines": [
                item.to_dict()
                for item in sorted(self.baselines, key=lambda entry: entry.baseline_id)
            ],
        }

    def get(self, baseline_id: str) -> ReviewedBaselineVersion:
        for item in self.baselines:
            if item.baseline_id == baseline_id:
                return item
        raise ValueError(f"Reviewed baseline id is not registered: {baseline_id}")

    def save(self, path: Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path


def register_reviewed_baseline(
    registry_path: Path,
    baseline_path: Path,
    baseline_id: str,
    *,
    activate: bool = True,
) -> ReviewedBaselineRegistry:
    baseline_id = baseline_id.strip()
    if not baseline_id:
        raise ValueError("baseline_id must not be empty")
    registry_path = Path(registry_path).resolve()
    baseline_path = Path(baseline_path).resolve()
    snapshot = ReviewedBaselineSnapshot.load(baseline_path)
    digest = _sha256(baseline_path)
    registry = ReviewedBaselineRegistry.load(registry_path)

    try:
        relative_path = baseline_path.relative_to(registry_path.parent).as_posix()
    except ValueError as exc:
        raise ValueError(
            "Reviewed baseline must be stored inside the baseline registry directory"
        ) from exc
    existing = None
    for item in registry.baselines:
        if item.baseline_id == baseline_id:
            existing = item
            break
    if existing is not None and existing.sha256 != digest:
        raise ValueError(
            f"Baseline id {baseline_id!r} already refers to different bytes"
        )
    if existing is None:
        registry.baselines.append(
            ReviewedBaselineVersion(
                baseline_id=baseline_id,
                path=relative_path,
                sha256=digest,
                created_at=snapshot.created_at,
                manifest_sha256=snapshot.manifest_sha256,
                gold_sha256=snapshot.gold_sha256,
            )
        )
    if activate:
        registry.active_baseline_id = baseline_id
    registry.save(registry_path)
    return registry


def load_active_reviewed_baseline(
    registry_path: Path,
) -> Optional[ReviewedBaselineSnapshot]:
    registry_path = Path(registry_path).resolve()
    registry = ReviewedBaselineRegistry.load(registry_path)
    if registry.active_baseline_id is None:
        return None
    version = registry.get(registry.active_baseline_id)
    root = registry_path.parent
    path = (root / version.path).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            "Active reviewed baseline path escapes registry directory"
        ) from exc
    if not path.is_file():
        raise ValueError(f"Active reviewed baseline file is missing: {path}")
    if _sha256(path) != version.sha256:
        raise ValueError(
            f"Active reviewed baseline bytes changed for {version.baseline_id}"
        )
    snapshot = ReviewedBaselineSnapshot.load(path)
    if snapshot.manifest_sha256 != version.manifest_sha256:
        raise ValueError("Active baseline manifest provenance does not match registry")
    if snapshot.gold_sha256 != version.gold_sha256:
        raise ValueError("Active baseline gold provenance does not match registry")
    return snapshot
