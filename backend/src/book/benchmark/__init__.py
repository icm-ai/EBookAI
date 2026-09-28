"""Rights-cleared real-world parser benchmark utilities."""

from book.benchmark.baseline import (
    ReviewedBaselineSnapshot,
    build_reviewed_baseline,
    load_baseline_leaderboard,
    write_reviewed_baseline,
)
from book.benchmark.consensus import (
    AdjudicationDecision,
    ConsensusConflict,
    GoldConsensusBundle,
    GoldConsensusStore,
    compare_reviewed_pages,
)
from book.benchmark.corpus import CorpusDownloadError, CorpusIntegrityError, CorpusStore
from book.benchmark.gold import (
    GoldAnnotation,
    GoldElement,
    GoldEvaluation,
    GoldPageAnnotation,
    GoldValidationError,
    evaluate_gold,
    evaluate_gold_gate,
    load_gold_annotation,
    validate_gold_against_spec,
)
from book.benchmark.leaderboard import (
    BackendLeaderboardEntry,
    LeaderboardPolicy,
    ParserLeaderboard,
    build_leaderboard,
    compare_leaderboards,
    render_leaderboard_markdown,
    write_leaderboard,
)
from book.benchmark.models import (
    BackendRunResult,
    BenchmarkReport,
    CorpusDocumentSpec,
    CorpusManifest,
    CorpusMaterialization,
)
from book.benchmark.report import render_markdown, write_markdown
from book.benchmark.review_plan import (
    ReviewPlan,
    ReviewTarget,
    render_review_plan_markdown,
    review_plan_coverage,
    review_plan_summary,
    validate_review_plan,
)
from book.benchmark.review_workbench import (
    GoldReviewDecision,
    GoldReviewSession,
    GoldReviewStore,
)
from book.benchmark.runner import ParserBenchmarkRunner, default_parser_registry

__all__ = [
    "AdjudicationDecision",
    "BackendRunResult",
    "BackendLeaderboardEntry",
    "BenchmarkReport",
    "CorpusDocumentSpec",
    "CorpusDownloadError",
    "CorpusIntegrityError",
    "CorpusManifest",
    "CorpusMaterialization",
    "CorpusStore",
    "ConsensusConflict",
    "GoldAnnotation",
    "GoldConsensusBundle",
    "GoldConsensusStore",
    "GoldElement",
    "GoldEvaluation",
    "GoldPageAnnotation",
    "GoldValidationError",
    "GoldReviewDecision",
    "GoldReviewSession",
    "GoldReviewStore",
    "LeaderboardPolicy",
    "ParserBenchmarkRunner",
    "ParserLeaderboard",
    "ReviewPlan",
    "ReviewTarget",
    "ReviewedBaselineSnapshot",
    "build_leaderboard",
    "build_reviewed_baseline",
    "compare_leaderboards",
    "compare_reviewed_pages",
    "default_parser_registry",
    "evaluate_gold",
    "evaluate_gold_gate",
    "load_baseline_leaderboard",
    "load_gold_annotation",
    "render_leaderboard_markdown",
    "render_markdown",
    "render_review_plan_markdown",
    "review_plan_coverage",
    "review_plan_summary",
    "validate_gold_against_spec",
    "validate_review_plan",
    "write_leaderboard",
    "write_markdown",
    "write_reviewed_baseline",
]
