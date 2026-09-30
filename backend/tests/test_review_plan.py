import json
from pathlib import Path

import pytest

from book.benchmark import CorpusManifest
from book.benchmark.review_plan import (
    ReviewPlan,
    render_review_plan_markdown,
    review_plan_coverage,
    review_plan_summary,
    validate_review_plan,
)

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "benchmark" / "corpus" / "manifest.json"
PLAN_PATH = ROOT / "benchmark" / "corpus" / "review-plan.json"


def test_real_review_plan_covers_five_documents_and_25_pages():
    manifest = CorpusManifest.load(MANIFEST_PATH)
    plan = ReviewPlan.load(PLAN_PATH)

    validate_review_plan(plan, manifest)
    summary = review_plan_summary(plan)

    assert summary["target_count"] == 25
    assert summary["document_count"] == 5
    assert set(summary["documents"]) == {
        "nist-ballot-definition-prototype",
        "nist-eel-sp1500-101-v1",
        "nist-ai-rmf-1-0",
        "nist-sp1299-csf2-overview",
        "nist-sp1299-csf2-overview-ja",
    }
    assert summary["task_counts"]["reading_order"] == 25
    assert summary["task_counts"]["text"] >= 20
    assert summary["priority_counts"]["high"] >= 10


def test_review_plan_coverage_distinguishes_draft_from_unannotated():
    manifest = CorpusManifest.load(MANIFEST_PATH)
    plan = ReviewPlan.load(PLAN_PATH)

    coverage = review_plan_coverage(plan, manifest, MANIFEST_PATH)

    assert coverage["target_count"] == 25
    assert coverage["draft"] == 2
    assert coverage["reviewed"] == 0
    assert coverage["unannotated"] == 23
    assert {
        (item["document_id"], item["page_index"], item["status"])
        for item in coverage["targets"]
        if item["status"] == "draft"
    } == {
        ("nist-eel-sp1500-101-v1", 8, "draft"),
        ("nist-ai-rmf-1-0", 3, "draft"),
    }


def test_review_plan_rejects_out_of_range_page(tmp_path):
    manifest = CorpusManifest.load(MANIFEST_PATH)
    payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    payload["targets"][0]["page_index"] = 99
    path = tmp_path / "bad-plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    plan = ReviewPlan.load(path)

    with pytest.raises(ValueError, match="outside page_count"):
        validate_review_plan(plan, manifest)


def test_review_plan_rejects_duplicate_document_page():
    payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    payload["targets"].append(dict(payload["targets"][0]))

    with pytest.raises(ValueError, match="duplicate"):
        ReviewPlan.from_dict(payload)


def test_review_plan_markdown_marks_targets_as_not_reviewed_gold():
    plan = ReviewPlan.load(PLAN_PATH)

    markdown = render_review_plan_markdown(plan)

    assert "Gold Review Plan" in markdown
    assert "not reviewed gold" in markdown
    assert "nist-ai-rmf-1-0" in markdown
    assert "Japanese" not in markdown or "nist-sp1299-csf2-overview-ja" in markdown
