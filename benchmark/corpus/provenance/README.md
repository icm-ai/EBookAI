# Consensus provenance

This directory stores canonical review provenance for benchmark-grade
`reviewed` gold.

`registry.json` is empty while the real corpus has no canonical reviewed
pages.

When Milestone 17 consensus gold is explicitly published, Milestone 18 also
writes a canonical consensus audit below the document directory and updates the
registry with the exact source SHA-256, current gold SHA-256, reviewers,
adjudicators and audit SHA-256.

Do not mark a gold annotation `reviewed` by hand without corresponding
consensus provenance. The governance gate intentionally fails closed in that
state.
