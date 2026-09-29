# Reviewed gold campaigns

This directory contains source-pinned campaigns that turn selected review-plan
targets into independently reviewed benchmark truth.

A campaign spec names:

- exact document/page targets;
- the parser backend used by the review workbench;
- the backend set used to create the first reviewed leaderboard;
- the immutable baseline id and filename that will be activated only after real
  consensus review.

Campaign specs do **not** contain placeholder reviewer identities.

The first campaign is:

```text
first-reviewed-v1
  document: nist-eel-sp1500-101-v1
  PDF page index: 8
  tasks: headings + reading_order
  initial gold status: draft
  baseline id: first-reviewed-v1
```

Inspect its current state:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli campaign-status
```

Assign real independent reviewers only when those people are known:

```bash
PYTHONPATH=backend/src python -m book.benchmark.cli campaign-assign \
  --created-by <maintainer> \
  --reviewer-a <reviewer-a> \
  --reviewer-b <reviewer-b> \
  --adjudicator <reviewer-c>
```

Do not commit fabricated names to move the campaign forward.
