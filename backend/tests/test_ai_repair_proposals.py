import json

import pytest
from book.domain.models import (
    Book,
    BookMetadata,
    BookNode,
    Confidence,
    NodeType,
    PatchOperation,
    SourceRef,
)
from book.quality import IssueSeverity, QualityIssue
from book.repair import AIRepairProposalError, AIRepairProposalGenerator


def _source(source_id="source-1"):
    return SourceRef(
        page_index=3,
        bbox=(10.0, 20.0, 300.0, 400.0),
        parser="fixture",
        source_id=source_id,
    )


def _book():
    return Book(
        metadata=BookMetadata(
            title="Fixture",
            source_path="fixture.pdf",
        ),
        nodes=[
            BookNode(
                id="before",
                type=NodeType.PARAGRAPH,
                content="Previous paragraph.",
                source=[_source()],
                confidence=Confidence(0.95, 0.9, 0.95),
            ),
            BookNode(
                id="target",
                type=NodeType.PARAGRAPH,
                content="Th1s OCR text.",
                source=[_source()],
                confidence=Confidence(0.55, 0.9, 0.95),
            ),
            BookNode(
                id="after",
                type=NodeType.PARAGRAPH,
                content="Following paragraph.",
                source=[_source()],
                confidence=Confidence(0.95, 0.9, 0.95),
            ),
        ],
    )


def _issue():
    return QualityIssue(
        id="issue-low-extraction",
        code="low_confidence",
        severity=IssueSeverity.REVIEW,
        message="Extraction confidence is low.",
        node_ids=("target",),
        confidence=0.9,
        evidence={"axis": "extraction"},
    )


def _response(**overrides):
    payload = {
        "operation": "replace_content",
        "target_node_id": "target",
        "payload": {"content": "This OCR text."},
        "reason": "The supplied source-grounded context supports correcting 1 to i.",
        "confidence": 0.86,
        "evidence_node_ids": ["target"],
        "evidence_source_ids": ["source-1"],
    }
    payload.update(overrides)
    return json.dumps(payload)


def test_prompt_contains_issue_neighbor_context_and_provenance():
    prompt = AIRepairProposalGenerator().build_prompt(_book(), _issue())

    assert '"issue-low-extraction"' in prompt
    assert '"before"' in prompt
    assert '"target"' in prompt
    assert '"after"' in prompt
    assert '"source-1"' in prompt
    assert '"page_index": 3' in prompt


def test_valid_grounded_response_becomes_pending_patch():
    generator = AIRepairProposalGenerator()

    proposal = generator.parse_response(
        _book(),
        _issue(),
        _response(),
        provider="fixture-provider",
        model="fixture-model",
    )

    assert proposal.status == "pending"
    assert proposal.patch.operation == PatchOperation.REPLACE_CONTENT
    assert proposal.patch.target_node_id == "target"
    assert proposal.patch.payload == {"content": "This OCR text."}
    assert proposal.patch.applied is False
    assert proposal.evidence_node_ids == ("target",)
    assert proposal.evidence_source_ids == ("source-1",)
    assert len(proposal.grounding_hash) == 64


def test_ai_proposal_rejects_hallucinated_node_or_source_ids():
    generator = AIRepairProposalGenerator()

    with pytest.raises(AIRepairProposalError, match="invented evidence nodes"):
        generator.parse_response(
            _book(),
            _issue(),
            _response(evidence_node_ids=["target", "invented"]),
            provider="fixture-provider",
            model="fixture-model",
        )

    with pytest.raises(AIRepairProposalError, match="invented source ids"):
        generator.parse_response(
            _book(),
            _issue(),
            _response(evidence_source_ids=["fake-source"]),
            provider="fixture-provider",
            model="fixture-model",
        )


def test_ai_proposal_rejects_structural_operations_outside_allowlist():
    generator = AIRepairProposalGenerator()

    with pytest.raises(AIRepairProposalError, match="not allowed"):
        generator.parse_response(
            _book(),
            _issue(),
            _response(
                operation="delete_node",
                payload={},
            ),
            provider="fixture-provider",
            model="fixture-model",
        )


def test_ai_set_attribute_only_allows_safe_heading_level():
    book = _book()
    book.find_node("target").type = NodeType.HEADING
    issue = QualityIssue(
        id="heading-level",
        code="heading_hierarchy",
        severity=IssueSeverity.REVIEW,
        message="Heading level should be reviewed.",
        node_ids=("target",),
        evidence={},
    )
    generator = AIRepairProposalGenerator()

    proposal = generator.parse_response(
        book,
        issue,
        _response(
            operation="set_attribute",
            payload={"key": "level", "value": 2},
        ),
        provider="fixture-provider",
        model="fixture-model",
    )
    assert proposal.patch.operation == PatchOperation.SET_ATTRIBUTE
    assert proposal.patch.payload == {"key": "level", "value": 2}

    with pytest.raises(AIRepairProposalError, match="not allowed"):
        generator.parse_response(
            book,
            issue,
            _response(
                operation="set_attribute",
                payload={"key": "class", "value": "chapter"},
            ),
            provider="fixture-provider",
            model="fixture-model",
        )


def test_issue_without_source_grounded_target_cannot_request_ai_repair():
    issue = QualityIssue(
        id="book-level",
        code="empty_document",
        severity=IssueSeverity.ERROR,
        message="No nodes.",
    )

    with pytest.raises(AIRepairProposalError, match="no target nodes"):
        AIRepairProposalGenerator().build_prompt(_book(), issue)
