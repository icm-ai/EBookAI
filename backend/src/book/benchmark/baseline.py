"""Provenance-pinned snapshots for reviewed-only parser leaderboard baselines."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

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
        raise ValueError(
            "Leaderboard corpus_id does not match the corpus manifest"
        )

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
