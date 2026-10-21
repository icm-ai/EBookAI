## 1. Proposal

- [x] 1.1 Inspect repository instructions, existing specs, PR code and RFC.
- [x] 1.2 Write the proposal and review-evidence requirement deltas.
- [x] 1.3 Run openspec validate add-ai-advisory-review-evidence --strict.
- [ ] 1.4 Obtain and record actual maintainer approval before landing the feature.

## 2. Existing behavior corrections

- [x] 2.1 Reject malformed owner/name repository values.
- [x] 2.2 Enforce canonical ASCII calendar dates and validate leap days.
- [x] 2.3 Require two reports in both aggregation entry points.
- [x] 2.4 Run focused API and CLI regression tests, preserving governance booleans.
- [x] 2.5 Validate the existing pinned single-report sample.
- [ ] 2.6 Run formatting checks and existing governance regression tests.

## 3. Merge readiness

- [ ] 3.1 Refresh against the corrected develop after the separate PR #8 fix lands.
- [ ] 3.2 Verify required CI checks on the final head without bypassing gates.

Unchecked items are pending or unverified, not evidence of approval or completion.

Local verification on 2026-10-21: 39 focused tests passed with Python 3.13.15
and pytest 8.4.2; the pinned sample passed; OpenSpec strict validation passed.
Existing governance tests could not collect because PyMuPDF/fitz is absent.
Black and isort are unavailable locally. CI verification remains required.
