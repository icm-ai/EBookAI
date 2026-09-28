"""Isolated multi-backend runner for parser-level corpus benchmarks."""

from __future__ import annotations

import importlib.metadata
import json
import multiprocessing
import os
import queue
import shutil
import tempfile
import time
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from book.benchmark.corpus import CorpusStore
from book.benchmark.gold import (
    GoldAnnotation,
    evaluate_gold,
    evaluate_gold_gate,
    load_gold_annotation,
)
from book.benchmark.metrics import parser_level_metrics, token_jaccard, token_set
from book.benchmark.models import BackendRunResult, BenchmarkReport, CorpusDocumentSpec
from book.domain.models import Book
from book.parsers import MarkerAdapter, MinerUAdapter, ParserRegistry, PyMuPDFAdapter
from book.parsers.base import BookParserAdapter, ParserBackendUnavailable
from book.quality import QualityEngine

_VERSION_DISTRIBUTIONS = {
    "pymupdf": ("PyMuPDF",),
    "mineru": ("mineru", "mineru-pdf"),
    "marker": ("marker-pdf", "marker"),
}


def _backend_version(name: str) -> str:
    for distribution in _VERSION_DISTRIBUTIONS.get(name, (name,)):
        try:
            return importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            continue
    return "unknown"


def _parse_worker(
    adapter: BookParserAdapter,
    source_path: str,
    work_dir: str,
    result_queue: object,
) -> None:
    """Run one optional parser in a process with an isolated cwd/temp directory."""

    try:
        os.chdir(work_dir)
        for key in ("TMPDIR", "TMP", "TEMP"):
            os.environ[key] = work_dir
        book = adapter.parse(Path(source_path))
        result_path = Path(work_dir) / "result.bookir.json"
        result_path.write_text(book.to_json() + "\n", encoding="utf-8")
        result_queue.put(("success", str(result_path)))
    except ParserBackendUnavailable as exc:
        result_queue.put(("unavailable", str(exc)))
    except BaseException as exc:
        result_queue.put(("failed", f"{type(exc).__name__}: {exc}"))


def default_parser_registry() -> ParserRegistry:
    """Return the standard benchmark set without installing optional backends."""

    return ParserRegistry([PyMuPDFAdapter(), MinerUAdapter(), MarkerAdapter()])


class ParserBenchmarkRunner:
    """Run the same immutable PDF bytes through multiple parser adapters."""

    def __init__(
        self,
        store: CorpusStore,
        output_dir: Path,
        *,
        registry: Optional[ParserRegistry] = None,
        quality_engine: Optional[QualityEngine] = None,
    ) -> None:
        self.store = store
        self.output_dir = Path(output_dir).resolve()
        self.registry = registry or default_parser_registry()
        self.quality_engine = quality_engine or QualityEngine()

    def run(
        self,
        *,
        document_ids: Optional[Iterable[str]] = None,
        backends: Optional[Sequence[str]] = None,
        timeout: float = 300.0,
        fetch_missing: bool = True,
    ) -> BenchmarkReport:
        if timeout <= 0:
            raise ValueError("Benchmark timeout must be > 0")
        specs = self.store.manifest.select(document_ids)
        backend_names = list(backends or ["pymupdf", "mineru", "marker"])
        if len(backend_names) != len(set(backend_names)):
            raise ValueError("Benchmark backend names must be unique")
        adapters = [self.registry.get(name) for name in backend_names]
        self.output_dir.mkdir(parents=True, exist_ok=True)

        runs: List[BackendRunResult] = []
        for spec in specs:
            source = self._source_for(spec, fetch_missing=fetch_missing)
            gold = load_gold_annotation(self.store.manifest_path, spec)
            document_runs: List[BackendRunResult] = []
            successful_books: Dict[str, Book] = {}
            for adapter in adapters:
                result, book = self._run_one(
                    spec=spec,
                    source=source,
                    adapter=adapter,
                    timeout=timeout,
                    gold=gold,
                )
                document_runs.append(result)
                if book is not None:
                    successful_books[adapter.name] = book
            self._attach_cross_backend_proxies(document_runs, successful_books)
            runs.extend(document_runs)

        report = BenchmarkReport(
            corpus_id=self.store.manifest.corpus_id,
            manifest_path=str(self.store.manifest_path),
            documents=[spec.to_dict() for spec in specs],
            runs=runs,
        )
        report_path = self.output_dir / "benchmark-results.json"
        report_path.write_text(report.to_json() + "\n", encoding="utf-8")
        return report

    def _source_for(self, spec: CorpusDocumentSpec, *, fetch_missing: bool) -> Path:
        path = self.store.path_for(spec)
        verification = self.store.verify([spec.id])[0]
        if verification["ok"]:
            return path
        if not fetch_missing:
            raise FileNotFoundError(
                f"Verified corpus materialization missing for {spec.id}: {path}"
            )
        materialized = self.store.fetch([spec.id])[0]
        return Path(materialized.path)

    def _run_one(
        self,
        *,
        spec: CorpusDocumentSpec,
        source: Path,
        adapter: BookParserAdapter,
        timeout: float,
        gold: Optional[GoldAnnotation],
    ) -> Tuple[BackendRunResult, Optional[Book]]:
        profile = adapter.profile()
        version = _backend_version(adapter.name)
        if not profile.get("available", False):
            return (
                BackendRunResult(
                    document_id=spec.id,
                    backend=adapter.name,
                    status="skipped",
                    elapsed_seconds=0.0,
                    backend_version=version,
                    parser_profile=profile,
                    error=(
                        f"Optional parser backend {adapter.name!r} is not installed "
                        "or is not runnable in this environment"
                    ),
                ),
                None,
            )

        stable_dir = self.output_dir / spec.id / adapter.name
        stable_dir.mkdir(parents=True, exist_ok=True)
        sandbox_parent = self.output_dir / ".sandbox"
        sandbox_parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()

        with tempfile.TemporaryDirectory(
            prefix=f"{spec.id}-{adapter.name}-", dir=str(sandbox_parent)
        ) as sandbox_value:
            sandbox = Path(sandbox_value)
            isolated_input = sandbox / "input.pdf"
            shutil.copy2(source, isolated_input)
            ctx = self._multiprocessing_context()
            result_queue = ctx.Queue(maxsize=1)
            process = ctx.Process(
                target=_parse_worker,
                args=(adapter, str(isolated_input), str(sandbox), result_queue),
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
                self._close_queue(result_queue)
                return (
                    BackendRunResult(
                        document_id=spec.id,
                        backend=adapter.name,
                        status="timeout",
                        elapsed_seconds=elapsed,
                        backend_version=version,
                        parser_profile=profile,
                        error=f"Parser exceeded timeout of {timeout:.3f}s",
                    ),
                    None,
                )

            try:
                worker_status, payload = result_queue.get(timeout=1.0)
            except queue.Empty:
                worker_status, payload = (
                    "failed",
                    "Parser worker exited with code "
                    f"{process.exitcode} without a result",
                )
            finally:
                self._close_queue(result_queue)

            if worker_status == "success":
                try:
                    payload = Path(str(payload)).read_text(encoding="utf-8")
                except OSError as exc:
                    worker_status = "failed"
                    payload = f"Unable to read worker BookIR output: {exc}"

        if worker_status == "unavailable":
            return (
                BackendRunResult(
                    document_id=spec.id,
                    backend=adapter.name,
                    status="skipped",
                    elapsed_seconds=elapsed,
                    backend_version=version,
                    parser_profile=profile,
                    error=str(payload),
                ),
                None,
            )
        if worker_status != "success":
            return (
                BackendRunResult(
                    document_id=spec.id,
                    backend=adapter.name,
                    status="failed",
                    elapsed_seconds=elapsed,
                    backend_version=version,
                    parser_profile=profile,
                    error=str(payload),
                ),
                None,
            )

        try:
            book = Book.from_json(str(payload))
            metrics = parser_level_metrics(
                book, spec, quality_engine=self.quality_engine
            )
        except Exception as exc:
            return (
                BackendRunResult(
                    document_id=spec.id,
                    backend=adapter.name,
                    status="failed",
                    elapsed_seconds=elapsed,
                    backend_version=version,
                    parser_profile=profile,
                    error=(
                        "BookIR normalization/metrics failed: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                ),
                None,
            )

        gold_metrics: Dict[str, object] = {}
        gold_evidence: Dict[str, object] = {}
        gold_gate_failures: List[str] = []
        if gold is not None:
            gold_result = evaluate_gold(book, gold)
            gold_metrics = dict(gold_result.metrics)
            gold_evidence = dict(gold_result.evidence)
            failures, baseline_deltas = evaluate_gold_gate(
                gold_metrics,
                thresholds=spec.gold_thresholds.get(adapter.name, {}),
                baselines=spec.gold_baselines.get(adapter.name, {}),
                max_regression=spec.gold_max_regression.get(adapter.name, {}),
            )
            gold_gate_failures = failures
            if baseline_deltas:
                gold_metrics["baseline_deltas"] = baseline_deltas

        bookir_path = stable_dir / "bookir.json"
        bookir_path.write_text(book.to_json() + "\n", encoding="utf-8")
        if gold_evidence:
            (stable_dir / "gold-evidence.json").write_text(
                json.dumps(gold_evidence, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        warnings = self._warnings(spec, book, metrics)
        if gold is not None and gold.status != "reviewed":
            warnings.append(
                "gold annotation is draft; metrics are informational and cannot gate"
            )
        return (
            BackendRunResult(
                document_id=spec.id,
                backend=adapter.name,
                status="success",
                elapsed_seconds=elapsed,
                backend_version=version,
                parser_profile=profile,
                metrics=metrics,
                gold_metrics=gold_metrics,
                gold_evidence=gold_evidence,
                gold_gate_failures=gold_gate_failures,
                warnings=warnings,
                bookir_path=str(bookir_path),
            ),
            book,
        )

    @staticmethod
    def _warnings(
        spec: CorpusDocumentSpec, book: Book, metrics: Dict[str, object]
    ) -> List[str]:
        warnings: List[str] = []
        parsed_pages = book.metadata.extra.get("page_count")
        if isinstance(parsed_pages, int) and parsed_pages != spec.page_count:
            warnings.append(
                f"parser page_count={parsed_pages} differs from "
                f"manifest={spec.page_count}"
            )
        if int(metrics.get("text_char_count", 0)) == 0:
            warnings.append("parser produced no normalized text")
        structure_hits = metrics.get("structure_hits", {})
        if isinstance(structure_hits, dict):
            missing = sorted(
                name for name, count in structure_hits.items() if not count
            )
            if missing:
                warnings.append(
                    "no structural nodes recovered for expected document features: "
                    + ", ".join(missing)
                )
        return warnings

    @staticmethod
    def _attach_cross_backend_proxies(
        runs: List[BackendRunResult], books: Dict[str, Book]
    ) -> None:
        successful = [run for run in runs if run.status == "success"]
        if not successful:
            return
        max_chars = max(
            int(run.metrics.get("text_char_count", 0)) for run in successful
        )
        tokens = {backend: token_set(book) for backend, book in books.items()}
        for run in successful:
            chars = int(run.metrics.get("text_char_count", 0))
            run.metrics["relative_text_coverage"] = (
                round(chars / max_chars, 4) if max_chars else None
            )
            peer_scores = [
                score
                for backend, peer_tokens in tokens.items()
                if backend != run.backend
                for score in [token_jaccard(tokens[run.backend], peer_tokens)]
                if score is not None
            ]
            run.metrics["text_consensus_jaccard_mean"] = (
                round(mean(peer_scores), 4) if peer_scores else None
            )
            run.metrics["consensus_peer_count"] = len(peer_scores)

    @staticmethod
    def _multiprocessing_context() -> multiprocessing.context.BaseContext:
        methods = multiprocessing.get_all_start_methods()
        return multiprocessing.get_context("fork" if "fork" in methods else "spawn")

    @staticmethod
    def _close_queue(result_queue: object) -> None:
        close = getattr(result_queue, "close", None)
        if callable(close):
            close()
        join_thread = getattr(result_queue, "join_thread", None)
        if callable(join_thread):
            join_thread()
