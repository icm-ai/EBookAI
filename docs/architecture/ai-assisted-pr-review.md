# AI-assisted pull-request review: advisory evidence first (RFC)

**Status:** proposed, non-governed tooling. **Owner:** [Issue #9](https://github.com/icm-ai/EBookAI/issues/9).
**Pilot:** [PR #8](https://github.com/icm-ai/EBookAI/pull/8) (benchmark CI dependency),
followed by [PR #7](https://github.com/icm-ai/EBookAI/pull/7) (EPUB typography).

## Decision and trust boundary

AI reviewers may discover bugs and record evidence, but their assessments
**do not constitute GitHub APPROVED reviews**, nor do they override human
review, branch protections, benchmark governance, CI, or release attestation.

The current governed `governance_engine` category requires **two distinct
non-PR-author GitHub approvals** under
`benchmark/governance/change-control.json` and
`backend/src/book/benchmark/change_control.py`. GitHub usernames alone
cannot prove whether reviewers are two independent human persons. The current
policy and workflow also do not explicitly reject bot identities. **This is
a governance trust gap, not permission to count bots as humans.**

Because changing the governance engine/policy is itself governed, this RFC
and its evidence validator do **not** modify those rules. Any policy change
must first receive the existing independent approvals; it cannot approve
itself. PR #8 remains unmerged until its approvals are satisfied.

## Minimal v1 evidence contract (self-attested)

`backend/src/book/review_evidence.py` validates a JSON record with:

- `schema_version: "1"`, `kind: "ai-advisory"`
- `repository`, `pull_request`, and **the full 40-character `head_sha`**
- `review_date`, `reviewer: {identity_type: "ai_agent", agent_id,
  provider, model, execution_id}`
- `assessment`: `no_blocking_findings`, `needs_changes`, or `inconclusive`
- `summary`, `findings`, `checks` with evidence references, and
  `limitations`
- `human_approval_required: true`, always

Review evidence must be stored with its PR and head SHA, never silently
carried forward after a new commit or force-push. The tool fails on schema
errors, SHA mismatch, duplicate claimed agent/execution identifiers, or
cross-PR aggregation. The tool **does not** authenticate an AI provider,
attest execution identity, prove separate prompt contexts, independently
rerun tests, or check GitHub review permissions.

Even when two distinct declared agent IDs pass aggregation, the summary
explicitly returns:

```json
{
  "independence_authenticated": false,
  "github_approvals_checked": false,
  "satisfies_governance_approval": false,
  "human_approval_required": true
}
```

These booleans are intentionally not configurable.

### CLI

Validate the pilot evidence against the exact PR head commit:

```bash
PYTHONPATH=backend/src python -m book.review_evidence validate \
  docs/review-evidence/pr-8/chatgpt-advisory-20261018.json \
  --repo icm-ai/EBookAI --pr 8 \
  --head 93d666839a8b4465f425a95066c5f2345364c715
```

When a **real second agent** has independently produced a signed or
traceable report for the *same head SHA*, aggregate the two files:

```bash
PYTHONPATH=backend/src python -m book.review_evidence aggregate \
  docs/review-evidence/pr-8/chatgpt-advisory-20261018.json \
  second-independent-agent-review.json \
  --repo icm-ai/EBookAI --pr 8 \
  --head 93d666839a8b4465f425a95066c5f2345364c715
```

The second file is **not supplied in this PR**; this is an example of
the future interface, not a claim of an already executed agent.

Regression checks:

```bash
PYTHONPATH=backend/src pytest -q backend/tests/test_ai_review_evidence.py
```

The normal backend test job will run this file; no existing governance
workflow is altered.

## Independent reviewer plan

Two separate *actual executions* are required for an independence claim.
Prefer different providers/models and isolated prompts/contexts; at minimum
record independent execution IDs and evidence for each run. Running the
same model twice in one chat, assigning different persona labels, or copying
one report under another name is **not** independent review.

- Agent A: functional correctness, dependency pin, regression coverage and
  first failure in CI logs.
- Agent B: least-privilege GitHub Actions security, governance
  invariants, provenance, and rollback safety.
- Compare overlapping/disputed findings before a human maintainer decides.
- Model findings can be posted as comments or status artifacts, **never**
  as a fabricated `APPROVED` review.

No second independently executed agent is available in the current
conversation; only the actual first read-only analysis is recorded.

## Security controls for a later opt-in automated reviewer

- Treat code, documentation, issue comments and workflow logs from PRs as
  **untrusted instructions** (prompt-injection boundary).
- Use read-only `contents: read` / `pull-requests: read` credentials for
  analysis; avoid secrets, deploy keys and write-enabled tokens in untrusted
  checkout contexts. Do not use `pull_request_target` to run head code.
- Pin PR number, base SHA and head SHA before analysis, re-check before
  publishing evidence, and mark stale findings after updates.
- Keep reviewer permissions separate from any human approval identity.
- Restrict context to necessary diffs/test outputs; redact secrets and
  copyrighted/private materials; retain logs with bounded retention.
- Add time/size/cost limits, independent provider failure handling, false
  positive tracking and explicit disclosures of tools that were not used.
- **Do not modify** existing approvals, change-control thresholds, baseline
  requirements, reviewed-gold evidence, or PR merge policy.

## Phased rollout

1. **Phase A (this PR):** stdlib advisory evidence validator and sample
   single-agent PR #8 review, tests, documentation. No automatic model calls,
   no CI workflow modification and no merge authority.
2. **Phase B (separate PR):** actual independently invoked reviewer adapters
   with read-only GitHub access and non-blocking PR comment/check outputs.
   Measure quality and reproducibility first.
3. **Phase C (separately approved governance PR):** define eligible
   human-account attestations and machine-review role; if policy/engine
   changes, receive the pre-existing approval floor before merging.

### Closing PR #8 and PR #7

PR #8's missing `fitz` dependency has a minimal fix with green primary CI,
but still needs **two eligible independent non-author human reviews**.
When #8 is approved and merged, refresh PR #7 against the updated
`develop` branch and re-run the governed change-control check. Only then
merge the typography feature if all required checks pass. AI evidence from
this RFC does **not** accelerate that permission step.
