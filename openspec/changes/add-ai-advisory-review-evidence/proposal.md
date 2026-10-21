# AI advisory review evidence

## Why

PR #10 introduces a schema, library API and CLI for self-reported AI review
evidence, but did not include the required OpenSpec proposal. The existing
architecture RFC describes the trust boundary without satisfying that process.
The validator also accepts malformed repository names, noncanonical dates and
single-report aggregation contrary to its intended contract.

## What Changes

- Specify single-report validation and optional repository, PR and head pins.
- Require nonempty owner/name components without whitespace and canonical
  ASCII YYYY-MM-DD calendar dates, without trimming invalid input into validity.
- Require at least two reports for aggregation through both the API and CLI.
- Preserve duplicate-identity rejection and advisory-only output invariants.
- Add focused regression tests using synthetic reports, without claiming a
  second actual independent review.

## Impact

- Affected specs: review-evidence (new capability).
- Affected code: backend/src/book/review_evidence.py and
  backend/tests/test_ai_review_evidence.py.
- Existing design: docs/architecture/ai-assisted-pr-review.md.
- No changes to workflows, governance policies, approval thresholds, benchmark
  engine, reviewed gold or baselines. No model calls or new dependencies.
- Previously accepted malformed records and single-report aggregates will fail
  with the existing validation-error status of 2 in the CLI.

## Approval and implementation status

Approved for the scope above on 2026-10-21 (Asia/Shanghai).

- Approver: 陈明, the user directing this repository task. No GitHub review
  identity is asserted by this record.
- Evidence: after being shown the proposal at commit
  `85b083808d174c188d8f4675d28f42e14843e4b0` and explicitly asked whether to
  approve it, the user replied “确认” in the same task.
- Scope: the Phase A advisory evidence contract and three validation
  corrections described above. This does not authorize governance policy
  changes, count as a GitHub APPROVED review or waive required CI checks.
- Timing: approval was obtained after the original implementation and the
  bug-fix corrections. This records the actual sequence and does not claim
  retroactive compliance with approval-before-implementation.

Implementation remains pending merge. Keep this proposal active until the
normal deployment and archiving process applies.
