"""End-to-end golden-corpus regression harness."""

from __future__ import annotations

import html
import re
import zipfile
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

from book.compiler import EpubCompiler
from book.domain.models import Book, NodeType
from book.parsers import PyMuPDFAdapter
from book.publication import ExternalEpubCheckRunner, PublicationQAEngine
from book.quality import QualityEngine
from book.reconstruction import ReconstructionPipeline
from book.regression.models import GoldenCaseResult, GoldenCaseSpec
from book.regression.render_evidence import EpubRenderEvidenceCollector

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _ratio(numerator: int, denominator: int) -> float:
    return 1.0 if denominator == 0 else numerator / denominator


def _text_recall(text: str, fragments: Iterable[str]) -> float:
    expected = list(fragments)
    if not expected:
        return 1.0
    haystack = _WS_RE.sub(" ", text).casefold()
    matched = sum(
        1 for fragment in expected if _WS_RE.sub(" ", fragment).casefold() in haystack
    )
    return matched / len(expected)


def _reading_order(text: str, fragments: Iterable[str]) -> float:
    expected = list(fragments)
    if len(expected) <= 1:
        return 1.0
    haystack = _WS_RE.sub(" ", text).casefold()
    positions = [haystack.find(_WS_RE.sub(" ", item).casefold()) for item in expected]
    pairs = len(expected) - 1
    satisfied = sum(
        1
        for left, right in zip(positions, positions[1:])
        if left >= 0 and right >= 0 and left < right
    )
    return satisfied / pairs


def _epub_text(epub_path: Path) -> str:
    chunks: List[str] = []
    with zipfile.ZipFile(epub_path, "r") as archive:
        for name in sorted(archive.namelist()):
            if not name.startswith("EPUB/text/") or not name.endswith(".xhtml"):
                continue
            value = archive.read(name).decode("utf-8")
            chunks.append(html.unescape(_TAG_RE.sub(" ", value)))
    return _WS_RE.sub(" ", " ".join(chunks)).strip()


class GoldenCorpusHarness:
    """Evaluate one source document against explicit semantic/quality thresholds."""

    def __init__(
        self,
        *,
        parser: Optional[PyMuPDFAdapter] = None,
        reconstruction: Optional[ReconstructionPipeline] = None,
        quality_engine: Optional[QualityEngine] = None,
        compiler: Optional[EpubCompiler] = None,
        publication_qa: Optional[PublicationQAEngine] = None,
        epubcheck_runner: Optional[ExternalEpubCheckRunner] = None,
    ) -> None:
        self.parser = parser or PyMuPDFAdapter()
        self.reconstruction = reconstruction or ReconstructionPipeline()
        self.quality_engine = quality_engine or QualityEngine()
        self.compiler = compiler or EpubCompiler()
        self.publication_qa = publication_qa or PublicationQAEngine()
        self.epubcheck_runner = epubcheck_runner
        self.render_collector = EpubRenderEvidenceCollector()

    def evaluate(
        self,
        source_path: Path,
        spec: GoldenCaseSpec,
        output_dir: Path,
    ) -> GoldenCaseResult:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        parsed = self.parser.parse(source_path)
        book = self.reconstruction.run(parsed)
        report = self.quality_engine.analyze(book)

        epub_path = output_dir / "book.epub"
        repeat_epub_path = output_dir / "book-repeat.epub"
        self.compiler.compile(book, epub_path)
        self.compiler.compile(book, repeat_epub_path)

        publication = self.publication_qa.analyze(
            book,
            report,
            issue_resolutions={},
            epub_path=epub_path,
        )
        external_epubcheck = (
            self.epubcheck_runner.run(epub_path)
            if self.epubcheck_runner is not None
            else None
        )

        metrics = self._metrics(
            book,
            report,
            epub_path,
            repeat_epub_path,
            spec,
            publication.release_ready,
            external_epubcheck.to_dict() if external_epubcheck else None,
        )
        failures = self._failures(spec, metrics, report)
        evidence = self.render_collector.collect(epub_path)

        return GoldenCaseResult(
            case_id=spec.id,
            category=spec.category,
            passed=not failures,
            metrics=metrics,
            failures=failures,
            known_gaps=spec.known_gaps,
            render_evidence=evidence,
            output_files={
                "epub": str(epub_path),
            },
        )

    def _metrics(
        self,
        book: Book,
        report: Any,
        epub_path: Path,
        repeat_epub_path: Path,
        spec: GoldenCaseSpec,
        publication_ready: bool,
        epubcheck: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        nodes = list(book.walk())
        content_nodes = [node for node in nodes if node.content.strip()]
        source_refs = [source for node in content_nodes for source in node.source]
        counts = Counter(node.type.value for node in nodes)
        text = "\n".join(node.content for node in nodes if node.content)
        issue_codes = sorted({issue.code for issue in report.issues})
        expected = spec.expectation

        type_scores = [
            min(counts[node_type] / required, 1.0)
            for node_type, required in expected.minimum_node_types.items()
            if required > 0
        ]
        text_recall = _text_recall(text, expected.text_fragments)
        reading_order = _reading_order(text, expected.ordered_fragments)
        footnote_refs = sum(
            len(node.attrs.get("reference_node_ids", []))
            for node in nodes
            if node.type == NodeType.FOOTNOTE
        )

        semantic_components = [*type_scores]
        if expected.text_fragments:
            semantic_components.append(text_recall)
        if expected.ordered_fragments:
            semantic_components.append(reading_order)
        if expected.minimum_footnote_references:
            semantic_components.append(
                min(
                    footnote_refs / expected.minimum_footnote_references,
                    1.0,
                )
            )
        semantic_score = (
            round(mean(semantic_components), 4) if semantic_components else None
        )

        epub_text_recall = _text_recall(
            _epub_text(epub_path),
            expected.text_fragments,
        )

        return {
            "node_count": len(nodes),
            "node_type_counts": dict(sorted(counts.items())),
            "semantic_score": semantic_score,
            "text_recall": round(text_recall, 4),
            "reading_order": round(reading_order, 4),
            "provenance_coverage": round(
                _ratio(
                    sum(1 for node in content_nodes if node.source),
                    len(content_nodes),
                ),
                4,
            ),
            "bbox_coverage": round(
                _ratio(
                    sum(1 for source in source_refs if source.bbox is not None),
                    len(source_refs),
                ),
                4,
            ),
            "quality_score": report.score,
            "quality_issue_codes": issue_codes,
            "footnote_reference_count": footnote_refs,
            "publication_ready": publication_ready,
            "epub_text_recall": round(epub_text_recall, 4),
            "epub_reproducible": (
                epub_path.read_bytes() == repeat_epub_path.read_bytes()
            ),
            "epubcheck": epubcheck,
        }

    @staticmethod
    def _failures(
        spec: GoldenCaseSpec,
        metrics: Dict[str, Any],
        report: Any,
    ) -> List[str]:
        failures: List[str] = []
        expected = spec.expectation
        thresholds = spec.thresholds
        counts = metrics["node_type_counts"]
        issue_codes = set(metrics["quality_issue_codes"])

        for node_type, minimum in expected.minimum_node_types.items():
            actual = int(counts.get(node_type, 0))
            if actual < minimum:
                failures.append(
                    f"node type {node_type}: expected >= {minimum}, got {actual}"
                )

        for code in expected.required_issue_codes:
            if code not in issue_codes:
                failures.append(f"required quality issue missing: {code}")
        for code in expected.forbidden_issue_codes:
            if code in issue_codes:
                failures.append(f"forbidden quality issue present: {code}")

        if metrics["footnote_reference_count"] < expected.minimum_footnote_references:
            failures.append(
                "footnote references: expected >= "
                f"{expected.minimum_footnote_references}, "
                f"got {metrics['footnote_reference_count']}"
            )

        if (
            expected.publication_ready is not None
            and metrics["publication_ready"] != expected.publication_ready
        ):
            failures.append(
                "publication readiness: expected "
                f"{expected.publication_ready}, got {metrics['publication_ready']}"
            )

        for name, minimum in (
            ("semantic_score", thresholds.semantic_score_min),
            ("text_recall", thresholds.text_recall_min),
            ("reading_order", thresholds.reading_order_min),
            ("provenance_coverage", thresholds.provenance_coverage_min),
            ("bbox_coverage", thresholds.bbox_coverage_min),
            ("epub_text_recall", thresholds.epub_text_recall_min),
        ):
            value = metrics.get(name)
            if minimum is not None and (value is None or float(value) < minimum):
                failures.append(f"{name}: expected >= {minimum}, got {value}")

        if not metrics["epub_reproducible"]:
            failures.append("EPUB bytes are not reproducible for identical BookIR")

        external = metrics.get("epubcheck")
        if expected.publication_ready is True and external is not None:
            if external.get("status") != "passed":
                failures.append(
                    f"external EPUBCheck did not pass: {external.get('status')}"
                )

        return failures
