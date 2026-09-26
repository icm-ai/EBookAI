"""Default structural reconstruction pipeline."""

from __future__ import annotations

from typing import Iterable, Optional

from book.domain.models import Book
from book.reconstruction.base import ReconstructionPass
from book.reconstruction.passes import (
    FootnoteAssociationPass,
    HeaderFooterRemovalPass,
    HeadingInferencePass,
    ParagraphMergePass,
)


class ReconstructionPipeline:
    """Apply deterministic reconstruction passes in a stable order."""

    def __init__(
        self,
        passes: Optional[Iterable[ReconstructionPass]] = None,
    ) -> None:
        self.passes = list(
            passes
            if passes is not None
            else (
                HeaderFooterRemovalPass(),
                HeadingInferencePass(),
                FootnoteAssociationPass(),
                ParagraphMergePass(),
            )
        )

    def run(self, book: Book) -> Book:
        result = book
        for reconstruction_pass in self.passes:
            result = reconstruction_pass.apply(result)
        return result
