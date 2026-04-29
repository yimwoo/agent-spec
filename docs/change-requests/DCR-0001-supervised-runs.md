# DCR-0001: Supervised Runs / Agent Reply Loop

| Field | Value |
|---|---|
| Status | accepted |
| Classification | **spike** (with required ADR before implementation) |
| Submitted | 2026-04-28 |
| Submitted by | yimwu (project owner), drafted by Claude pilot agent |
| Decided by | yimwu |
| Decided on | 2026-04-28 |
| Confidence | medium |
| Target milestone | V2 (post-MVP) |

## Summary

Add a bounded, file-backed loop in which a code agent executes a task context
pack, AgentSpec collects the resulting output, diff, test results, and logs, a
reviewer model produces structured feedback, and the same or a different
executor continues the task — until the loop terminates on success, exhaustion
of an iteration cap, a policy gate, or a human approval requirement.

## Motivation

Task context packs (D-12.12) bound the *intent* of a single attempt, but
nothing in the current architecture bounds a *sequence* of attempts. Today, a
human must orchestrate the inner loop manually: dispatch the agent, read the
output, decide whether to continue, hand back feedback. That is the moment
where most agent productivity is lost — not in the writing, but in the
review-and-resume cycle.

A supervised run formalizes that loop while keeping AgentSpec's safety
posture (D-23.4 Automation Permissions): every iteration writes only inside
the pack's allowed paths, every iteration produces a verifiable diff, and any
policy-flagged change halts for human approval.

## Proposed Change

Introduce three new runtime concepts and one persistent artifact tree:

1. **Run Orchestrator** — a new core component that, given a task context pack,
   drives an executor → collector → reviewer → executor cycle bounded by a
   configurable `max_iterations` cap.
2. **Reviewer interface** — a structured-output contract for a model (or static
   analyzer) that returns issues with severity, file references, and a
   suggested next action.
3. **Run state on disk** — `agent/runs/<run-id>/` containing per-iteration
   JSONL audit records (executor invocation, diff hash, test summary,
   reviewer findings, policy verdict). Aligns with D-23.6 Audit, which
   already designates `agent/runs/` as the JSONL audit location.
4. **Policy gate hook** — a pluggable evaluator (D-12.17 Policy Engine) that
   classifies each proposed change as `auto-continue`, `pause-for-review`, or
   `halt`, based on touched paths, test results, and risk classification.

A run terminates when **any** of the following holds:

- success criteria from the context pack are met
- `max_iterations` reached
- policy gate returns `halt`
- pause-for-review is open and has not been resolved within a timeout
- the human approver explicitly halts

## Source Section References

Existing `D-*` anchors this change touches:

- `D-07` Architectural Principles — extends "orchestrator-subagent for bounded
  analysis" from analysis to *execution*; stretches "one writer by default"
  and therefore requires an ADR.
- `D-12` Core Runtime Components — adds new components (Run Orchestrator,
  Reviewer wrapper) to the runtime.
- `D-12.12` Context Pack Builder — supervised runs *consume* packs; the pack
  schema may need optional fields (`max_iterations`, `reviewer_profile`).
- `D-12.17` Policy Engine — supervised runs are the first real client of the
  policy engine; this DCR pressures that component to become concrete.
- `D-23.4` Automation Permissions — supervised runs must comply with the
  existing automation gates (allowed paths, branch isolation, no auto-merge,
  human review for write-capable jobs).
- `D-23.6` Audit — `agent/runs/` JSONL is already designated; this DCR
  populates it.
- `D-24` Observability and Evaluation — run logs become the primary input
  for evaluation harnesses.

Proposed new design-doc sections (added in a future re-ingest, not by editing
the snapshot):

- `D-12.18` Run Orchestrator
- `D-12.19` Reviewer Interface
- `D-23.7` Supervised Run Permissions

## Impact Assessment

### Existing requirements affected

| Req | Source | Type of impact | Action |
|---|---|---|---|
| `R-001` | D-02 | Tasks must reference sources, ADRs, requirements, code, tests; supervised runs add **iteration evidence** to that reference set. | Extend acceptance criteria when DCR accepted; no immediate rewrite. |
| `R-007` | D-03 | CLI surface grows by `agentspec run …`. | New requirements (R-127..R-130) handle this; R-007 unchanged. |
| `R-009` (drift) | D-03 | Supervised-run iterations produce diffs; drift checker should ingest them. | Defer — no V1 change. |
| Any req citing `D-12.17` (Policy Engine) | various | Policy Engine moves from latent to active. | Re-evaluate during spike. |
| Any req citing `D-23.4` (Automation Permissions) | various | All listed gates apply unchanged; supervised runs are an *instance* of the existing rule, not an exception. | None — confirms existing rules. |
| Any req citing `D-23.6` (Audit) | various | `agent/runs/` JSONL becomes load-bearing. | None now; verify during spike. |

### Existing task context packs affected

- `T-001` (markdown sectionizer) — **not affected**. Sectionizer is independent of run orchestration.

### Source / spec docs needing updates

- `docs/spec/runtime-architecture.md` — add Run Orchestrator and Reviewer
  components once the spike concludes and ADR-0003 is accepted.
- `docs/spec/security-and-governance.md` — add supervised-run permission
  matrix.
- `docs/spec/observability-and-evaluation.md` — formalize run-log schema.
- `docs/spec/spec-index.md` — index the new sections.
- `docs/source/src-0001-agentspec-design-doc.md` — **not edited directly**;
  a re-ingest is required to add D-12.18 / D-12.19 / D-23.7 in a way that
  preserves canonical content hashes.

### Code modules (eventual; no work in this milestone)

- `agentspec/run.py` (new) — Run Orchestrator
- `agentspec/review.py` (new) — Reviewer interface and default adapter
- `agentspec/policy.py` (new or extracted) — policy gate evaluation
- `agentspec/cli.py` — `agentspec run start | resume | inspect | abort`
- `agentspec/io.py` — JSONL run-log writer helpers
- `agentspec/task.py` — optional `max_iterations` / `reviewer_profile` fields
  on context packs

### Open questions raised

| ID | Question |
|---|---|
| `Q-012` | What reviewer model is used by default in supervised runs, and is the choice configurable per-repo or per-task? |
| `Q-013` | What is the default `max_iterations` cap, and how should it be tuned per task type (small fix vs. large refactor)? |
| `Q-014` | Should `agent/runs/` state be committed to git, `.gitignore`'d, or split (audit metadata committed, raw outputs ignored)? |

## Proposed new requirements

All recorded with `status: proposed-pending-acceptance`. They flip to
`accepted` only after the spike completes and ADR-0003 is accepted.

- `R-127` (P2) — AgentSpec supports a bounded supervised run that executes a
  single context pack with a `max_iterations` cap, allowed-paths enforcement,
  and policy-gate evaluation between iterations.
- `R-128` (P2) — A supervised run collects per-iteration evidence (executor
  output, diff, test results, logs) into `agent/runs/<run-id>/` as JSONL
  audit records.
- `R-129` (P2) — A reviewer model produces structured feedback (issue list
  with severity, file references, suggested next action) consumable by the
  next iteration.
- `R-130` (P2) — A supervised run halts and requires explicit human approval
  when the policy engine classifies a change as risky.

## Disposition

**Recommended classification: `spike`, with a mandatory follow-up ADR
(`ADR-0003`) before any production implementation requirement flips from
`proposed-pending-acceptance` to `accepted`.**

Rationale:

- The change introduces a new top-level runtime component (Run Orchestrator)
  and bends the "one writer by default" principle from D-07. That is an
  architectural decision, not a tactical one — it must be recorded as an
  ADR.
- Multiple unknowns (reviewer choice, iteration cap, run-log retention) are
  better resolved by a small executable prototype than by spec debate.
- Phase 9 of the rollout (D-28.10 Automation) is the natural home for the
  *productized* version; the spike de-risks that phase.

Required follow-ups:

- Spike task: `T-004-spike-supervised-runs` (to be created when capacity is
  available; **not** created by this DCR intake). `T-003` is already
  reserved for the DCR-0002 schema bootstrap.
- ADR: `ADR-0003-supervised-run-protocol` (drafted from spike findings).
- Re-ingest of the design doc to add `D-12.18` / `D-12.19` / `D-23.7` once
  ADR-0003 is accepted.

**Do not** create implementation context packs from R-127..R-130 yet. They
are gated by ADR-0003.

## Acceptance Criteria

This DCR is considered fully addressed when:

1. `T-004-spike-supervised-runs` has produced a written spike report under
   `docs/discovery/spikes/` (new subdirectory; out of scope for this DCR).
2. `ADR-0003-supervised-run-protocol` is accepted, citing the spike.
3. Q-012, Q-013, and Q-014 are resolved or carried forward into ADR-0003.
4. R-127..R-130 are flipped to `accepted` and have associated context packs.

Until then, this DCR remains in classification `spike` with `Status: classified`.
