"""Materialize and verify rights-cleared real-world benchmark PDFs."""

from __future__ import annotations

import base64
import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from book.benchmark.models import (
    CorpusDocumentSpec,
    CorpusManifest,
    CorpusMaterialization,
)


class CorpusIntegrityError(RuntimeError):
    """Raised when corpus bytes do not match their pinned digest."""


class CorpusDownloadError(RuntimeError):
    """Raised when a remote corpus item cannot be materialized."""


class CorpusStore:
    """Fetch, cache, and digest-pin real-world benchmark sources."""

    def __init__(self, manifest_path: Path, cache_dir: Path) -> None:
        self.manifest_path = Path(manifest_path).resolve()
        self.manifest = CorpusManifest.load(self.manifest_path)
        self.cache_dir = Path(cache_dir).resolve()

    def path_for(self, document: CorpusDocumentSpec) -> Path:
        return self.cache_dir / f"{document.id}-{document.sha256[:12]}.pdf"

    def fetch(
        self,
        document_ids: Optional[Iterable[str]] = None,
        *,
        force: bool = False,
        timeout: float = 60.0,
    ) -> List[CorpusMaterialization]:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return [
            self._materialize(document, force=force, timeout=timeout)
            for document in self.manifest.select(document_ids)
        ]

    def verify(
        self,
        document_ids: Optional[Iterable[str]] = None,
    ) -> List[Dict[str, object]]:
        results: List[Dict[str, object]] = []
        for document in self.manifest.select(document_ids):
            path = self.path_for(document)
            if not path.is_file():
                results.append(
                    {
                        "document_id": document.id,
                        "path": str(path),
                        "exists": False,
                        "ok": False,
                        "expected_sha256": document.sha256,
                        "sha256": None,
                        "byte_count": 0,
                    }
                )
                continue
            digest = self._sha256(path)
            results.append(
                {
                    "document_id": document.id,
                    "path": str(path),
                    "exists": True,
                    "ok": digest == document.sha256,
                    "expected_sha256": document.sha256,
                    "sha256": digest,
                    "byte_count": path.stat().st_size,
                }
            )
        return results

    def _materialize(
        self,
        document: CorpusDocumentSpec,
        *,
        force: bool,
        timeout: float,
    ) -> CorpusMaterialization:
        destination = self.path_for(document)
        if destination.is_file() and not force:
            digest = self._sha256(destination)
            if digest == document.sha256:
                return CorpusMaterialization(
                    document_id=document.id,
                    path=str(destination),
                    sha256=digest,
                    byte_count=destination.stat().st_size,
                    source="cache",
                    cached=True,
                )

        if document.embedded_base64_path:
            source = self._read_embedded(document)
            source_kind = "embedded"
        else:
            source = self._download(document, timeout=timeout)
            source_kind = "remote"

        digest = hashlib.sha256(source).hexdigest()
        if digest != document.sha256:
            raise CorpusIntegrityError(
                f"SHA-256 mismatch for {document.id}: expected {document.sha256}, "
                f"got {digest}"
            )

        self._atomic_write(destination, source)
        return CorpusMaterialization(
            document_id=document.id,
            path=str(destination),
            sha256=digest,
            byte_count=len(source),
            source=source_kind,
            cached=False,
        )

    def _read_embedded(self, document: CorpusDocumentSpec) -> bytes:
        asset = (self.manifest_path.parent / document.embedded_base64_path).resolve()
        try:
            asset.relative_to(self.manifest_path.parent.resolve())
        except ValueError as exc:
            raise ValueError(
                f"Embedded corpus path escapes manifest directory: {asset}"
            ) from exc
        try:
            encoded = asset.read_bytes()
            return base64.b64decode(encoded, validate=True)
        except (OSError, ValueError) as exc:
            raise CorpusIntegrityError(
                f"Unable to decode embedded corpus asset for {document.id}: {asset}"
            ) from exc

    @staticmethod
    def _download(document: CorpusDocumentSpec, *, timeout: float) -> bytes:
        request = urllib.request.Request(
            document.source_url,
            headers={"User-Agent": "EBookAI-real-world-benchmark/1"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            raise CorpusDownloadError(
                f"Unable to fetch {document.id} from {document.source_url}"
            ) from exc

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _atomic_write(path: Path, value: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
