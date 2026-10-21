## ADDED Requirements

### Requirement: Validate advisory evidence

The system SHALL validate schema version 1 AI advisory reports through the
library API and a single-file validate CLI command. Reports MUST include a
repository, positive integer PR number, lowercase 40-character head SHA,
reviewer identity, assessment, summary, checks, findings and limitations.
Optional repository, PR and head pins MUST reject mismatched reports.

#### Scenario: Validate a pinned report
- **WHEN** a complete report matches the requested repository, PR and head SHA
- **THEN** validation succeeds and does not claim governance approval

#### Scenario: Reject stale evidence
- **WHEN** the report head differs from the requested head SHA
- **THEN** validation fails and the CLI exits with status 2

### Requirement: Validate repository components

The system SHALL require exactly one slash separating nonempty owner and name
components, with no whitespace anywhere in the repository string. This is
syntax validation and MUST NOT be represented as repository authentication.

#### Scenario: Reject malformed provenance
- **WHEN** a repository is /name, owner/, whitespace-containing or has extra slashes
- **THEN** validation fails even when no repository pin is supplied

#### Scenario: Accept ordinary provenance
- **WHEN** a report declares icm-ai/EBookAI and otherwise satisfies the contract
- **THEN** repository syntax validation succeeds

### Requirement: Validate canonical calendar dates

The system SHALL require review_date to match ASCII YYYY-MM-DD exactly and
represent a valid calendar date. It MUST reject surrounding whitespace,
basic dates, ISO week dates and non-ASCII digits.

#### Scenario: Reject noncanonical dates
- **WHEN** review_date is 20261018, 2026-W42-7 or 2026-1-8
- **THEN** validation fails with a YYYY-MM-DD error

#### Scenario: Check leap-day validity
- **WHEN** review_date is 2024-02-29
- **THEN** calendar validation succeeds, while 2026-02-29 fails

### Requirement: Aggregate multiple advisory reports

The system SHALL aggregate at least two valid reports for the same repository,
PR and head SHA through both API and CLI. It MUST reject repeated declared
agent IDs or execution IDs. Counts MUST describe declared identities only.

#### Scenario: Reject insufficient reports
- **WHEN** zero or one report is supplied to the API or aggregate CLI
- **THEN** aggregation fails and the CLI exits with status 2 without success JSON

#### Scenario: Aggregate distinct reports
- **WHEN** two valid reports share the same PR and head and have distinct IDs
- **THEN** aggregation returns an advisory report count of two

#### Scenario: Reject incompatible reports
- **WHEN** reports have different repository, PR or head values, or duplicate IDs
- **THEN** aggregation fails

### Requirement: Preserve governance trust boundaries

The system SHALL require human_approval_required=true in input reports and
MUST NOT count advisory evidence as GitHub approvals. Aggregated output SHALL
always set independence_authenticated=false, github_approvals_checked=false,
satisfies_governance_approval=false and human_approval_required=true.
Existing governance policies and approval thresholds SHALL remain unchanged.

#### Scenario: Successful aggregation remains advisory
- **WHEN** all input reports pass validation and claim no blocking findings
- **THEN** all four output booleans retain the values required above

#### Scenario: Reject misleading reports
- **WHEN** a report claims a GitHub-approval kind, disables human approval or
  marks high/critical findings as no_blocking_findings
- **THEN** validation fails
