"""Local A/B/C execution for the runtime ablation pilot.

Variant D intentionally stays external because it requires an explicitly chosen
AI provider/model and cost accounting. The analyzer consumes D through the same
AblationRunArtifact contract.
"""

from __future__ import annotations

import json
import multiprocessing
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from book.benchmark.ablation import (
    AblationObservation,
    AblationPilotSpec,
    AblationReadiness,
    AblationRunArtifact,
)
from book.benchmark.corpus import CorpusStore
from book.benchmark.gold import GoldAnnotation, evaluate_gold, load_gold_annotation
from book.domain.models import Book
from book.orchestration import AttemptStatus, ParserOrchestrator
from book.parsers import MarkerAdapter, MinerUAdapter, ParserRegistry, PyMuPDFAdapter
from book.quality import QualityEngine
from book.reconstruction import ReconstructionPipeline
from book.repair import PatchEngine, PatchValidationError


def _metric_at_path(metrics: Dict[str, Any], path: str) -> Optional[float]:
    current: Any = metrics
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if isinstance(current, bool) or not isinstance(current, (int, float)):
        return None
    return float(current)


def _selected_gold(
    annotation: GoldAnnotation,
    page_indexes: Sequence[int],
) -> GoldAnnotation:
    selected = tuple(
        page for page in annotation.pages if page.page_index in set(page_indexes)
    )
    if len(selected) != len(set(page_indexes)):
        found = {page.page_index for page in selected}
        missing = sorted(set(page_indexes) - found)
        raise ValueError(f"Reviewed gold is missing selected pages: {missing}")
    return GoldAnnotation(
        schema_version=annotation.schema_version,
        document_id=annotation.document_id,
        source_sha256=annotation.source_sha256,
        pages=selected,
        status=annotation.status,
        annotated_by=annotation.annotated_by,
        reviewed_by=annotation.reviewed_by,
        notes=annotation.notes,
    )


def _issue_pages(book: Book, issue: Any) -> Set[int]:
    pages: Set[int] = set()
    evidence_pages = issue.evidence.get("pages")
    if isinstance(evidence_pages, list):
        for value in evidence_pages:
            if isinstance(value, int):
                pages.add(value)
    for node_id in issue.node_ids:
        node = book.find_node(node_id)
        if node is None:
            continue
        pages.update(source.page_index for source in node.source)
    return pages


def _target_review_issue_count(
    book: Book,
    page_indexes: Sequence[int],
    *,
    engine: Optional[QualityEngine] = None,
) -> int:
    selected = set(page_indexes)
    report = (engine or QualityEngine()).analyze(book)
    count = 0
    for issue in report.issues:
        pages = _issue_pages(book, issue)
        if not pages or pages.intersection(selected):
            count += 1
    return count


def _quality_macro(
    metrics: Dict[str, Any],
    metric_paths: Sequence[str],
) -> Tuple[Optional[float], Dict[str, float]]:
    values = {
        path: value
        for path in metric_paths
        for value in [_metric_at_path(metrics, path)]
        if value is not None
    }
    if not values:
        return None, {}
    return round(sum(values.values()) / len(values), 6), values


def _default_registry() -> ParserRegistry:
    return ParserRegistry(
        [
            PyMuPDFAdapter(),
            MinerUAdapter(),
            MarkerAdapter(),
        ]
    )


def _apply_deterministic_repairs(book: Book) -> Tuple[Book, int, int]:
    engine = QualityEngine()
    patch_engine = PatchEngine()
    report = engine.analyze(book)
    patches = [
        issue.suggested_patch
        for issue in report.issues
        if issue.suggested_patch is not None
    ]
    result = Book.from_dict(book.to_dict())
    applied = 0
    rejected = 0
    for patch in patches:
        try:
            result = patch_engine.apply(result, patch)
            applied += 1
        except PatchValidationError:
            rejected += 1
    return result, applied, rejected


def _variant_worker(
    variant_id: str,
    source_path: str,
    result_path: str,
) -> None:
    source = Path(source_path)
    metadata: Dict[str, Any] = {
        "variant_id": variant_id,
        "selected_parser": None,
        "parser_attempts": 0,
        "intervention_count": 0,
        "valid_for_decision": True,
        "invalid_reason": "",
    }

    try:
        if variant_id == "A":
            raw = PyMuPDFAdapter().parse(source)
            book = ReconstructionPipeline().run(raw)
            metadata["selected_parser"] = "pymupdf"
            metadata["parser_attempts"] = 1
        elif variant_id in {"B", "C"}:
            result = ParserOrchestrator(_default_registry()).run(source)
            if result.book is None:
                raise RuntimeError("Parser orchestrator produced no BookIR result")
            book = result.book
            metadata["selected_parser"] = result.selected_parser
            metadata["parser_attempts"] = len(result.attempts)

            rejected_pymupdf = any(
                attempt.parser_name == "pymupdf"
                and attempt.status == AttemptStatus.REJECTED
                for attempt in result.attempts
            )
            fallback_attempts = [
                attempt
                for attempt in result.attempts
                if attempt.parser_name in {"mineru", "marker"}
            ]
            if (
                rejected_pymupdf
                and fallback_attempts
                and all(
                    attempt.status == AttemptStatus.UNAVAILABLE
                    for attempt in fallback_attempts
                )
            ):
                metadata["valid_for_decision"] = False
                metadata["invalid_reason"] = (
                    "quality routing requested a semantic fallback, but every "
                    "configured semantic backend was unavailable"
                )

            if variant_id == "C":
                book, applied, rejected = _apply_deterministic_repairs(book)
                metadata["intervention_count"] = applied
                metadata["rejected_patch_count"] = rejected
        else:
            raise ValueError("Local ablation runner supports only variants A, B, and C")

        payload = {
            "status": "success",
            "book": book.to_dict(),
            "metadata": metadata,
        }
    except Exception as exc:
        payload = {
            "status": "failed",
            "error": f"{type(exc).__name__}: {exc}",
            "metadata": metadata,
        }

    Path(result_path).write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _context() -> multiprocessing.context.BaseContext:
    methods = multiprocessing.get_all_start_methods()
    return multiprocessing.get_context("fork" if "fork" in methods else "spawn")


def _run_worker(
    variant_id: str,
    source: Path,
    *,
    timeout: float,
    sandbox: Path,
) -> Tuple[str, float, Optional[Book], Dict[str, Any], str]:
    result_path = sandbox / f"{variant_id}.json"
    started = time.monotonic()
    process = _context().Process(
        target=_variant_worker,
        args=(variant_id, str(source), str(result_path)),
    )
    process.start()
    process.join(timeout)
    elapsed = time.monotonic() - started

    if process.is_alive():
        process.terminate()
        process.join(5.0)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(2.0)
        return (
            "timeout",
            elapsed,
            None,
            {
                "variant_id": variant_id,
                "valid_for_decision": True,
                "invalid_reason": "",
                "selected_parser": None,
                "parser_attempts": 0,
                "intervention_count": 0,
            },
            f"variant exceeded timeout of {timeout:.3f}s",
        )

    if not result_path.is_file():
        return (
            "failed",
            elapsed,
            None,
            {
                "variant_id": variant_id,
                "valid_for_decision": True,
                "invalid_reason": "",
                "selected_parser": None,
                "parser_attempts": 0,
                "intervention_count": 0,
            },
            f"variant worker exited with code {process.exitcode} without output",
        )

    payload = json.loads(result_path.read_text(encoding="utf-8"))
    metadata = dict(payload.get("metadata", {}))
    if payload.get("status") != "success":
        return (
            "failed",
            elapsed,
            None,
            metadata,
            str(payload.get("error", "variant worker failed")),
        )
    return (
        "success",
        elapsed,
        Book.from_dict(payload["book"]),
        metadata,
        "",
    )


def run_local_ablation(
    spec: AblationPilotSpec,
    readiness: AblationReadiness,
    *,
    manifest_path: Path,
    cache_dir: Path,
    output_dir: Path,
    variants: Sequence[str] = ("A", "B", "C"),
    timeout: float = 300.0,
) -> AblationRunArtifact:
    """Run local non-AI variants on the exact reviewed pilot target set."""

    if not readiness.ready:
        raise ValueError(
            "Ablation pilot is not evidence-ready; obtain reviewed gold before running"
        )
    requested = tuple(variants)
    if not requested:
        raise ValueError("At least one local ablation variant is required")
    if any(item not in {"A", "B", "C"} for item in requested):
        raise ValueError("Local ablation runner supports only A, B, and C")
    if len(requested) != len(set(requested)):
        raise ValueError("Local ablation variants must be unique")
    if timeout <= 0:
        raise ValueError("Ablation timeout must be > 0")

    manifest_path = Path(manifest_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    store = CorpusStore(manifest_path, cache_dir)
    manifest = store.manifest
    by_id = {item.id: item for item in manifest.documents}

    pages_by_document: Dict[str, List[int]] = defaultdict(list)
    for document_id, page_index in readiness.ready_targets:
        pages_by_document[document_id].append(page_index)

    materializations = {
        item.document_id: Path(item.path)
        for item in store.fetch(sorted(pages_by_document))
    }
    observations: List[AblationObservation] = []

    for document_id in sorted(pages_by_document):
        pages = tuple(sorted(pages_by_document[document_id]))
        corpus_spec = by_id[document_id]
        annotation = load_gold_annotation(manifest_path, corpus_spec)
        if annotation is None or annotation.status != "reviewed":
            raise ValueError(
                f"{document_id}: local ablation requires canonical reviewed gold"
            )
        selected_gold = _selected_gold(annotation, pages)
        source = materializations[document_id]

        for variant_id in requested:
            with tempfile.TemporaryDirectory(
                prefix=f"ablation-{document_id}-{variant_id}-",
                dir=str(output_dir),
            ) as sandbox_value:
                status, elapsed, book, metadata, error = _run_worker(
                    variant_id,
                    source,
                    timeout=timeout,
                    sandbox=Path(sandbox_value),
                )

            quality_macro: Optional[float] = None
            metric_values: Dict[str, float] = {}
            review_issue_count = 0
            if book is not None:
                gold_result = evaluate_gold(book, selected_gold)
                quality_macro, metric_values = _quality_macro(
                    gold_result.metrics,
                    spec.quality_metric_paths,
                )
                review_issue_count = _target_review_issue_count(book, pages)
                stable_dir = output_dir / document_id / variant_id
                stable_dir.mkdir(parents=True, exist_ok=True)
                (stable_dir / "bookir.json").write_text(
                    book.to_json() + "\n",
                    encoding="utf-8",
                )
                (stable_dir / "gold-metrics.json").write_text(
                    json.dumps(
                        gold_result.metrics,
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )

            observations.append(
                AblationObservation(
                    variant_id=variant_id,
                    document_id=document_id,
                    page_indexes=pages,
                    status=status,
                    elapsed_seconds=elapsed,
                    quality_macro=quality_macro,
                    metric_values=metric_values,
                    review_issue_count=review_issue_count,
                    manual_review_minutes=None,
                    ai_cost_usd=0.0,
                    intervention_count=int(metadata.get("intervention_count", 0)),
                    selected_parser=(
                        str(metadata["selected_parser"])
                        if metadata.get("selected_parser") is not None
                        else None
                    ),
                    parser_attempts=int(metadata.get("parser_attempts", 0)),
                    valid_for_decision=bool(metadata.get("valid_for_decision", True)),
                    invalid_reason=str(metadata.get("invalid_reason", "")),
                    error=error,
                )
            )

    artifact = AblationRunArtifact(
        pilot_id=spec.pilot_id,
        corpus_id=spec.corpus_id,
        observations=tuple(observations),
        source="local-runtime",
    )
    artifact.save(output_dir / "ablation-run.json")
    return artifact
