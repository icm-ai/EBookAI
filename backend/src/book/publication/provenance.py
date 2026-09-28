"""Deterministic toolchain provenance for release attestation."""

from __future__ import annotations

import importlib.metadata
import os
import platform
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from book.domain.models import Book
from book.publication.epubcheck import EpubCheckResult


def _package_version(name: str) -> Optional[str]:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


@dataclass(frozen=True)
class ToolchainProvenance:
    """Stable, non-secret description of the toolchain that produced a release."""

    runtime: Dict[str, str]
    parser: Dict[str, Any]
    reconstruction: Dict[str, Any]
    ai_repairs: List[Dict[str, str]]
    compiler: Dict[str, str]
    external_validation: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": "0.1",
            "runtime": dict(self.runtime),
            "parser": dict(self.parser),
            "reconstruction": dict(self.reconstruction),
            "ai_repairs": [dict(item) for item in self.ai_repairs],
            "compiler": dict(self.compiler),
            "external_validation": dict(self.external_validation),
        }


class ToolchainProvenanceBuilder:
    """Extract reproducible tool/version evidence from BookIR and runtime metadata."""

    def build(self, book: Book, epubcheck: EpubCheckResult) -> ToolchainProvenance:
        orchestration = book.metadata.extra.get("orchestration", {})
        if not isinstance(orchestration, dict):
            orchestration = {}

        attempts = orchestration.get("attempts", [])
        if not isinstance(attempts, list):
            attempts = []

        parser_names = sorted(
            {
                str(item.get("parser_name"))
                for item in attempts
                if isinstance(item, dict) and item.get("parser_name")
            }
        )
        selected_parser = str(orchestration.get("selected_parser", ""))

        ai_proposals = book.metadata.extra.get("review", {}).get("ai_proposals", [])
        if not isinstance(ai_proposals, list):
            ai_proposals = []
        ai_repairs = sorted(
            (
                {
                    "provider": str(item.get("provider", "")),
                    "model": str(item.get("model", "")),
                    "input_mode": str(item.get("input_mode", "text")),
                    "status": str(item.get("status", "")),
                }
                for item in ai_proposals
                if isinstance(item, dict)
            ),
            key=lambda item: (
                item["provider"],
                item["model"],
                item["input_mode"],
                item["status"],
            ),
        )

        package_versions = {
            name: version
            for name in (
                "PyMuPDF",
                "pydantic",
                "mineru",
                "marker-pdf",
                "openai",
                "anthropic",
            )
            if (version := _package_version(name)) is not None
        }
        runtime = {
            "python": platform.python_version(),
            **package_versions,
        }
        build_revision = os.environ.get("EBOOKAI_BUILD_REVISION", "").strip()
        if build_revision:
            runtime["ebookai_revision"] = build_revision

        return ToolchainProvenance(
            runtime=runtime,
            parser={
                "selected": selected_parser,
                "attempted": parser_names,
            },
            reconstruction={
                "engine": "ebookai.book.reconstruction",
                "book_ir_version": str(book.schema_version),
            },
            ai_repairs=ai_repairs,
            compiler={
                "engine": "ebookai.book.compiler.EpubCompiler",
                "format": "EPUB3",
            },
            external_validation={
                "epubcheck": {
                    "status": epubcheck.status,
                    "version": epubcheck.version,
                }
            },
        )
