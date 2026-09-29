# Review batches

This directory stores explicit independent-review assignments for benchmark
gold targets.

A committed batch must name reviewer A and reviewer B. Those identities must be
different. An optional adjudicator must differ from both.

Assignments may only reference pages already present in
`benchmark/corpus/review-plan.json`.

Create a batch with:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli review-batch-create \
  --id <batch-id> \
  --created-by <maintainer> \
  --reviewer-a <reviewer-a> \
  --reviewer-b <reviewer-b> \
  --priorities high
```

Do not commit placeholder reviewer identities merely to populate this
directory. A batch should represent a real review assignment.
