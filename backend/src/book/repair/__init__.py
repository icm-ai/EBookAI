"""Auditable BookIR repair and patch application."""

from book.repair.ai_proposals import (
    AIRepairProposal,
    AIRepairProposalError,
    AIRepairProposalGenerator,
)
from book.repair.patch_engine import PatchEngine, PatchValidationError, PatchValidator
from book.repair.source_evidence import SourceEvidenceRenderer, SourceImageEvidence

__all__ = [
    "AIRepairProposal",
    "AIRepairProposalError",
    "AIRepairProposalGenerator",
    "PatchEngine",
    "PatchValidationError",
    "PatchValidator",
    "SourceEvidenceRenderer",
    "SourceImageEvidence",
]
