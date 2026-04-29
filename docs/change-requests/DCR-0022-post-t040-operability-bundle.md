# DCR-0022: Post-T-040 operability bundle

| Field | Value |
|---|---|
| Status | classified |
| Classification | defer |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-28 |
| Confidence | medium |

## Summary

Capture four operability findings from the T-040 (`aspec status`) code
review that are real but not urgent, so they leave reviewer-comment
land and become a tracked, prioritized backlog. None of these items is
being implemented now; this DCR's purpose is to make the deferred work
discoverable and to record the rationale for *why* it was deferred.

The fifth finding from the same review (P1: structured JSON error
envelope) was already shipped via T-042 before this DCR was filed. The
P2 finding on model-review diagnostics is captured separately as
related to Q-026 (model-backed `quality_reviewer` gap).

## Motivation

T-040 introduced a JSON status surface harnesses can consume. The code
review surfaced four secondary operability gaps that don't gate
harness adoption today but will compound as more harnesses, dashboards,
or dogfood loops use AgentSpec. Filing them as one defer DCR avoids
proliferating four micro-DCRs, keeps the rationale together, and lets
a future implementer pick them up as a coherent slice.

## Proposed Change

Each item below is independently shippable. The expectation is that
each becomes its own implementation pack (or, where design uncertainty
warrants, its own spike DCR) when the project advances it.

### Item 1 — Run records carry recovery context (P2)

Origin: T-040 review finding #2 (`agentspec/status.py:121-140`).

The per-run record in `_load_runs` exposes `last_decision` (e.g.,
`"halt"`) but not the surrounding *why*. For paused or halted runs, a
harness or operator should be able to read enough from the status
payload to triage without round-tripping through `aspec run inspect`.

Proposed additions to each run record:

- `last_review_reason` — the reviewer's reason string for
  `last_decision`
- `policy_flags` — list of policy-gate flags (e.g.,
  `forbidden_path`, `cap_exceeded`, `model_review_unavailable`)
- `test_status` — last verification status (`not_run`, `passed`,
  `failed`)
- `last_event_ref` — pointer into `events.jsonl` for the latest
  decision event
- `recovery_command` — a copy-pastable command appropriate for the
  run's terminal state (e.g., `aspec run resume <id>` for paused,
  `aspec run inspect <id>` for halted)

The top-level `status.recommendation` already names a recovery
command for the *first* attention run. Per-run records add the same
clarity for the rest of the queue.

### Item 2 — Completion atomicity for run state + ledger (P2)

Origin: T-040 review finding #3 (`agentspec/run.py:373-386`).

Resume code on `complete` writes three artifacts in sequence: the run
state file, the optional summary projection, and the committed task
ledger. If the third write raises, the local run is already
`complete` on disk while the ledger still shows the pack as not-done.
A retry with the same `run_id` is then blocked by duplicate-state
detection.

Failure mode is rare (essentially "disk full" or "permission flipped
between writes") but the recovery path is awkward when it does happen
— the operator has to delete state files manually.

Proposed fix:

- Reorder to write the ledger first, then state. Ledger writes are
  idempotent inserts; if they fail, the state file is never written
  and a retry converges naturally.
- Or, wrap the sequence in a try/except with a compensating delete on
  the state file when the ledger write fails. Less elegant but
  preserves the current observation order.

The first option is preferred. No new schema needed.

### Item 3 — Metrics surface for feedback loops (spike candidate)

Origin: T-040 review finding #5 (`agentspec/status.py:31-66`).

The status payload exposes counts (`by_status`, `by_priority`, etc.)
but no derived metrics: cycle time per pack, pause/halt rate,
verification pass rate, reviewer-fallback rate, policy-flag
aggregations, retry counts, DCR churn. A future dashboard, MCP
consumer, or autonomous-mode self-tuner would want these.

This item is the most uncertain and may warrant its own **spike DCR**
when advanced. Open questions to resolve before implementing:

- Which metrics matter and at what aggregation window?
- Where does the metrics computation live — `status.py`, a new
  `metrics.py`, or a sidecar log?
- Is the metrics output a separate command (`aspec metrics`) or a
  field on `aspec status --json`?
- What's the schema name (`agentspec.metrics.v0`?) and stability
  contract?

Until those are resolved, no implementation work. `events.jsonl` and
the per-run state files already contain the raw data; this item is
purely about rolling them up.

### Item 4 — Recovery-oriented CLI aliases (P3, ergonomics)

Origin: T-040 review finding #6 (`agentspec/cli.py:116-214`).

The `run` group has 11 subcommands (`start`, `resume`, `loop`,
`step`, `package`, `result`, `demo`, `exec`, `inspect`, `prompt`,
`abort`). A user-facing top-level `aspec continue` or
`aspec next-action` would be a thin shim that reads
`build_project_status`'s `recommendation` field and dispatches to the
underlying command.

Pure ergonomics over existing surface. No new behavior, no new
schema. Smallest possible follow-up.

## Impact Assessment

- Supports `R-007` by improving CLI ergonomics and harness reliability.
- Supports `R-128` by making run-state breadcrumbs more visible.
- Supports `R-135` by making autonomous/research run halts easier to
  triage without round-tripping.
- Code surface (per item, when implemented):
  - Item 1: `agentspec/status.py`, `agentspec/run.py`
  - Item 2: `agentspec/run.py`, `agentspec/task.py`
  - Item 3: TBD (likely `agentspec/status.py` or new
    `agentspec/metrics.py`)
  - Item 4: `agentspec/cli.py`, `agentspec/status.py`
- Test surface: `tests/test_status_cli.py`,
  `tests/test_supervised_run*.py`, plus one new test file per item
  when shipped.

## Disposition

Classification: `defer`.

Rationale:

- Items 1, 2, 4 are clear in shape but not urgent. They're polish on
  top of the working T-040 / T-042 surface. Each can be its own
  small implementation pack when prioritized.
- Item 3 (metrics surface) is genuinely under-designed and may need
  its own spike DCR before implementation — flagged here so the
  decision isn't lost.
- The four items share enough thematic coherence ("operability
  tightening on the just-shipped status surface") that a single
  bundle DCR captures the rationale better than four micro-DCRs.

Per ADR-0002, a `defer` classification means downstream context-pack
creation is not yet eligible for these items. Promotion to
`implement-now` (or `spike` for item 3) is a separate DCR transition
when prioritized.

## Acceptance Criteria

This DCR is a backlog capture — it has no acceptance criteria of its
own. Each item, when promoted to `implement-now` or `spike`, will
produce its own DCR or implementation pack with concrete acceptance
criteria.

The criteria for *this* DCR are:

- Each of the four items has a clear-enough scope that a future
  implementer (human or agent) can pick it up without re-reading the
  T-040 review.
- Item 3 explicitly flags the open design questions that would need
  spike work before implementation.
- The DCR is discoverable via `aspec dcr list` so it appears in
  status surveys alongside other deferred work.
