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

Pending maintainer review and approval of this proposal. No GitHub APPROVED
review or prior OpenSpec approval is claimed. The original feature already
exists in PR #10; this proposal does not retroactively satisfy its missing
approval-before-implementation step. The accompanying corrections restore
intended behavior under the bug-fix exception in openspec/AGENTS.md.

Before landing the feature, record the actual approver, date and review evidence
here. Do not archive this proposal or mark approval complete until that happens.
