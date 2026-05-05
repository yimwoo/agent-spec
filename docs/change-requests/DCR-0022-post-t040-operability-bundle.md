# DCR-0022: Post-T-040 operability bundle

| Field | Value |
|---|---|
| Status | accepted |
| Classification | defer |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-05 |
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

**Resolution 2026-05-01 — promoted to DCR-0028.** Item 1 was lifted out of
this defer bundle on 2026-05-01 and now lives in
`DCR-0028-run-status-recovery-context.md` with classification
`implement-now`. Items 3 and 4 remain in this DCR as `defer`.

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

**Update 2026-04-29 — research-mode write extends scope.**

Empty-queue autonomous research run `research-20260429T164324Z` (see
`reports/dogfood/2026-04-29-empty-queue-autonomous-research.md`) surfaced
a second defect in the same code block. The ledger write at
`agentspec/run.py:375-386` fires whenever `review.decision == "complete"`
with no mode guard, so research-mode runs — where
`state["context_pack"] == RESEARCH_CONTEXT_PACK_SENTINEL` — write a
`<research-mode>` entry into `agent/task-ledger.yml`. The bogus entry
was removed from the live workspace by hand after discovery; no
production code changed.

This is a different failure mode from the atomicity gap above
(wrong-mode write vs. partial-write recovery) but shares the same call
site, so a single fix can address both when item 2 is promoted:

- Skip the `record_task_ledger_status` call when the run is research
  mode (e.g., `state.get("mode") == "research"` or the sentinel
  context pack), so research completion never touches the
  implementation ledger.
- Apply the write-ledger-first reordering (or compensating delete) for
  non-research runs as originally proposed.

Per ADR-0005 / R-142, research mode's allowed write surface is
`reports/dogfood/**`, `docs/discovery/open-questions.yml`, and
`docs/change-requests/**` — `agent/task-ledger.yml` is out of scope by
design, which makes this a contract violation, not just polish.

**Resolution 2026-04-29 — promoted to DCR-0024.** Item 2 was lifted
out of this defer bundle on 2026-04-29 and now lives in
`DCR-0024-atomic-completion-research-mode-ledger-guard.md` with
classification `implement-now`. Items 1, 3, and 4 remain in this DCR
as `defer`.

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

**Resolution 2026-05-05 — promoted to DCR-0052.** Item 3 was lifted out of
this defer bundle on 2026-05-05 and now lives in
`DCR-0052-project-metrics-surface-for-feedback-loops.md` with classification
`implement-now`.

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

**Resolution 2026-05-01 — promoted to DCR-0034.** Item 4 was lifted out of
this defer bundle on 2026-05-01 and now lives in
`DCR-0034-promote-dcr-0022-recovery-cli-aliases.md` with classification
`implement-now`. Item 3 remains in this DCR as `defer`.

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

- Item 4 has been promoted to DCR-0034.
- Item 3 has been promoted to DCR-0052.
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
