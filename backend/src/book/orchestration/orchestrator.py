"""Quality-aware orchestration across interchangeable parser adapters."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from book.domain.models import Book
from book.orchestration.models import (
    AttemptStatus,
    OrchestrationResult,
    ParserAttempt,
    StopReason,
)
from book.orchestration.policy import OrchestratorPolicy
from book.parsers.base import ParserBackendError, ParserBackendUnavailable
from book.parsers.registry import ParserRegistry
from book.quality import QualityEngine, QualityReport
from book.reconstruction import ReconstructionPipeline


class ParserOrchestrator:
    """Run parsers from cheap/preferred to stronger fallbacks using quality feedback."""

    def __init__(
        self,
        registry: ParserRegistry,
        *,
        reconstruction: Optional[ReconstructionPipeline] = None,
        quality_engine: Optional[QualityEngine] = None,
        policy: Optional[OrchestratorPolicy] = None,
    ) -> None:
        self.registry = registry
        self.reconstruction = reconstruction or ReconstructionPipeline()
        self.quality_engine = quality_engine or QualityEngine()
        self.policy = policy or OrchestratorPolicy()

    def run(
        self,
        path: Path,
        *,
        required_features: Iterable[str] = (),
    ) -> OrchestrationResult:
        path = Path(path)
        requirements: Set[str] = set(required_features)
        attempts: List[ParserAttempt] = []
        attempted_names: Set[str] = set()
        executed_attempts = 0

        best_book: Optional[Book] = None
        best_report: Optional[QualityReport] = None
        best_parser: Optional[str] = None

        while executed_attempts < self.policy.max_attempts:
            candidates = self.registry.candidates(
                path,
                required_features=requirements,
                available_only=False,
            )
            candidates = [
                adapter
                for adapter in self.policy.order(candidates)
                if adapter.name not in attempted_names
            ]
            if not candidates:
                break

            adapter = candidates[0]
            attempted_names.add(adapter.name)
            required_snapshot = tuple(sorted(requirements))

            if not adapter.is_available():
                attempts.append(
                    ParserAttempt(
                        parser_name=adapter.name,
                        status=AttemptStatus.UNAVAILABLE,
                        required_features=required_snapshot,
                        reason="runtime_unavailable",
                    )
                )
                continue

            try:
                raw_book = adapter.parse(path)
            except ParserBackendUnavailable as exc:
                attempts.append(
                    ParserAttempt(
                        parser_name=adapter.name,
                        status=AttemptStatus.UNAVAILABLE,
                        required_features=required_snapshot,
                        reason="runtime_unavailable",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                continue
            except ParserBackendError as exc:
                executed_attempts += 1
                attempts.append(
                    ParserAttempt(
                        parser_name=adapter.name,
                        status=AttemptStatus.FAILED,
                        required_features=required_snapshot,
                        reason="backend_error",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                continue

            executed_attempts += 1
            reconstructed = self.reconstruction.run(raw_book)
            report = self.quality_engine.analyze(reconstructed)
            decision = self.policy.gate.evaluate(report)

            attempt = ParserAttempt(
                parser_name=adapter.name,
                status=(
                    AttemptStatus.ACCEPTED
                    if decision.accepted
                    else AttemptStatus.REJECTED
                ),
                required_features=required_snapshot,
                quality_score=report.score,
                issue_counts=report.counts,
                issue_codes=tuple(sorted({issue.code for issue in report.issues})),
                reason="; ".join(decision.reasons),
            )
            attempts.append(attempt)

            if self._is_better(report, best_report):
                best_book = reconstructed
                best_report = report
                best_parser = adapter.name

            if decision.accepted:
                return self._finalize(
                    book=reconstructed,
                    report=report,
                    accepted=True,
                    selected_parser=adapter.name,
                    stop_reason=StopReason.QUALITY_ACCEPTED,
                    attempts=attempts,
                    requirements=requirements,
                )

            requirements.update(
                self.policy.escalation.required_features(
                    report,
                    current=requirements,
                )
            )

        if executed_attempts >= self.policy.max_attempts:
            stop_reason = StopReason.MAX_ATTEMPTS
        elif not attempts:
            stop_reason = StopReason.NO_CANDIDATES
        else:
            stop_reason = StopReason.EXHAUSTED

        return self._finalize(
            book=best_book,
            report=best_report,
            accepted=False,
            selected_parser=best_parser,
            stop_reason=stop_reason,
            attempts=attempts,
            requirements=requirements,
        )

    @staticmethod
    def _is_better(
        candidate: QualityReport,
        current: Optional[QualityReport],
    ) -> bool:
        if current is None:
            return True
        candidate_key = ParserOrchestrator._quality_rank(candidate)
        current_key = ParserOrchestrator._quality_rank(current)
        return candidate_key > current_key

    @staticmethod
    def _quality_rank(report: QualityReport) -> Tuple[float, int, int, int]:
        counts = report.counts
        return (
            report.score,
            -counts["error"],
            -counts["review"],
            -len(report.issues),
        )

    def _finalize(
        self,
        *,
        book: Optional[Book],
        report: Optional[QualityReport],
        accepted: bool,
        selected_parser: Optional[str],
        stop_reason: StopReason,
        attempts: List[ParserAttempt],
        requirements: Iterable[str],
    ) -> OrchestrationResult:
        required_features = tuple(sorted(set(requirements)))
        final_book = self._attach_audit(
            book,
            report=report,
            accepted=accepted,
            selected_parser=selected_parser,
            stop_reason=stop_reason,
            attempts=attempts,
            required_features=required_features,
        )
        return OrchestrationResult(
            book=final_book,
            quality_report=report,
            accepted=accepted,
            selected_parser=selected_parser,
            stop_reason=stop_reason,
            attempts=list(attempts),
            required_features=required_features,
        )

    def _attach_audit(
        self,
        book: Optional[Book],
        *,
        report: Optional[QualityReport],
        accepted: bool,
        selected_parser: Optional[str],
        stop_reason: StopReason,
        attempts: List[ParserAttempt],
        required_features: Tuple[str, ...],
    ) -> Optional[Book]:
        if book is None:
            return None

        result = Book.from_dict(book.to_dict())
        if report is not None:
            result.metadata.extra.setdefault("quality", {})["report"] = report.to_dict()

        result.metadata.extra["orchestration"] = {
            "accepted": accepted,
            "selected_parser": selected_parser,
            "stop_reason": stop_reason.value,
            "required_features": list(required_features),
            "attempts": [attempt.to_dict() for attempt in attempts],
            "policy": self.policy.to_dict(),
        }
        return result
