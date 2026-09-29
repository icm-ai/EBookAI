"""CLI for rights-cleared corpus materialization and parser benchmarks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

from book.benchmark.baseline import (
    build_reviewed_baseline,
    load_baseline_leaderboard,
    register_reviewed_baseline,
    write_reviewed_baseline,
)
from book.benchmark.corpus import CorpusStore
from book.benchmark.gold import evaluate_gold, evaluate_gold_gate, load_gold_annotation
from book.benchmark.governance import (
    BenchmarkGovernancePolicy,
    build_governance_release_manifest,
    evaluate_governance,
    run_governed_accuracy_ci,
    write_governance_outputs,
)
from book.benchmark.leaderboard import (
    LeaderboardPolicy,
    ParserLeaderboard,
    build_leaderboard,
    compare_leaderboards,
    write_leaderboard,
)
from book.benchmark.models import BenchmarkReport, CorpusManifest
from book.benchmark.report import write_markdown
from book.benchmark.review_plan import (
    ReviewPlan,
    render_review_plan_markdown,
    review_plan_coverage,
    review_plan_summary,
    validate_review_plan,
)
from book.benchmark.runner import ParserBenchmarkRunner
from book.domain.models import Book

DEFAULT_MANIFEST = Path("benchmark/corpus/manifest.json")
DEFAULT_CACHE = Path(".cache/ebookai/corpus")
DEFAULT_LEADERBOARD_POLICY = Path("benchmark/leaderboard/policy.json")
DEFAULT_REVIEW_PLAN = Path("benchmark/corpus/review-plan.json")
DEFAULT_GOVERNANCE_POLICY = Path("benchmark/governance/policy.json")
DEFAULT_BASELINE_REGISTRY = Path("benchmark/leaderboard/baselines/registry.json")
DEFAULT_PROVENANCE_REGISTRY = Path("benchmark/corpus/provenance/registry.json")


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

    leaderboard = subparsers.add_parser(
        "leaderboard", help="Build a coverage-aware parser gold leaderboard"
    )
    leaderboard.add_argument("results", type=Path)
    leaderboard.add_argument("--output", type=Path, required=True)
    leaderboard.add_argument("--policy", type=Path, default=DEFAULT_LEADERBOARD_POLICY)
    leaderboard.add_argument(
        "--include-draft",
        action="store_true",
        help="Include draft annotations for exploratory, non-gating rankings",
    )
    leaderboard.add_argument(
        "--baseline",
        type=Path,
        help="Optional saved leaderboard.json to compare for metric regressions",
    )
    leaderboard.add_argument(
        "--max-regression",
        type=float,
        help="Override allowed per-metric regression for baseline comparison",
    )

    baseline_create = subparsers.add_parser(
        "baseline-create",
        help="Freeze a provenance-pinned reviewed-only leaderboard baseline",
    )
    baseline_create.add_argument("leaderboard", type=Path)
    baseline_create.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    baseline_create.add_argument("--output", type=Path, required=True)

    baseline_register = subparsers.add_parser(
        "baseline-register",
        help="Register an immutable reviewed baseline version and optionally activate it",
    )
    baseline_register.add_argument("baseline", type=Path)
    baseline_register.add_argument("--id", required=True)
    baseline_register.add_argument(
        "--registry",
        type=Path,
        default=DEFAULT_BASELINE_REGISTRY,
    )
    baseline_register.add_argument(
        "--no-activate",
        action="store_true",
        help="Register the version without making it active",
    )

    governance_check = subparsers.add_parser(
        "governance-check",
        help="Validate reviewed gold, consensus provenance and active baseline state",
    )
    governance_check.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    governance_check.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_GOVERNANCE_POLICY,
    )
    governance_check.add_argument(
        "--baseline-registry",
        type=Path,
        default=DEFAULT_BASELINE_REGISTRY,
    )
    governance_check.add_argument(
        "--provenance-registry",
        type=Path,
        default=DEFAULT_PROVENANCE_REGISTRY,
    )
    governance_check.add_argument("--output", type=Path, required=True)

    governance_ci = subparsers.add_parser(
        "governance-ci",
        help="Run bootstrap governance or strict reviewed-gold accuracy regression",
    )
    governance_ci.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    governance_ci.add_argument(
        "--policy",
        type=Path,
        default=DEFAULT_GOVERNANCE_POLICY,
    )
    governance_ci.add_argument(
        "--baseline-registry",
        type=Path,
        default=DEFAULT_BASELINE_REGISTRY,
    )
    governance_ci.add_argument(
        "--provenance-registry",
        type=Path,
        default=DEFAULT_PROVENANCE_REGISTRY,
    )
    governance_ci.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    governance_ci.add_argument("--output", type=Path, required=True)
    governance_ci.add_argument("--timeout", type=float, default=300.0)

    review_plan = subparsers.add_parser(
        "review-plan", help="Validate and summarize the gold human-review queue"
    )
    review_plan.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    review_plan.add_argument("--plan", type=Path, default=DEFAULT_REVIEW_PLAN)
    review_plan.add_argument("--output", type=Path)
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
    if args.command == "leaderboard":
        report = BenchmarkReport.load(args.results)
        policy = LeaderboardPolicy.load(args.policy)
        if args.include_draft:
            policy = LeaderboardPolicy(
                accuracy_paths=policy.accuracy_paths,
                include_draft=True,
                minimum_annotated_pages=policy.minimum_annotated_pages,
                minimum_annotated_documents=policy.minimum_annotated_documents,
                maximum_metric_regression=policy.maximum_metric_regression,
            )
        board = build_leaderboard(report, policy=policy)
        json_path, markdown_path = write_leaderboard(board, args.output)
        failures = []
        if args.baseline is not None:
            failures = compare_leaderboards(
                board,
                load_baseline_leaderboard(args.baseline),
                maximum_metric_regression=args.max_regression,
            )
        print(
            json.dumps(
                {
                    "leaderboard": str(json_path),
                    "markdown": str(markdown_path),
                    "regressions": failures,
                },
                indent=2,
            )
        )
        return 0 if not failures else 1
    if args.command == "baseline-create":
        board = ParserLeaderboard.load(args.leaderboard)
        snapshot = build_reviewed_baseline(args.manifest, board)
        path = write_reviewed_baseline(snapshot, args.output)
        print(
            json.dumps(
                {
                    "baseline": str(path),
                    "manifest_sha256": snapshot.manifest_sha256,
                    "gold_sha256": snapshot.gold_sha256,
                },
                indent=2,
            )
        )
        return 0
    if args.command == "baseline-register":
        registry = register_reviewed_baseline(
            args.registry,
            args.baseline,
            args.id,
            activate=not args.no_activate,
        )
        print(json.dumps(registry.to_dict(), indent=2))
        return 0
    if args.command == "governance-check":
        policy = BenchmarkGovernancePolicy.load(args.policy)
        result = evaluate_governance(
            args.manifest,
            policy,
            args.baseline_registry,
            provenance_registry_path=args.provenance_registry,
        )
        release = build_governance_release_manifest(
            result,
            manifest_path=args.manifest,
            policy_path=args.policy,
            baseline_registry_path=args.baseline_registry,
            provenance_registry_path=args.provenance_registry,
        )
        paths = write_governance_outputs(result, release, args.output)
        print(
            json.dumps(
                {
                    "report": result.to_dict(),
                    "artifacts": [str(path) for path in paths],
                },
                indent=2,
            )
        )
        return 0 if result.ok else 1
    if args.command == "governance-ci":
        result = run_governed_accuracy_ci(
            manifest_path=args.manifest,
            policy_path=args.policy,
            baseline_registry_path=args.baseline_registry,
            provenance_registry_path=args.provenance_registry,
            output_dir=args.output,
            cache_dir=args.cache,
            timeout=args.timeout,
        )
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.ok else 1
    if args.command == "review-plan":
        manifest = CorpusManifest.load(args.manifest)
        plan = ReviewPlan.load(args.plan)
        validate_review_plan(plan, manifest)
        summary = review_plan_summary(plan)
        summary["coverage"] = review_plan_coverage(plan, manifest, args.manifest)
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                render_review_plan_markdown(plan),
                encoding="utf-8",
            )
        print(json.dumps(summary, indent=2))
        return 0
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
