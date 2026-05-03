# DCR-0035: Research mode review evidence contract

| Field | Value |
|---|---|
| Status | accepted |
| Classification | spike |
| Submitted | 2026-05-02 |
| Submitted by | automation dogfood |
| Decided by | user |
| Decided on | 2026-05-02 |
| Confidence | medium |

## Summary

Research-mode autonomous runs can produce a valid durable proposal and pass
verification, then still halt because the quality reviewer does not recognize
the executor output as explicit acceptance-criteria evidence.

The control plane should make the evidence contract for research-mode
completion more deterministic so an executor can report exactly what the
quality reviewer expects.

## Evidence

- A research-mode run with no ready context pack created a DCR and linked open
  question inside the allowed research paths.
- The executor reported touched paths, covered requirements and questions,
  source-link verification, parse checks, DCR discovery, `git diff --check`,
  `aspec doctor`, and `aspec drift`.
- The first review produced a minor auto-continued pause because no
  deterministic auto-continue rule matched the output.
- The second review halted with a high-severity DCR because the quality
  reviewer required explicit acceptance-criteria evidence in the executor
  output, even though the output named the proposal artifact, verification
  commands, and covered requirements.
- Follow-up dogfood run `research-20260502T045240Z` in agentracing produced
  the same minor pause when the first `aspec run result` payload omitted the
  advertised runner-result fields. Resubmitting with
  `schema=agentspec.runner_result.v0`, `touched_paths`, and
  `test_status=passed` completed successfully. The issue is therefore not only
  reviewer wording; the CLI/reviewer contract should either reject underspecified
  result payloads before review or make the required fields unmistakable.

## Proposed Change

Run a narrow spike to define and enforce a research-mode result contract:

- Add an explicit `acceptance_evidence` field, or document a required structured
  shape inside `executor_output`, for research-mode results.
- Include durable artifact paths, allowed-path confirmation, source checks,
  verification commands, covered requirement IDs, and whether a task/context
  pack was intentionally not created.
- Teach deterministic or quality review to recognize that structured evidence
  before escalating to a high-severity pause.
- Preserve the conservative halt behavior for genuinely ambiguous architecture,
  governance, credential, destructive-operation, or remote-push concerns.

## Impact Assessment

Affected requirements:

- Autonomous research fallback should remain useful when no ready task exists.
- Severity-routed pause behavior should avoid high-severity DCR noise for
  adequately evidenced research-only proposals.
- Multi-reviewer completion should remain conservative, but the executor and
  reviewer should share a clear evidence contract.

## Acceptance Criteria

- A future context pack defines the research-mode completion evidence schema or
  required output template.
- Tests or fixtures cover a research-only proposal that passes, a minor
  unclassified pause that auto-continues, and a genuinely high-severity pause
  that still produces a DCR and halts.
- Existing autonomous-mode hard limits remain unchanged.

## Spike Outcome

See `docs/discovery/spikes/research-mode-review-evidence-contract.md`.
