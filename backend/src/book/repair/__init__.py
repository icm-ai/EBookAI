"""Auditable BookIR repair and patch application."""

from book.repair.ai_proposals import (
    AIRepairProposal,
    AIRepairProposalError,
    AIRepairProposalGenerator,
)
from book.repair.patch_engine import (
    PatchEngine,
    PatchUndoError,
    PatchValidationError,
    PatchValidator,
)
from book.repair.source_evidence import SourceEvidenceRenderer, SourceImageEvidence

__all__ = [
    "AIRepairProposal",
    "AIRepairProposalError",
    "AIRepairProposalGenerator",
    "PatchEngine",
    "PatchUndoError",
    "PatchValidationError",
    "PatchValidator",
    "SourceEvidenceRenderer",
    "SourceImageEvidence",
]
