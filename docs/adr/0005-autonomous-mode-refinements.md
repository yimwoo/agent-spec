# ADR-0005: Autonomous Mode Refinements — Research Fallback, Severity Gating, Multi-Reviewer Signoff

Status: accepted
Date: 2026-04-28
Related: `ADR-0003-supervised-run-protocol.md`,
`ADR-0004-autonomous-execution-profile.md`,
`DCR-0019-agentracing-dogfood-learnings-and-autonomous-mode.md`,
`R-142`, `R-143`, `R-144`
Builds on: ADR-0004
Resolves: `Q-020` (one-pack vs queue-drain semantics for autonomous mode)

## Context

ADR-0004 defined the basic autonomous execution profile: execute one context
pack, transform `pause_for_human` verdicts into blocked findings, halt on
hard limits.

After ADR-0004 shipped, DCR-0019 was refined with three asks that ADR-0004
does not address:

1. **Research fallback** — when no executable context pack is ready, the
   loop should not just halt. It should be allowed to do bounded research
   (study repo artifacts, capture evidence-backed feature ideas, produce
   draft DCRs or proposed requirements).
2. **Severity gating** — not every `pause_for_human` is equally important.
   Naming/style asks are minor and can be logged-and-continued; product,
   security, scope, or architecture asks are high-impact and still need a
   human. ADR-0004's uniform "halt on every pause" is too binary.
3. **Multi-reviewer signoff** — ADR-0003 already defined
   `continuation_reviewer` and `quality_reviewer` profiles; ADR-0005 wires
   them into autonomous-mode decisions explicitly. Cheap reviewer for
   severity classification; strong reviewer for terminal `complete`
   verdicts.

ADR-0005 records these refinements without amending ADR-0004 (per the DCR
protocol, ADRs are frozen decisions; new architectural additions get a new
ADR).

## Decision

Add three additions to the autonomous execution profile.

### 1. Research fallback (sub-mode of autonomous)

When an autonomous loop runs and `aspec task next` returns no ready pack,
the loop MAY enter **research mode** instead of halting. Research mode is
strictly time-bounded, write-restricted, and produces inputs for humans
rather than implementation diffs.

**Allowed actions in research mode:**

- Read any file under the host repository.
- Read configured "adjacent" repositories listed in
  `.agentspec/config.yml` under `autonomous_mode.research_sources` (MVP
  default: `[]` — same-repo only).
- Append to `reports/dogfood/<date>-<slug>.md` (per R-139).
- Append open-question entries with `raised_by: <run-id>` and an explicit
  `proposed: research_finding` marker.
- Create DCR stubs under `docs/change-requests/` with `Status: open`,
  `Classification: pending`, citing the research evidence.

**Forbidden actions:**

- Writes outside `reports/dogfood/`, `docs/discovery/open-questions.yml`,
  or `docs/change-requests/`.
- Calls to `aspec dcr accept`, `aspec requirement accept`, or any other
  artifact-acceptance command.
- Any git commit, push, branch, or tag operation.
- Network calls outside the configured runner.
- Producing a proposed requirement directly in `requirements.yml`. New
  requirements always go through a DCR first.

**Termination:**

Research mode terminates on the first of:

- `max_research_findings` produced (default `5` per run).
- `max_iterations` (per ADR-0003) reached.
- Reviewer emits `complete` (research session declared productive).
- Reviewer emits `halt` (no productive direction found).

### 2. Pause severity classification

The reviewer/controller MUST classify each `pause_for_human` verdict with
a `severity` field:

```json
{
  "decision": "pause_for_human",
  "severity": "minor",        // or "high"
  "reason": "...",
  ...
}
```

**`severity: minor`** is allowed only when the pause concerns:

- choice between two implementation alternatives that are functionally
  equivalent
- naming, style, or formatting preferences
- a default value where the active context pack does not constrain the
  choice
- routine elaboration of an existing accepted requirement

In autonomous mode, a `minor` severity pause results in:

- the chosen default being recorded as an `open-questions.yml` entry with
  `proposed: minor_default` and the chosen value
- the loop continues with that default as the working assumption

**`severity: high`** is required whenever the pause concerns:

- product positioning, scope expansion, or non-goal redefinition
- security, secrets, credentials, or compliance
- architectural choice between non-equivalent alternatives
- modification or supersession of an existing accepted ADR or requirement
- destructive operations on shared state

In autonomous mode, a `high` severity pause results in:

- a DCR stub being drafted under `docs/change-requests/` with the pause
  context
- the loop halts and surfaces the DCR to the human

### 3. Multi-reviewer signoff

Autonomous-mode runs use the reviewer profiles from ADR-0003:

- `continuation_reviewer` (cheap, fast) classifies severity for
  `pause_for_human` verdicts and decides minor-default values.
- `quality_reviewer` (strong, slow) is required to sign off before
  autonomous mode emits a terminal `complete` verdict. Without
  quality-reviewer signoff, autonomous mode degrades to `pause_for_human
  severity=high` and halts.

For research mode, only `quality_reviewer` evaluates whether findings are
substantive enough to leave the run in `complete` rather than `halt`.

Supervised mode is unaffected — it can use a single reviewer.

## Resolved Question

**Q-020:** Should autonomous mode operate strictly one-pack-per-invocation,
or may a single autonomous loop drain the entire ready queue?

**Resolution:** strict one-pack-per-invocation for the implementation
branch. The research fallback is a separate mode that runs until its own
termination conditions, but never executes more than one implementation
pack in a single invocation. Multi-pack drains are explicitly out of scope
and would require a future DCR.

## New Open Questions

- **Q-022** — How is `research_sources` configured? File paths, git
  refs, or a registry of trusted projects? MVP allows file paths only.
- **Q-023** — How does `continuation_reviewer` actually classify
  severity? Rule-based, model-based, or hybrid? MVP starts with a small
  rule list (paths/words) plus model fallback.
- **Q-024** — Should research-mode DCR drafts default to `Status: open`
  or `Status: classified, Classification: pending`? Both are pre-decision
  states; the DCR-0002 schema requires Classification, so research drafts
  use a `Classification: pending` value with an enum addition is needed.
  Until that addition lands, research drafts log as `open-questions.yml`
  entries only.

## Consequences

### Positive

- Autonomous loops make progress when the implementation queue is empty.
- Severity gating means substantive concerns still surface to humans
  while routine ones don't block the loop.
- Multi-reviewer signoff aligns autonomous mode with ADR-0003's existing
  profile structure — no new model abstractions needed.
- Research outputs are durable artifacts (per R-139) that survive
  sessions.

### Negative / Costs

- Three new states (research mode, severity classification, dual signoff)
  expand the run-state schema. Backwards compatibility for existing run
  records needs an explicit migration.
- Research mode is the most likely to produce noisy artifacts —
  open-questions and DCR drafts can pile up if the reviewer is too
  permissive.
- Severity classification is a model judgment call; mis-classification
  ("treated as minor what should be high") is a real risk.

### Neutral

- ADR-0004's hard limits are unchanged. Allowed-paths only, no
  destructive git, no remote pushes, no credential exfiltration, no
  artifact auto-acceptance — all still apply in research mode and to
  both severity classes.
- ADR-0005 does not change the executor model or the per-run iteration
  cap from ADR-0003.

## Implementation Guidance

The first implementation pack should add:

- `agentspec/run.py` — accept `mode: research` on run state; route
  `pause_for_human` through severity classification before applying the
  ADR-0004 transformation.
- `agentspec/review.py` — add `severity` field to verdict schema; default
  `null` for backwards compatibility.
- `agentspec/model_review.py` — implement severity classification rules
  + model fallback.
- `agentspec/policy.py` — encode the research-mode write restrictions as
  hard gates.
- `agentspec/cli.py` — `--research` flag on `run loop` (or implicit when
  `aspec task next` returns nothing in autonomous mode).
- Tests covering: severity classification rules, research-mode write
  restrictions, dual signoff requirement for `complete`.

ADR-0005 implementation MUST NOT ship before R-135 (basic autonomous
mode) lands. The order is: R-135 first, then R-142..R-144 layered on
top.

## Status of this ADR

Accepted on 2026-04-28 by yimwu after reviewing the DCR-0019 refinements
that followed ADR-0004's initial draft. Implementation requirements
R-142..R-144 are recorded with status `proposed-pending-acceptance` and
require verified implementation packs before promotion.
