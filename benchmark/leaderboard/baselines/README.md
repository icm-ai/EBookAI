# Reviewed parser baselines

Files in this directory are provenance-pinned reviewed-only leaderboard
snapshots.

Do not hand-author a baseline or create one from draft gold. After consensus
gold has been canonically published, generate the snapshot with:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli baseline-create \
  artifacts/parser-benchmark/leaderboard/leaderboard.json \
  --manifest benchmark/corpus/manifest.json \
  --output benchmark/leaderboard/baselines/first-reviewed.json
```

The command refuses to create a snapshot without canonical reviewed gold and
at least one eligible backend.

No real baseline is committed yet because the current real corpus seeds still
require independent human review.
