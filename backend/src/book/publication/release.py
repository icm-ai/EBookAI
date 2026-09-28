"""Reproducible release bundles for reviewed BookIR publications."""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from book.compiler import EpubCompiler
from book.domain.models import BOOK_IR_VERSION, Book
from book.publication.epubcheck import EpubCheckResult, ExternalEpubCheckRunner
from book.publication.models import PublicationReport
from book.publication.qa import PublicationQAEngine
from book.quality import QualityReport


def _canonical_json(value: Dict[str, Any]) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class ReleaseArtifact:
    """One integrity-protected file inside a release bundle."""

    path: str
    sha256: str
    size: int
    media_type: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "size": self.size,
            "media_type": self.media_type,
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReleaseArtifact":
        return cls(
            path=str(value["path"]),
            sha256=str(value["sha256"]),
            size=int(value["size"]),
            media_type=str(value.get("media_type", "application/octet-stream")),
        )


@dataclass(frozen=True)
class ReleaseManifest:
    """Deterministic manifest tying source, BookIR, EPUB, and reports together."""

    release_id: str
    source_filename: str
    release_ready: bool
    require_epubcheck: bool
    epubcheck_status: str
    epubcheck_version: str
    artifacts: List[ReleaseArtifact]
    schema_version: str = "0.1"
    book_ir_version: str = BOOK_IR_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "book_ir_version": self.book_ir_version,
            "release_id": self.release_id,
            "source_filename": self.source_filename,
            "release_ready": self.release_ready,
            "policy": {
                "require_epubcheck": self.require_epubcheck,
            },
            "external_validation": {
                "epubcheck": {
                    "status": self.epubcheck_status,
                    "version": self.epubcheck_version,
                }
            },
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ReleaseManifest":
        policy = value.get("policy", {})
        external = value.get("external_validation", {})
        epubcheck = external.get("epubcheck", {}) if isinstance(external, dict) else {}
        return cls(
            schema_version=str(value.get("schema_version", "0.1")),
            book_ir_version=str(value.get("book_ir_version", BOOK_IR_VERSION)),
            release_id=str(value["release_id"]),
            source_filename=str(value.get("source_filename", "")),
            release_ready=bool(value.get("release_ready", False)),
            require_epubcheck=bool(
                policy.get("require_epubcheck", False)
                if isinstance(policy, dict)
                else False
            ),
            epubcheck_status=str(
                epubcheck.get("status", "") if isinstance(epubcheck, dict) else ""
            ),
            epubcheck_version=str(
                epubcheck.get("version", "") if isinstance(epubcheck, dict) else ""
            ),
            artifacts=[
                ReleaseArtifact.from_dict(item)
                for item in value.get("artifacts", [])
            ],
        )


@dataclass(frozen=True)
class ReleaseBuildResult:
    """Release pipeline output retained by the review layer."""

    manifest: ReleaseManifest
    publication_report: PublicationReport
    epubcheck_result: EpubCheckResult
    bundle_path: Path


class ReleasePipeline:
    """Compile, validate, hash, package, and verify reviewed publication output."""

    BUNDLE_NAME = "release-bundle.zip"

    def __init__(
        self,
        *,
        compiler: Optional[EpubCompiler] = None,
        qa_engine: Optional[PublicationQAEngine] = None,
        epubcheck_runner: Optional[ExternalEpubCheckRunner] = None,
    ) -> None:
        self.compiler = compiler or EpubCompiler()
        self.qa_engine = qa_engine or PublicationQAEngine()
        self.epubcheck_runner = epubcheck_runner or ExternalEpubCheckRunner()

    def build(
        self,
        *,
        source_path: Path,
        source_filename: str,
        book: Book,
        quality_report: QualityReport,
        issue_resolutions: Dict[str, str],
        output_dir: Path,
        require_epubcheck: bool = False,
    ) -> ReleaseBuildResult:
        source_path = Path(source_path)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)

        output_dir = Path(output_dir)
        output_dir.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(
            prefix=".release-",
            dir=output_dir.parent,
        ) as temporary:
            staging = Path(temporary)
            epub_path = staging / "publication" / "book.epub"
            epub_path.parent.mkdir(parents=True, exist_ok=True)
            self.compiler.compile(book, epub_path)

            publication_report = self.qa_engine.analyze(
                book,
                quality_report,
                issue_resolutions=issue_resolutions,
                epub_path=epub_path,
            )

            release_book = Book.from_dict(book.to_dict())
            release_book.metadata.extra.setdefault("review", {})[
                "publication_report"
            ] = publication_report.to_dict()
            self.compiler.compile(release_book, epub_path)

            epubcheck_result = self.epubcheck_runner.run(epub_path)
            release_ready = self._release_ready(
                publication_report,
                epubcheck_result,
                require_epubcheck=require_epubcheck,
            )

            source_suffix = source_path.suffix.lower() or ".bin"
            source_target = staging / "source" / f"source{source_suffix}"
            source_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_path, source_target)

            bookir_target = staging / "book" / "bookir.json"
            bookir_target.parent.mkdir(parents=True, exist_ok=True)
            bookir_target.write_bytes(_canonical_json(release_book.to_dict()))

            qa_target = staging / "reports" / "publication-qa.json"
            qa_target.parent.mkdir(parents=True, exist_ok=True)
            qa_target.write_bytes(_canonical_json(publication_report.to_dict()))

            epubcheck_target = staging / "reports" / "epubcheck.json"
            epubcheck_target.write_bytes(_canonical_json(epubcheck_result.to_dict()))

            artifacts = self._artifacts(
                staging,
                {
                    source_target.relative_to(staging).as_posix(): self._source_media_type(
                        source_suffix
                    ),
                    "book/bookir.json": "application/json",
                    "publication/book.epub": "application/epub+zip",
                    "reports/publication-qa.json": "application/json",
                    "reports/epubcheck.json": "application/json",
                },
            )
            release_id = self._release_id(
                artifacts,
                require_epubcheck=require_epubcheck,
                release_ready=release_ready,
                epubcheck_status=epubcheck_result.status,
            )
            manifest = ReleaseManifest(
                release_id=release_id,
                source_filename=source_filename,
                release_ready=release_ready,
                require_epubcheck=require_epubcheck,
                epubcheck_status=epubcheck_result.status,
                epubcheck_version=epubcheck_result.version,
                artifacts=artifacts,
            )
            (staging / "manifest.json").write_bytes(
                _canonical_json(manifest.to_dict())
            )

            bundle_path = staging / self.BUNDLE_NAME
            self._write_bundle(staging, bundle_path)

            if output_dir.exists():
                shutil.rmtree(output_dir)
            shutil.copytree(staging, output_dir)

        return ReleaseBuildResult(
            manifest=manifest,
            publication_report=publication_report,
            epubcheck_result=epubcheck_result,
            bundle_path=output_dir / self.BUNDLE_NAME,
        )

    def verify_bundle(self, bundle_path: Path) -> Dict[str, Any]:
        bundle_path = Path(bundle_path)
        errors: List[str] = []
        if not bundle_path.is_file():
            return {
                "valid": False,
                "release_id": "",
                "errors": ["Release bundle does not exist"],
            }

        try:
            archive = zipfile.ZipFile(bundle_path, "r")
        except zipfile.BadZipFile:
            return {
                "valid": False,
                "release_id": "",
                "errors": ["Release bundle is not a valid ZIP archive"],
            }

        with archive:
            try:
                manifest_payload = json.loads(archive.read("manifest.json"))
                manifest = ReleaseManifest.from_dict(manifest_payload)
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
                return {
                    "valid": False,
                    "release_id": "",
                    "errors": [f"Invalid release manifest: {exc}"],
                }

            names = set(archive.namelist())
            for artifact in manifest.artifacts:
                if artifact.path not in names:
                    errors.append(f"Missing artifact: {artifact.path}")
                    continue
                value = archive.read(artifact.path)
                if len(value) != artifact.size:
                    errors.append(f"Size mismatch: {artifact.path}")
                if _sha256_bytes(value) != artifact.sha256:
                    errors.append(f"SHA-256 mismatch: {artifact.path}")

            expected_release_id = self._release_id(
                manifest.artifacts,
                require_epubcheck=manifest.require_epubcheck,
                release_ready=manifest.release_ready,
                epubcheck_status=manifest.epubcheck_status,
            )
            if expected_release_id != manifest.release_id:
                errors.append("Release id does not match manifest contents")

        return {
            "valid": not errors,
            "release_id": manifest.release_id,
            "errors": errors,
        }

    @staticmethod
    def _release_ready(
        report: PublicationReport,
        epubcheck: EpubCheckResult,
        *,
        require_epubcheck: bool,
    ) -> bool:
        if not report.release_ready:
            return False
        if epubcheck.available:
            return epubcheck.executed and epubcheck.valid is True
        return not require_epubcheck

    @staticmethod
    def _artifacts(
        root: Path,
        media_types: Dict[str, str],
    ) -> List[ReleaseArtifact]:
        artifacts: List[ReleaseArtifact] = []
        for relative_path in sorted(media_types):
            value = (root / relative_path).read_bytes()
            artifacts.append(
                ReleaseArtifact(
                    path=relative_path,
                    sha256=_sha256_bytes(value),
                    size=len(value),
                    media_type=media_types[relative_path],
                )
            )
        return artifacts

    @staticmethod
    def _release_id(
        artifacts: List[ReleaseArtifact],
        *,
        require_epubcheck: bool,
        release_ready: bool,
        epubcheck_status: str,
    ) -> str:
        payload = {
            "artifacts": [artifact.to_dict() for artifact in artifacts],
            "policy": {"require_epubcheck": require_epubcheck},
            "release_ready": release_ready,
            "epubcheck_status": epubcheck_status,
        }
        digest = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return f"sha256:{digest}"

    @staticmethod
    def _write_bundle(root: Path, bundle_path: Path) -> None:
        entries = sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and path != bundle_path
        )
        with zipfile.ZipFile(bundle_path, "w") as archive:
            for path in entries:
                relative = path.relative_to(root).as_posix()
                info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_STORED
                info.create_system = 3
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes())

    @staticmethod
    def _source_media_type(suffix: str) -> str:
        return {
            ".pdf": "application/pdf",
            ".epub": "application/epub+zip",
            ".txt": "text/plain",
        }.get(suffix, "application/octet-stream")
