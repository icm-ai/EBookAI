import base64
import hashlib
import json
from pathlib import Path

import fitz
import pytest
from book.benchmark.ablation import (
    AblationDecisionPolicy,
    AblationObservation,
    AblationPilotSpec,
    AblationReadiness,
    AblationRunArtifact,
    AblationTarget,
    AblationVariant,
    aggregate_variant,
    analyze_ablation,
    inspect_ablation_readiness,
    validate_pilot,
)
from book.benchmark.ablation_runner import (
    _apply_deterministic_repairs,
    run_local_ablation,
)
from book.benchmark.models import CorpusManifest
from book.benchmark.review_plan import ReviewPlan
from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    SourceRef,
)


def _variants():
    return (
        AblationVariant(
            id="A",
            label="Simple",
            added_component="direct parser",
            components=("pymupdf",),
            complexity_rank=1,
        ),
        AblationVariant(
            id="B",
            label="Routing",
            added_component="quality routing",
            components=("pymupdf", "orchestrator"),
            complexity_rank=2,
        ),
        AblationVariant(
            id="C",
            label="Repair",
            added_component="deterministic repair",
            components=("pymupdf", "orchestrator", "patch"),
            complexity_rank=3,
        ),
        AblationVariant(
            id="D",
            label="AI",
            added_component="AI repair",
            components=("pymupdf", "orchestrator", "patch", "ai"),
            complexity_rank=4,
        ),
    )


def _spec(*, minimum_pages=8, require_human=True):
    buckets = tuple(f"bucket-{index}" for index in range(minimum_pages))
    return AblationPilotSpec(
        pilot_id="fixture-pilot",
        corpus_id="fixture-corpus",
        targets=tuple(
            AblationTarget(
                document_id="doc",
                page_index=index,
                bucket=bucket,
            )
            for index, bucket in enumerate(buckets)
        ),
        variants=_variants(),
        quality_metric_paths=("text.f1",),
        decision_policy=AblationDecisionPolicy(
            minimum_reviewed_pages=minimum_pages,
            required_buckets=buckets,
            minimum_quality_gain_to_keep=0.01,
            negligible_quality_gain=0.002,
            maximum_latency_multiplier=1.5,
            maximum_failure_rate_increase=0.0,
            minimum_review_burden_reduction=0.10,
            require_human_minutes_for_final=require_human,
        ),
    )


def _readiness(spec):
    keys = tuple(
        (target.document_id, target.page_index) for target in spec.targets
    )
    return AblationReadiness(
        pilot_id=spec.pilot_id,
        state="ready",
        reviewed_pages=len(keys),
        target_pages=len(keys),
        reviewed_buckets=tuple(
            sorted({target.bucket for target in spec.targets})
        ),
        required_buckets=tuple(
            sorted(spec.decision_policy.required_buckets)
        ),
        ready_targets=keys,
        pending_targets=(),
    )


def _observation(
    variant,
    *,
    quality,
    elapsed,
    issues,
    minutes,
    cost=0.0,
    valid=True,
):
    return AblationObservation(
        variant_id=variant,
        document_id="doc",
        page_indexes=tuple(range(8)),
        status="success",
        elapsed_seconds=elapsed,
        quality_macro=quality,
        metric_values={"text.f1": quality},
        review_issue_count=issues,
        manual_review_minutes=minutes,
        ai_cost_usd=cost,
        intervention_count=0 if variant in {"A", "B"} else 2,
        selected_parser="pymupdf",
        parser_attempts=1 if variant == "A" else 2,
        valid_for_decision=valid,
        invalid_reason="" if valid else "missing semantic fallback",
    )


def test_repository_occam_pilot_refuses_conclusions_without_reviewed_gold():
    root = Path(__file__).resolve().parents[2]
    spec = AblationPilotSpec.load(
        root / "benchmark" / "ablation" / "runtime-occam-v1.json"
    )
    readiness = inspect_ablation_readiness(
        spec,
        manifest_path=root / "benchmark" / "corpus" / "manifest.json",
        review_plan_path=root / "benchmark" / "corpus" / "review-plan.json",
        provenance_registry_path=(
            root / "benchmark" / "corpus" / "provenance" / "registry.json"
        ),
    )

    assert readiness.ok is True
    assert readiness.state == "waiting_for_review"
    assert readiness.reviewed_pages == 0
    assert readiness.target_pages == 10

    report = analyze_ablation(spec, readiness, [])
    assert report.conclusion_ready is False
    assert [item.verdict for item in report.decisions] == [
        "insufficient_evidence",
        "insufficient_evidence",
        "insufficient_evidence",
    ]


def test_occam_policy_keeps_routing_removes_noop_repair_and_makes_ai_optional():
    spec = _spec()
    readiness = _readiness(spec)
    artifact = AblationRunArtifact(
        pilot_id=spec.pilot_id,
        corpus_id=spec.corpus_id,
        observations=(
            _observation("A", quality=0.80, elapsed=8, issues=40, minutes=80),
            _observation("B", quality=0.83, elapsed=10, issues=24, minutes=56),
            _observation("C", quality=0.831, elapsed=10.4, issues=24, minutes=56),
            _observation(
                "D",
                quality=0.85,
                elapsed=20,
                issues=16,
                minutes=40,
                cost=2.4,
            ),
        ),
    )

    report = analyze_ablation(spec, readiness, [artifact])

    assert report.conclusion_ready is True
    assert report.decisions[0].verdict == "keep"
    assert report.decisions[0].confidence == "decision_ready"
    assert report.decisions[1].verdict == "remove_candidate"
    assert report.decisions[2].verdict == "optional"
    assert report.decisions[2].latency_multiplier > 1.5
    assert any(
        "latency" in reason for reason in report.decisions[2].reasons
    )


def test_missing_human_minutes_keeps_verdict_provisional():
    spec = _spec()
    readiness = _readiness(spec)
    artifact = AblationRunArtifact(
        pilot_id=spec.pilot_id,
        corpus_id=spec.corpus_id,
        observations=(
            _observation("A", quality=0.80, elapsed=8, issues=40, minutes=None),
            _observation("B", quality=0.83, elapsed=10, issues=24, minutes=None),
            _observation("C", quality=0.84, elapsed=11, issues=20, minutes=None),
            _observation("D", quality=0.85, elapsed=12, issues=18, minutes=None),
        ),
    )

    report = analyze_ablation(spec, readiness, [artifact])

    assert report.conclusion_ready is False
    assert all(item.confidence == "provisional" for item in report.decisions)


def test_missing_d_variant_is_insufficient_not_a_fake_ai_conclusion():
    spec = _spec(require_human=False)
    readiness = _readiness(spec)
    artifact = AblationRunArtifact(
        pilot_id=spec.pilot_id,
        corpus_id=spec.corpus_id,
        observations=(
            _observation("A", quality=0.80, elapsed=8, issues=40, minutes=None),
            _observation("B", quality=0.83, elapsed=10, issues=24, minutes=None),
            _observation("C", quality=0.84, elapsed=11, issues=20, minutes=None),
        ),
    )

    report = analyze_ablation(spec, readiness, [artifact])

    assert report.conclusion_ready is False
    assert report.decisions[2].verdict == "insufficient_evidence"


def test_environment_invalid_variant_cannot_drive_architecture_decision():
    spec = _spec(require_human=False)
    readiness = _readiness(spec)
    artifact = AblationRunArtifact(
        pilot_id=spec.pilot_id,
        corpus_id=spec.corpus_id,
        observations=(
            _observation("A", quality=0.80, elapsed=8, issues=40, minutes=None),
            _observation(
                "B",
                quality=0.80,
                elapsed=8.1,
                issues=40,
                minutes=None,
                valid=False,
            ),
        ),
    )

    report = analyze_ablation(spec, readiness, [artifact])

    assert report.decisions[0].verdict == "insufficient_evidence"


def test_failed_pages_are_not_dropped_from_quality_mean():
    observations = [
        AblationObservation(
            variant_id="A",
            document_id="doc-a",
            page_indexes=(0,),
            status="success",
            elapsed_seconds=1,
            quality_macro=1.0,
        ),
        AblationObservation(
            variant_id="A",
            document_id="doc-b",
            page_indexes=(0,),
            status="failed",
            elapsed_seconds=1,
            error="boom",
        ),
    ]

    aggregate = aggregate_variant("A", observations)

    assert aggregate is not None
    assert aggregate.quality_macro == 0.5
    assert aggregate.failure_rate == 0.5


def test_duplicate_variant_document_across_artifacts_is_rejected():
    spec = _spec(require_human=False)
    readiness = _readiness(spec)
    observation = _observation(
        "A",
        quality=0.8,
        elapsed=8,
        issues=40,
        minutes=None,
    )
    first = AblationRunArtifact(
        pilot_id=spec.pilot_id,
        corpus_id=spec.corpus_id,
        observations=(observation,),
    )
    second = AblationRunArtifact(
        pilot_id=spec.pilot_id,
        corpus_id=spec.corpus_id,
        observations=(observation,),
    )

    with pytest.raises(ValueError, match="Duplicate variant/document"):
        analyze_ablation(spec, readiness, [first, second])


def test_pilot_validation_rejects_target_outside_review_plan(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "fixture-corpus",
                "documents": [
                    {
                        "id": "doc",
                        "title": "Doc",
                        "source_url": "https://example.invalid/doc.pdf",
                        "license_url": "https://example.invalid/license",
                        "rights_basis": "test",
                        "sha256": "a" * 64,
                        "document_class": "test",
                        "language": "en",
                        "page_count": 2,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "fixture-corpus",
                "targets": [
                    {
                        "document_id": "doc",
                        "page_index": 0,
                        "tasks": ["text"],
                        "difficulty_tags": ["simple"],
                        "priority": "high",
                        "rationale": "fixture",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    spec = AblationPilotSpec(
        pilot_id="bad",
        corpus_id="fixture-corpus",
        targets=(AblationTarget("doc", 1, "simple"),),
        variants=_variants(),
        quality_metric_paths=("text.f1",),
        decision_policy=AblationDecisionPolicy(
            minimum_reviewed_pages=1,
            required_buckets=("simple",),
        ),
    )

    with pytest.raises(ValueError, match="not in review plan"):
        validate_pilot(
            spec,
            CorpusManifest.load(manifest_path),
            ReviewPlan.load(plan_path),
        )


def test_deterministic_repair_applies_only_existing_quality_suggestions():
    source = SourceRef(
        page_index=0,
        bbox=(0.0, 0.0, 10.0, 10.0),
        parser="fixture",
        source_id="source",
    )
    book = Book(
        metadata=BookMetadata(
            title="Fixture",
            language="en",
            identifier="fixture",
            source_path="fixture.pdf",
        ),
        nodes=[
            BookNode(
                id="h1",
                type=NodeType.HEADING,
                content="One",
                source=[source],
                confidence=Confidence(),
                attrs={"level": 1},
            ),
            BookNode(
                id="h2",
                type=NodeType.HEADING,
                content="Three",
                source=[source],
                confidence=Confidence(),
                attrs={"level": 3},
            ),
        ],
    )

    repaired, applied, rejected = _apply_deterministic_repairs(book)

    assert applied == 1
    assert rejected == 0
    assert book.find_node("h2").attrs["level"] == 3
    assert repaired.find_node("h2").attrs["level"] == 2


def _reviewed_fixture(tmp_path):
    pdf_path = tmp_path / "source.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Hello ablation")
    document.save(pdf_path)
    document.close()
    pdf_bytes = pdf_path.read_bytes()
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    embedded = tmp_path / "source.pdf.b64"
    embedded.write_bytes(base64.b64encode(pdf_bytes))

    gold_dir = tmp_path / "gold"
    gold_dir.mkdir()
    (gold_dir / "doc.json").write_text(
        json.dumps(
            {
                "schema_version": "1",
                "document_id": "doc",
                "source_sha256": digest,
                "status": "reviewed",
                "annotated_by": "alice",
                "reviewed_by": "alice + bob",
                "notes": "",
                "pages": [
                    {
                        "page_index": 0,
                        "tasks": ["text"],
                        "elements": [
                            {
                                "id": "t1",
                                "type": "paragraph",
                                "text": "Hello ablation",
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "corpus_id": "fixture-corpus",
                "documents": [
                    {
                        "id": "doc",
                        "title": "Doc",
                        "source_url": "https://example.invalid/doc.pdf",
                        "license_url": "https://example.invalid/license",
                        "rights_basis": "test",
                        "sha256": digest,
                        "document_class": "test",
                        "language": "en",
                        "page_count": 1,
                        "expected_capabilities": ["native_text"],
                        "redistributable": True,
                        "embedded_base64_path": embedded.name,
                        "gold_annotations_path": "gold/doc.json",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    spec = AblationPilotSpec(
        pilot_id="fixture-pilot",
        corpus_id="fixture-corpus",
        targets=(AblationTarget("doc", 0, "simple"),),
        variants=_variants(),
        quality_metric_paths=("text.f1",),
        decision_policy=AblationDecisionPolicy(
            minimum_reviewed_pages=1,
            required_buckets=("simple",),
            require_human_minutes_for_final=False,
        ),
    )
    readiness = AblationReadiness(
        pilot_id=spec.pilot_id,
        state="ready",
        reviewed_pages=1,
        target_pages=1,
        reviewed_buckets=("simple",),
        required_buckets=("simple",),
        ready_targets=(("doc", 0),),
        pending_targets=(),
    )
    return spec, readiness, manifest


def test_local_runner_executes_simple_variant_on_reviewed_fixture(tmp_path):
    spec, readiness, manifest = _reviewed_fixture(tmp_path)

    artifact = run_local_ablation(
        spec,
        readiness,
        manifest_path=manifest,
        cache_dir=tmp_path / "cache",
        output_dir=tmp_path / "ablation",
        variants=("A",),
        timeout=10,
    )

    assert len(artifact.observations) == 1
    observation = artifact.observations[0]
    assert observation.variant_id == "A"
    assert observation.status == "success"
    assert observation.valid_for_decision is True
    assert observation.quality_macro is not None
    assert (tmp_path / "ablation" / "doc" / "A" / "bookir.json").is_file()


def test_local_runner_refuses_unreviewed_pilot(tmp_path):
    spec, readiness, manifest = _reviewed_fixture(tmp_path)
    not_ready = AblationReadiness(
        pilot_id=readiness.pilot_id,
        state="waiting_for_review",
        reviewed_pages=0,
        target_pages=1,
        reviewed_buckets=(),
        required_buckets=("simple",),
        ready_targets=(),
        pending_targets=(("doc", 0),),
    )

    with pytest.raises(ValueError, match="not evidence-ready"):
        run_local_ablation(
            spec,
            not_ready,
            manifest_path=manifest,
            cache_dir=tmp_path / "cache",
            output_dir=tmp_path / "ablation",
            variants=("A",),
        )
