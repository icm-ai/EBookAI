"""CLI for rights-cleared corpus materialization and parser benchmarks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from book.benchmark.corpus import CorpusStore
from book.benchmark.gold import evaluate_gold, evaluate_gold_gate, load_gold_annotation
from book.benchmark.models import BenchmarkReport, CorpusManifest
from book.benchmark.report import write_markdown
from book.benchmark.runner import ParserBenchmarkRunner
from book.domain.models import Book

DEFAULT_MANIFEST = Path("benchmark/corpus/manifest.json")
DEFAULT_CACHE = Path(".cache/ebookai/corpus")


def _csv(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _store(args: argparse.Namespace) -> CorpusStore:
    return CorpusStore(args.manifest, args.cache)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m book.benchmark.cli",
        description="Run parser-level benchmarks on rights-cleared real PDFs.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def corpus_args(command: argparse.ArgumentParser) -> None:
        command.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
        command.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
        command.add_argument(
            "--documents", help="Comma-separated corpus document ids (default: all)"
        )

    fetch = subparsers.add_parser("fetch", help="Materialize verified corpus PDFs")
    corpus_args(fetch)
    fetch.add_argument("--force", action="store_true")
    fetch.add_argument("--timeout", type=float, default=60.0)

    verify = subparsers.add_parser("verify", help="Verify cached corpus digests")
    corpus_args(verify)

    run = subparsers.add_parser("run", help="Run parsers on identical corpus bytes")
    corpus_args(run)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--backends", default="pymupdf,mineru,marker")
    run.add_argument("--timeout", type=float, default=300.0)
    run.add_argument("--no-fetch", action="store_true")

    report = subparsers.add_parser("report", help="Render benchmark JSON as Markdown")
    report.add_argument("results", type=Path)
    report.add_argument("--output", type=Path, required=True)

    gold_validate = subparsers.add_parser(
        "gold-validate", help="Validate source-pinned sparse gold annotations"
    )
    gold_validate.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    gold_validate.add_argument(
        "--documents", help="Comma-separated corpus document ids (default: all)"
    )

    gold_evaluate = subparsers.add_parser(
        "gold-evaluate", help="Evaluate an existing BookIR JSON against gold"
    )
    gold_evaluate.add_argument("bookir", type=Path)
    gold_evaluate.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    gold_evaluate.add_argument("--document", required=True)
    gold_evaluate.add_argument("--backend", default="pymupdf")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "fetch":
        results = _store(args).fetch(
            _csv(args.documents), force=args.force, timeout=args.timeout
        )
        print(json.dumps([item.to_dict() for item in results], indent=2))
        return 0
    if args.command == "verify":
        results = _store(args).verify(_csv(args.documents))
        print(json.dumps(results, indent=2))
        return 0 if all(bool(item["ok"]) for item in results) else 1
    if args.command == "run":
        store = _store(args)
        benchmark = ParserBenchmarkRunner(store, args.output)
        result = benchmark.run(
            document_ids=_csv(args.documents),
            backends=_csv(args.backends),
            timeout=args.timeout,
            fetch_missing=not args.no_fetch,
        )
        print(result.to_json())
        has_runtime_failure = any(
            run.status in {"failed", "timeout"} for run in result.runs
        )
        has_gold_gate_failure = any(run.gold_gate_failures for run in result.runs)
        return 0 if not (has_runtime_failure or has_gold_gate_failure) else 1
    if args.command == "report":
        result = BenchmarkReport.load(args.results)
        write_markdown(result, args.output)
        print(str(args.output))
        return 0
    if args.command == "gold-validate":
        manifest = CorpusManifest.load(args.manifest)
        results = []
        for spec in manifest.select(_csv(args.documents)):
            annotation = load_gold_annotation(args.manifest, spec)
            results.append(
                {
                    "document_id": spec.id,
                    "status": "valid" if annotation is not None else "unannotated",
                    "annotation_status": (
                        annotation.status if annotation is not None else None
                    ),
                    "annotated_pages": (
                        [page.page_index for page in annotation.pages]
                        if annotation is not None
                        else []
                    ),
                }
            )
        print(json.dumps(results, indent=2))
        return 0
    if args.command == "gold-evaluate":
        manifest = CorpusManifest.load(args.manifest)
        spec = manifest.select([args.document])[0]
        annotation = load_gold_annotation(args.manifest, spec)
        if annotation is None:
            raise ValueError(f"Document {spec.id!r} has no gold annotation")
        book = Book.from_json(args.bookir.read_text(encoding="utf-8"))
        evaluation = evaluate_gold(book, annotation)
        failures, baseline_deltas = evaluate_gold_gate(
            evaluation.metrics,
            thresholds=spec.gold_thresholds.get(args.backend, {}),
            baselines=spec.gold_baselines.get(args.backend, {}),
            max_regression=spec.gold_max_regression.get(args.backend, {}),
        )
        payload = evaluation.to_dict()
        payload["gate_failures"] = failures
        payload["baseline_deltas"] = baseline_deltas
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if not failures else 1
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
