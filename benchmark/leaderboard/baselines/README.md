# Reviewed parser baselines

Files in this directory are provenance-pinned reviewed-only leaderboard
snapshots.

`registry.json` is the version registry. A baseline becomes active only after
it is registered with an immutable id.

Do not hand-author a baseline or create one from draft gold. After consensus
gold has been canonically published, generate the snapshot with:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli baseline-create \
  artifacts/parser-benchmark/leaderboard/leaderboard.json \
  --manifest benchmark/corpus/manifest.json \
  --output benchmark/leaderboard/baselines/2026-10-initial.json
```

Then register and activate the immutable version:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli baseline-register \
  benchmark/leaderboard/baselines/2026-10-initial.json \
  --id 2026-10-initial
```

The baseline file must remain in this directory. Reusing an id for different
bytes is rejected.

The repository currently has no real baseline because the real corpus still
has no canonical reviewed pages. `registry.json` therefore intentionally has
`active_baseline_id: null`.
