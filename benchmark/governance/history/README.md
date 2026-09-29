# Benchmark change history

This directory is for immutable post-merge records produced from a successful
Milestone 19 change-control report.

Create a record from the preserved PR evidence:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli change-control-record \
  artifacts/benchmark-change-control/change-report.json \
  artifacts/benchmark-change-control/reviews.json \
  --author <pr-author> \
  --merged-commit <merge-commit-sha> \
  --recorded-by <maintainer> \
  --governance-release artifacts/reviewed-accuracy-governance/governance-release.json
```

A history record pins:

- the merge commit;
- base/head refs from the PR report;
- change-report SHA-256;
- optional governance-release SHA-256;
- governed paths and categories;
- independent approvers;
- recorder identity and timestamp.

Existing history files cannot be overwritten with different content.
