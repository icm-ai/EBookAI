"""Models for rights-cleared real-world parser benchmarks."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_ALLOWED_STATUSES = {"success", "skipped", "failed", "timeout"}


@dataclass(frozen=True)
class CorpusDocumentSpec:
    """One immutable document definition in the benchmark corpus."""

    id: str
    title: str
    source_url: str
    license_url: str
    rights_basis: str
    sha256: str
    document_class: str
    language: str
    page_count: int
    complexity_tags: tuple[str, ...] = ()
    expected_capabilities: tuple[str, ...] = ()
    redistributable: bool = False
    embedded_base64_path: str = ""
    gold_annotations_path: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not _ID_RE.fullmatch(self.id):
            raise ValueError(f"Invalid corpus document id: {self.id!r}")
        if not self.title.strip():
            raise ValueError("Corpus document title must not be empty")
        if not self.source_url.startswith("https://"):
            raise ValueError("Corpus source_url must use https")
        if not self.license_url.startswith("https://"):
            raise ValueError("Corpus license_url must use https")
        if not self.rights_basis.strip():
            raise ValueError("Corpus rights_basis must not be empty")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError("Corpus sha256 must be 64 lowercase hex characters")
        if self.page_count <= 0:
            raise ValueError("Corpus page_count must be > 0")
        if self.embedded_base64_path and not self.redistributable:
            raise ValueError(
                "Embedded corpus assets require redistributable=true and an "
                "explicit rights basis"
            )

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CorpusDocumentSpec":
        return cls(
            id=str(value["id"]),
            title=str(value["title"]),
            source_url=str(value["source_url"]),
            license_url=str(value["license_url"]),
            rights_basis=str(value["rights_basis"]),
            sha256=str(value["sha256"]).lower(),
            document_class=str(value["document_class"]),
            language=str(value.get("language", "und")),
            page_count=int(value["page_count"]),
            complexity_tags=tuple(
                str(item) for item in value.get("complexity_tags", [])
            ),
            expected_capabilities=tuple(
                str(item) for item in value.get("expected_capabilities", [])
            ),
            redistributable=bool(value.get("redistributable", False)),
            embedded_base64_path=str(value.get("embedded_base64_path", "")),
            gold_annotations_path=str(value.get("gold_annotations_path", "")),
            notes=str(value.get("notes", "")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "source_url": self.source_url,
            "license_url": self.license_url,
            "rights_basis": self.rights_basis,
            "sha256": self.sha256,
            "document_class": self.document_class,
            "language": self.language,
            "page_count": self.page_count,
            "complexity_tags": list(self.complexity_tags),
            "expected_capabilities": list(self.expected_capabilities),
            "redistributable": self.redistributable,
            "embedded_base64_path": self.embedded_base64_path,
            "gold_annotations_path": self.gold_annotations_path,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class CorpusManifest:
    """Versioned manifest for a rights-cleared benchmark corpus."""

    corpus_id: str
    documents: tuple[CorpusDocumentSpec, ...]
    schema_version: str = "1"
    description: str = ""

    def __post_init__(self) -> None:
        if self.schema_version != "1":
            raise ValueError(
                f"Unsupported corpus manifest schema: {self.schema_version!r}"
            )
        if not _ID_RE.fullmatch(self.corpus_id):
            raise ValueError(f"Invalid corpus id: {self.corpus_id!r}")
        ids = [document.id for document in self.documents]
        if len(ids) != len(set(ids)):
            raise ValueError("Corpus manifest contains duplicate document ids")
        if not ids:
            raise ValueError("Corpus manifest must contain at least one document")

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "CorpusManifest":
        documents = value.get("documents")
        if not isinstance(documents, list):
            raise ValueError("Corpus manifest documents must be a list")
        return cls(
            schema_version=str(value.get("schema_version", "")),
            corpus_id=str(value["corpus_id"]),
            description=str(value.get("description", "")),
            documents=tuple(CorpusDocumentSpec.from_dict(item) for item in documents),
        )

    @classmethod
    def load(cls, path: Path) -> "CorpusManifest":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Corpus manifest root must be an object")
        return cls.from_dict(payload)

    def select(self, ids: Optional[Iterable[str]] = None) -> List[CorpusDocumentSpec]:
        if ids is None:
            return list(self.documents)
        requested = list(ids)
        by_id = {document.id: document for document in self.documents}
        unknown = sorted(set(requested) - set(by_id))
        if unknown:
            raise KeyError(f"Unknown corpus document ids: {', '.join(unknown)}")
        return [by_id[item] for item in requested]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "description": self.description,
            "documents": [document.to_dict() for document in self.documents],
        }


@dataclass(frozen=True)
class CorpusMaterialization:
    document_id: str
    path: str
    sha256: str
    byte_count: int
    source: str
    cached: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "path": self.path,
            "sha256": self.sha256,
            "byte_count": self.byte_count,
            "source": self.source,
            "cached": self.cached,
        }


@dataclass
class BackendRunResult:
    """Serializable result for one document/backend parser attempt."""

    document_id: str
    backend: str
    status: str
    elapsed_seconds: float
    backend_version: str = "unknown"
    parser_profile: Dict[str, Any] = field(default_factory=dict)
    metrics: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    error: str = ""
    bookir_path: str = ""

    def __post_init__(self) -> None:
        if self.status not in _ALLOWED_STATUSES:
            raise ValueError(f"Unsupported benchmark status: {self.status!r}")
        if self.elapsed_seconds < 0:
            raise ValueError("elapsed_seconds must be >= 0")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "document_id": self.document_id,
            "backend": self.backend,
            "status": self.status,
            "elapsed_seconds": round(self.elapsed_seconds, 6),
            "backend_version": self.backend_version,
            "parser_profile": self.parser_profile,
            "metrics": self.metrics,
            "warnings": list(self.warnings),
            "error": self.error,
            "bookir_path": self.bookir_path,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "BackendRunResult":
        return cls(
            document_id=str(value["document_id"]),
            backend=str(value["backend"]),
            status=str(value["status"]),
            elapsed_seconds=float(value.get("elapsed_seconds", 0.0)),
            backend_version=str(value.get("backend_version", "unknown")),
            parser_profile=dict(value.get("parser_profile", {})),
            metrics=dict(value.get("metrics", {})),
            warnings=[str(item) for item in value.get("warnings", [])],
            error=str(value.get("error", "")),
            bookir_path=str(value.get("bookir_path", "")),
        )


@dataclass
class BenchmarkReport:
    corpus_id: str
    manifest_path: str
    runs: List[BackendRunResult]
    documents: List[Dict[str, Any]] = field(default_factory=list)
    schema_version: str = "1"

    def to_dict(self) -> Dict[str, Any]:
        status_counts = {status: 0 for status in sorted(_ALLOWED_STATUSES)}
        backend_names = sorted({run.backend for run in self.runs})
        document_ids = sorted({run.document_id for run in self.runs})
        by_backend: Dict[str, Dict[str, Any]] = {}
        for backend in backend_names:
            items = [run for run in self.runs if run.backend == backend]
            successes = [run for run in items if run.status == "success"]
            attempted = [run for run in items if run.status != "skipped"]
            for item in items:
                status_counts[item.status] += 1
            by_backend[backend] = {
                "documents": len(items),
                "success": len(successes),
                "skipped": sum(item.status == "skipped" for item in items),
                "failed": sum(item.status == "failed" for item in items),
                "timeout": sum(item.status == "timeout" for item in items),
                "runnable_success_rate": (
                    round(len(successes) / len(attempted), 4) if attempted else None
                ),
                "mean_elapsed_seconds": (
                    round(
                        sum(item.elapsed_seconds for item in successes)
                        / len(successes),
                        6,
                    )
                    if successes
                    else None
                ),
            }
        return {
            "schema_version": self.schema_version,
            "corpus_id": self.corpus_id,
            "manifest_path": self.manifest_path,
            "documents": self.documents,
            "summary": {
                "document_count": len(document_ids),
                "backend_count": len(backend_names),
                "run_count": len(self.runs),
                "status_counts": status_counts,
                "by_backend": by_backend,
            },
            "runs": [run.to_dict() for run in self.runs],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "BenchmarkReport":
        if str(value.get("schema_version", "")) != "1":
            raise ValueError("Unsupported benchmark report schema")
        return cls(
            schema_version="1",
            corpus_id=str(value["corpus_id"]),
            manifest_path=str(value.get("manifest_path", "")),
            documents=[dict(item) for item in value.get("documents", [])],
            runs=[BackendRunResult.from_dict(item) for item in value.get("runs", [])],
        )

    @classmethod
    def load(cls, path: Path) -> "BenchmarkReport":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Benchmark report root must be an object")
        return cls.from_dict(payload)
