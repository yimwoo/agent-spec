# Supervised-Run Acceptance Review (R-127..R-130)

Recorded: 2026-04-28
Originating: T-029, DCR-0001, ADR-0003
Reviewer: Claude pilot agent (audit only — no code changes)

## Context

R-127..R-130 were filed alongside DCR-0001 (supervised runs spike) and
have remained `proposed-pending-acceptance` ever since. ADR-0003 is
accepted; the supervised-run MVP shipped via DCR-0008 and DCR-0010..DCR-0018;
the full inner loop (state schema, events.jsonl, reviewer adapter,
deterministic + model reviewers, harness step, runner package, runner
result, demo, subprocess runner) is in production. AGENTS.md has been
flagging these four as "remain proposed until approval/evidence-flow
coverage and requirement acceptance review."

This audit closes that loop.

## R-127 — Bounded run with iteration cap + allowed-paths enforcement

**Acceptance criteria** (from `requirements.yml`):

> 1. Run terminates on success, on max_iterations exhaustion, on policy
>    halt, or on explicit human halt.
> 2. Diffs produced by any iteration touch only paths declared in the
>    pack's Allowed Paths.

**Code evidence:**

- `agentspec/run.py::start_run` initializes state with `max_iterations`
  resolved from per-task-type defaults
  (`config.supervised_runs.max_iterations.{implementation, spike, spec, review}`).
- `agentspec/run.py::resume_run` increments `iteration` per call, calls
  `evaluate_policy(...)`, and writes terminal status via
  `_status_for_decision(review.decision)`.
- `agentspec/run.py::abort_run` provides the explicit human-halt path.
- `agentspec/policy.py::evaluate_policy` returns
  `PolicyVerdict(decision="halt", flags=["max_iterations_exceeded"])`
  when iteration > max_iterations and
  `flags=["forbidden_path"]` when any touched path falls outside
  allowed scope.

**Test evidence** (from `tests/test_supervised_run.py`):

- `test_resume_halts_when_max_iterations_is_exceeded` — iteration cap.
- `test_resume_halts_when_touched_path_is_outside_allowed_scope` —
  allowed-paths gate.
- `test_resume_completes_when_executor_reports_done_and_tests_pass` —
  success termination.
- `test_inspect_and_abort_report_state` — explicit human halt via abort.

**Verdict: meets.**

## R-128 — Per-iteration JSONL evidence + resumability

**Acceptance criteria:**

> 1. Each iteration appends one JSONL record with the documented schema.
> 2. Run state is sufficient to resume a paused run from disk.

**Code evidence:**

- `agentspec/run.py::STATE_SCHEMA = "agentspec.supervised_run.state.v0"`
  and `EVENT_SCHEMA = "agentspec.supervised_run.event.v0"` declare the
  schema versions.
- `_append_event(...)` writes one JSONL line per iteration to
  `agent/runs/<run-id>/events.jsonl` with `kind` ∈
  {`run_started`, `executor_output`, `reviewer_verdict`,
  `controller_response`, `autonomous_pause_to_finding`, `aborted`}.
- `load_run_state(root, run_id)` reads `state.yml` for resumption;
  `resume_run` refuses to operate on a terminal state.

**Test evidence:**

- `test_start_creates_state_and_events_with_configured_profiles` —
  state.yml + first event.
- `test_resume_auto_continues_for_active_context_pack_choice` — multi-
  iteration appends.
- `test_loop_resumes_existing_run_and_auto_continues` — resumption
  from disk.
- `test_cli_run_start_resume_inspect_abort` — end-to-end CLI surface.

**Verdict: meets.**

## R-129 — Reviewer produces structured feedback

**Acceptance criteria:**

> 1. Reviewer output validates against a documented schema.
> 2. An iteration receives the prior reviewer findings as input and
>    references them in its next action.

**Code evidence:**

- `agentspec/review.py::ReviewVerdict` is the structured schema:
  `decision`, `confidence`, `reason`, `message_to_executor`,
  `requires_human`, `flags`. `to_dict()` serializes to
  `agentspec.supervised_run.verdict.v0` shape.
- `agentspec/review.py::review_executor_output` produces the verdict
  from policy verdict + executor output + active context pack;
  deterministic by default, model-backed when `reviewer_mode=model`
  per `agentspec/model_review.py`.
- `agentspec/run.py::build_next_executor_prompt` packages the prior
  reviewer's `message_to_executor` into the next handoff prompt.

**Test evidence:**

- `test_model_reviewer_can_auto_continue_deterministic_pause` — model
  fallback decision shape.
- `test_invalid_model_response_falls_back_to_deterministic_pause`,
  `test_wrong_model_schema_falls_back_to_deterministic_pause`,
  `test_unavailable_model_response_falls_back_to_deterministic_pause`
  — schema validation + degradation.
- `test_model_complete_cannot_bypass_missing_or_failed_verification` —
  reviewer constraints honored.
- `test_prompt_after_auto_continue_includes_reviewer_instruction` —
  next iteration receives prior reviewer's instruction.
- `test_step_resumes_auto_continue_and_returns_next_prompt` — full
  consume-and-emit flow.

**Verdict: meets.**

## R-130 — Halts on risky changes; cannot continue past halt without approval

**Acceptance criteria:**

> 1. Policy verdict halt triggers a pause record in `agent/runs/<run-id>/`.
> 2. A run cannot continue past a halt without a recorded approval event.

**Code evidence:**

- `agentspec/run.py::TERMINAL_RUN_STATUSES = {"halted", "complete", "aborted"}`.
  `resume_run` raises `ValueError(f"Run {run_id} is already {status}.")`
  when invoked on a terminal state.
- `_append_event` records every reviewer verdict (including halts) as
  a JSONL `reviewer_verdict` event in `agent/runs/<run-id>/events.jsonl`.
- The autonomous-mode addition (T-028) further records an
  `autonomous_pause_to_finding` event when a `pause_for_human` is
  transformed into a halt.

**Test evidence:**

- `test_resume_halts_when_max_iterations_is_exceeded` — halt event +
  terminal state.
- `test_resume_halts_when_touched_path_is_outside_allowed_scope` —
  policy halt + record.
- `test_terminal_run_refuses_continuation_prompt` — terminal state
  blocks continuation.
- `test_policy_halt_cannot_be_overridden_by_model` — model reviewer
  cannot bypass a policy halt.

**Verdict: meets, with a stronger guarantee than literal text.**

**Interpretation note:** the literal acceptance text says "cannot
continue past a halt **without a recorded approval event**", which
implies the existence of an approval-and-continue mechanism. The
current implementation has no such mechanism: terminal states are
strictly terminal. A halted run cannot be continued under any
circumstances; the operator must `abort` it and start a new run.

This is a **strictly stronger** guarantee than R-130 requires (zero
approval events ⇒ zero continuations ⇒ strict subset of allowed
transitions), so R-130 is met. If a future use case wants
"approve-and-continue", that's a new requirement and a new DCR — not a
gap in R-130.

A follow-up open question is filed for that potential extension
(see disposition section).

## Findings Summary

| Req | Verdict | Notes |
|---|---|---|
| R-127 | meets | Multi-path termination + allowed-paths gate, both tested. |
| R-128 | meets | Schema + JSONL + resumability all present. |
| R-129 | meets | Structured verdict, schema validation, prior-reviewer handoff. |
| R-130 | meets | Stricter than literal text (no approval-continue mechanism); future extension is its own DCR. |

## Disposition

All four requirements meet acceptance. T-029 will execute:

```
aspec requirement accept R-127
aspec requirement accept R-128
aspec requirement accept R-129
aspec requirement accept R-130
```

Follow-up filed as Q-025: "Should AgentSpec ever support an
approve-and-continue mechanism past a halt? Today halts are strictly
terminal; an approval mechanism would make R-130's literal text
expressible. New DCR if we ever want this — explicit, audited,
governance-friendly path needed."

Beyond Q-025, no other gaps surfaced during this review.
