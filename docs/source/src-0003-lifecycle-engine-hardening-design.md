# AgentSpec Lifecycle Engine Hardening Design

## Status

Draft

## Owner

Yiming Wu

## Review Status

Revised after senior technical design review.

This document replaces the broader "AgentSpec Engine Lifecycle Design" draft with
a milestone-safe plan. The revision keeps AgentSpec as the lifecycle control
plane, but avoids creating a second state system beside the architecture already
present in this repository.

## Summary

AgentSpec should continue evolving into the repo-local lifecycle control plane
for spec-driven agent development.

The core product principle remains:

> No meaningful agent work should disappear outside durable project state.

The revised design narrows the implementation path:

- Preserve the current CLI name: `aspec`.
- Preserve the current config path: `.agentspec/config.yml`.
- Preserve task context packs as the durable work unit.
- Preserve supervised runs, sessions, review records, task ledger, handoff, and
  roadmap as existing lifecycle authorities.
- Add workflow support as an additive contract, not a replacement state machine.
- Add lifecycle projection and write-back checks before strict enforcement.
- Defer skill gates, blocking hooks, broad migration, and new evidence
  directories until the base lifecycle contract is stable.

The intended lifecycle remains:

```text
source/spec -> task context pack -> workflow reference -> run/session
  -> verification -> review -> completion -> handoff -> roadmap/status
```

## Current Architecture Anchors

The design must fit the repo as it exists today.

Current durable state includes:

- `.agentspec/config.yml`
- `agent/context-packs/*.md`
- `agent/runs/*/state.yml`
- `agent/runs/*/summary.yml`
- `agent/sessions/active/*`
- `agent/sessions/archived/*`
- `agent/reviews/REVIEW-####.yml`
- `agent/task-ledger.yml`
- `agent/handoff.yml`
- `agent/outcomes.yml`
- `agent/maturity.yml`
- `docs/ROADMAP.md`
- `docs/source/*`
- `docs/traceability/requirements.yml`

Current lifecycle behavior includes:

- `aspec status --json` summarizes requirements, DCRs, tasks, runs, sessions,
  outcomes, maturity, workflows, and handoff.
- `aspec task create --from-workflow <file>` can backfill a context pack from a
  workflow artifact.
- `aspec status` and `aspec task next` can surface orphan workflow warnings.
- `aspec review code` records review evidence under `agent/reviews/`.
- `aspec task complete` records task completion and can link review evidence.
- `aspec roadmap` writes `docs/ROADMAP.md` from canonical AgentSpec state.

This design must extend those surfaces rather than replace them.

## Problem Statement

AgentSpec already stores durable project state, but lifecycle integrity is not
yet fully enforced or uniformly projected across all commands.

The concrete failures to address are:

1. A workflow can exist without a referencing task context pack.
2. A task context pack can reference a workflow path that is missing or stale.
3. Status can show the project as idle while repairable lifecycle drift exists.
4. Verification may be recorded in run state or ledger but not exposed as a
   consistent completion gate.
5. Review evidence can exist but not be linked to the task completion record.
6. Handoff and roadmap can become stale after completion.
7. Finish/write-back behavior is spread across completion commands, plugin
   skills, roadmap generation, and handoff logic.

The current repo already detects one real orphan workflow:

```text
docs/plans/2026-04-28-agentspec-mvp-workflow.md
```

The near-term product goal is to make that kind of lifecycle drift visible,
repairable, and eventually blockable in governed mode.

## Goals

### Product Goals

1. Make AgentSpec the durable lifecycle control plane for spec-driven agent
   development.
2. Preserve existing developer-facing vocabulary: source, requirement, task
   context pack, run, review, handoff, roadmap.
3. Make workflow/task linkage explicit enough for humans and agents to repair.
4. Ensure `aspec status` and continuation commands never hide actionable drift.
5. Make completion include verification, review linkage, handoff, ledger, and
   roadmap write-back.
6. Keep lifecycle state readable through plain repo files.
7. Keep strict enforcement opt-in and compatible with legacy repos.

### Engineering Goals

1. Add a lifecycle projection layer over existing artifacts.
2. Harden workflow/task bidirectional link validation.
3. Introduce a shared write-back module that reuses existing formats.
4. Add an `aspec finish` orchestration command only after the write-back module
   exists.
5. Keep roadmap generation deterministic and migration-safe.
6. Add strict/gated behavior after warn-mode checks are stable.

## Non-Goals

AgentSpec should not become:

1. A coding agent.
2. A terminal multiplexer.
3. A multi-agent scheduler.
4. A CI system.
5. A project management SaaS.
6. A remote execution platform.
7. A plugin runtime where skills own lifecycle state.

For this milestone, AgentSpec should also not:

1. Rename `.agentspec/` to `.agent-spec/`.
2. Replace `agent/runs/` with workflow files.
3. Replace `agent/reviews/` with `agent/evidence/`.
4. Change `agent/task-ledger.yml` from its current keyed mapping without a
   separate migration.
5. Install blocking git hooks by default.
6. Require human approval for all strict-mode review until configurable review
   policy exists.

## Design Principles

### 1. Extend Existing State, Do Not Duplicate It

The lifecycle engine should normalize existing artifacts into a coherent
projection. It should not introduce a second authoritative state machine that can
disagree with runs, sessions, reviews, or the task ledger.

### 2. Task Context Pack Remains The Work Unit

The task context pack remains the durable unit agents execute from. Workflows are
plans or execution aids linked to context packs.

### 3. Workflows Are Additive

Native workflows under `agent/workflows/` may be added for new projects, but
existing workflow paths remain valid inputs:

```text
agent/workflows/*.md
docs/**/plans/**workflow.md
.hotl/state/**/*.json
```

Workflow support must therefore be scanner-first and migration-safe.

### 4. Review Evidence Stays In `agent/reviews/`

Task-level review evidence already has an established durable format:

```text
agent/reviews/REVIEW-####.yml
```

Any finish or lifecycle command should link this evidence rather than introduce a
parallel review authority.

### 5. Finish Means Write-Back

A task is not done just because code changed or tests passed. Completion should
also update the durable project projection:

- task ledger
- handoff
- roadmap
- final run or task summary
- review linkage

### 6. Enforcement Is Progressive

The lifecycle engine should start in warn/repair mode. Blocking behavior should
arrive only after:

- warnings are stable,
- repair commands are available,
- tests cover compatibility,
- strict mode is explicitly enabled.

## Terminology

| Term | Meaning |
|---|---|
| Source snapshot | Canonical design/source input under `docs/source/` |
| Requirement | Accepted implementation need under `docs/traceability/requirements.yml` |
| Task context pack | Durable work unit under `agent/context-packs/` |
| Workflow | Linked plan or execution artifact for a task context pack |
| Run | Supervised or autonomous execution state under `agent/runs/` |
| Session | Worktree or ownership lease under `agent/sessions/` |
| Review | Durable review evidence under `agent/reviews/` |
| Handoff | Machine-readable continuation state under `agent/handoff.yml` |
| Roadmap | Generated project status projection under `docs/ROADMAP.md` |
| Lifecycle drift | Mismatch between linked lifecycle artifacts or their projections |
| Strict mode | Opt-in mode where blocking lifecycle drift fails completion |

## High-Level Architecture

```text
+----------------------------------------------------------------+
|                            aspec CLI                            |
+----------------------------------------------------------------+
| status | continue | task | run | review | roadmap | drift | finish |
+----------------------------------------------------------------+
|                    Lifecycle Projection Layer                   |
+----------------------------------------------------------------+
| normalize tasks | workflows | runs | sessions | reviews | handoff |
| compute next action | classify drift | summarize gates            |
+----------------------------------------------------------------+
|                         Existing Core State                     |
+----------------------------------------------------------------+
| context packs | runs | sessions | reviews | ledger | handoff       |
| outcomes | maturity | roadmap | requirements | DCRs                |
+----------------------------------------------------------------+
|                           Validators                            |
+----------------------------------------------------------------+
| links | paths | branch policy | verification | review | write-back  |
+----------------------------------------------------------------+
|                           Write-Back                            |
+----------------------------------------------------------------+
| task ledger | handoff | roadmap | final summaries | review linkage  |
+----------------------------------------------------------------+
```

The lifecycle projection layer is read-mostly. It computes the current lifecycle
view from existing artifacts. Write operations remain concentrated in command
handlers and a shared write-back module.

## Repository Layout

The compatible layout is:

```text
repo/
├── AGENTS.md
├── .agentspec/
│   ├── config.yml
│   ├── cache/
│   └── locks/
├── agent/
│   ├── context-packs/
│   │   ├── _TEMPLATE.md
│   │   └── T-001-example.md
│   ├── workflows/              # additive native workflows for new projects
│   │   ├── implement-feature.md
│   │   └── W-001-example.md
│   ├── runs/
│   ├── sessions/
│   ├── reviews/
│   │   └── REVIEW-0001.yml
│   ├── task-ledger.yml
│   ├── handoff.yml
│   ├── outcomes.yml
│   └── maturity.yml
├── docs/
│   ├── ROADMAP.md
│   ├── source/
│   ├── traceability/
│   ├── change-requests/
│   ├── adr/
│   └── plans/                  # legacy/external workflow compatibility
└── reports/
```

This design intentionally does not introduce `.agent-spec/`.

## Lifecycle Projection

AgentSpec should expose a normalized lifecycle status without making every
artifact use the same physical schema.

### Normalized States

```text
ready
planned
in_progress
verify_pending
review_pending
complete
blocked
archived
```

### State Sources

| Normalized state | Primary source |
|---|---|
| `ready` | task context pack with no active or terminal run overlay |
| `planned` | task context pack has a valid linked workflow but no active run |
| `in_progress` | active run or active session exists |
| `verify_pending` | run touched implementation paths and verification is missing or failed |
| `review_pending` | verification passed but review evidence is missing or not linked |
| `complete` | task ledger/run state records completion with required write-back |
| `blocked` | halted run, blocked session, or blocking lifecycle drift |
| `archived` | archived session or historical completed task retained for traceability |

The projection should explain which artifact produced each state. That makes
status reviewable and debuggable.

## Core Artifacts

### 1. Task Context Pack

Path:

```text
agent/context-packs/T-001-example.md
```

Purpose:

The task context pack remains the bounded work unit. It defines objective,
requirements, allowed paths, verification expectations, and optional workflow
linkage.

Compatible metadata should remain Markdown-readable:

```markdown
# T-001: Add invoice retry policy

Type: `implementation`
Stream: `billing`
Milestone: `M2.1`
Slice: `4`
Branch: `feat/billing-M2.1-slice-4-invoice-retry`
Workflow: `agent/workflows/W-001-invoice-retry.md`

## Requirements

- `R-193` AgentSpec enforces workflow-pack coverage and generated roadmap status.

## Allowed Paths

- `services/billing/**`
- `tests/billing/**`
- `agent/reviews/*.yml`
- `agent/task-ledger.yml`
- `agent/handoff.yml`

## Verification

- `npm test -- billing`
- `npm run typecheck`
```

Front matter can be supported later, but this revision does not require a
front-matter migration.

### 2. Workflow Artifact

Workflow files are execution plans. They do not replace run state.

Native workflow path for new projects:

```text
agent/workflows/W-001-invoice-retry.md
```

Legacy/external workflow paths remain scanned:

```text
docs/**/plans/**workflow.md
.hotl/state/**/*.json
```

Native workflow example:

```markdown
---
workflow_id: W-001
task_pack: agent/context-packs/T-001-add-invoice-retry-policy.md
status: planned
---

# Workflow W-001: Add invoice retry policy

## Linked Task

`agent/context-packs/T-001-add-invoice-retry-policy.md`

## Plan

1. Inspect current billing submission flow.
2. Add retry configuration.
3. Implement retry wrapper for transient failures.
4. Add tests.
5. Run verification commands.
6. Record review and write-back.
```

Required validation:

- workflow has a task reference when it is native;
- task reference exists;
- referenced task links back when the task is planned or active;
- external workflows without a referencing task are reported as orphan drift.

### 3. Run State

Path:

```text
agent/runs/<run-id>/state.yml
```

Purpose:

Run state remains the execution authority for supervised or autonomous work. It
records status, iteration, touched paths, verification state, reviewer verdict,
and recovery command context.

Lifecycle commands should read run state instead of duplicating execution state
inside workflow files.

### 4. Review Evidence

Path:

```text
agent/reviews/REVIEW-####.yml
```

Purpose:

Review evidence remains task-level and durable. Completion and finish commands
should link review IDs into the task ledger and handoff.

Review evidence should support:

- verdict;
- reviewer;
- task/context pack selector;
- reviewed range;
- summary;
- findings or explicit no-blocking-findings note.

### 5. Task Ledger

Path:

```text
agent/task-ledger.yml
```

Purpose:

The ledger remains durable task completion state. The current keyed mapping by
context pack path should be preserved until a separate schema migration exists.

Compatible shape:

```yaml
schema: agentspec.task_ledger.v0
tasks:
  agent/context-packs/T-001-add-invoice-retry-policy.md:
    status: complete
    run_id: complete-t-001-add-invoice-retry-policy
    reason: Completed with verification and review.
    verification:
      status: passed
    code_review:
      id: REVIEW-0001
      verdict: ready
      path: agent/reviews/REVIEW-0001.yml
    updated_at: 2026-05-11T12:00:00Z
```

### 6. Handoff

Path:

```text
agent/handoff.yml
```

Purpose:

Handoff remains the machine-readable current project state for future sessions.
It should be updated by completion/finish operations and include:

- last completed task;
- verification status;
- linked review evidence;
- current status summary;
- recommended next action;
- paths to important artifacts.

### 7. Roadmap

Path:

```text
docs/ROADMAP.md
```

Purpose:

Roadmap remains the human-readable project status projection.

Phase 1 should keep the current deterministic full-file generation behavior
unless existing roadmap preservation requirements are accepted.

Phase 2 may add generated-block mode:

```markdown
<!-- aspec:roadmap:start -->
generated content
<!-- aspec:roadmap:end -->
```

Generated-block mode must be config-gated and tested for manual content
preservation before it becomes default.

## CLI Design

### Existing Commands To Preserve

The lifecycle design must preserve and build on:

```bash
aspec init
aspec status
aspec status --json
aspec continue
aspec next-action
aspec task create
aspec task create --from-workflow <file>
aspec task next
aspec task complete <selector>
aspec run loop
aspec run step
aspec run inspect <run-id>
aspec review code --task <task> --verdict ready --summary "..."
aspec roadmap
aspec roadmap --check
aspec drift
```

### `aspec status`

Status should become the primary lifecycle projection surface.

It should report:

- task queue;
- active and attention runs;
- sessions;
- workflow drift;
- verification state;
- review linkage;
- handoff recency;
- roadmap recency;
- next recommended action.

Important rule:

```text
aspec status must not describe the project as cleanly idle while blocking or
repairable lifecycle drift exists.
```

### `aspec continue` / `aspec next-action`

Continuation should prioritize:

1. attention runs;
2. active runs;
3. blocking lifecycle drift repair;
4. ready task context packs;
5. orphan workflow backfill;
6. idle status.

The exact ordering between ready tasks and orphan workflow backfill should be
configurable later. For the near term, orphan drift should be visible before an
idle result.

### `aspec workflow create`

Add only after link validation is stable.

Proposed behavior:

```bash
aspec workflow create <task-selector>
```

It should:

- fail if the task context pack does not exist;
- create `agent/workflows/W-###-<slug>.md`;
- add a workflow reference to the context pack;
- add a task reference to the workflow;
- copy allowed paths and verification hints where available;
- avoid changing run state.

### `aspec finish`

Add after a shared write-back module exists.

Proposed behavior:

```bash
aspec finish <task-selector>
aspec finish --current
aspec finish --dry-run
```

`aspec finish` should orchestrate existing completion/write-back APIs. It should
not invent a new task ledger or review format.

Checks:

1. Task context pack exists.
2. Linked workflow is valid when present or required by policy.
3. Active run/session state is terminal or intentionally released.
4. Verification passed or an explicit allowed waiver exists.
5. Review evidence exists and is linked, or review is explicitly waived by
   policy.
6. Changed files satisfy allowed path policy when a changed-file list is
   available.
7. Handoff can be regenerated.
8. Task ledger can be updated.
9. Roadmap is current after write-back.

In warn mode, failures produce findings and repair commands.

In strict mode, blocking findings fail finish.

### `aspec verify-work`

Defer as a separate command unless a clear gap remains after `run` and `finish`
are hardened.

For the near term, verification status should continue to come from:

- run state;
- task ledger;
- explicit test status provided to completion commands;
- verification commands documented in task context packs.

## Shared Write-Back Module

Introduce a small internal module:

```text
agentspec.writeback
```

Initial functions:

```python
build_completion_projection(root, task_selector)
update_task_ledger(root, completion)
update_handoff(root, completion, project_status)
update_roadmap(root)
verify_writeback(root, completion)
```

The module should call or wrap existing task, handoff, and roadmap functions
instead of duplicating their serialization logic.

Atomicity requirement:

- Do not mark a task complete if required ledger or handoff writes fail.
- Preserve the existing ledger-first completion safety behavior.

## Drift Detection

Lifecycle drift should be classified separately from source/spec drift, even if
it is surfaced through `aspec drift`.

Initial lifecycle drift checks:

| Check | Description | Initial severity |
|---|---|---|
| orphan workflow | Workflow exists without referencing task context pack | warning/blocking in strict |
| broken workflow link | Task and workflow do not reference each other | warning/blocking in strict |
| missing review linkage | Task complete but review ID missing when required | warning/blocking in strict |
| missing verification | Task complete but verification is missing or failed | warning/blocking in strict |
| stale handoff | Handoff does not reflect last completion | warning |
| stale roadmap | Roadmap check fails | warning/blocking in strict |
| path violation | Touched paths exceed allowed paths when known | blocking in strict |

`aspec drift --fix` should not be added until individual repair operations are
well tested. Prefer explicit repair commands first.

## Strict Mode

Strict mode should reuse the existing maturity/enforcement idea rather than
introduce a separate marker-first policy.

Possible config:

```yaml
lifecycle:
  enforcement: warn # warn | strict
  require_workflow_for_run: false
  require_review_for_completion: true
  require_roadmap_current: true
```

Do not add blocking git hooks by default.

Optional hooks can be generated later, but they should be opt-in and documented
as local enforcement aids, not the core enforcement model.

## Migration Strategy

Migration should be incremental and reversible through git.

### Existing AgentSpec Repos

Do:

- preserve `.agentspec/config.yml`;
- preserve `agent/context-packs/`;
- preserve `agent/reviews/`;
- preserve current task ledger schema;
- add missing workflow references only when safe;
- report ambiguous cases instead of guessing.

### HOTL-Style Workflows

Do:

- scan `docs/**/plans/**workflow.md`;
- scan `.hotl/state/**/*.json`;
- recommend `aspec task create --from-workflow <file>`;
- preserve original workflow paths;
- optionally copy to `agent/workflows/` only with an explicit migration command.

### Deferred Migration

Defer:

- moving all workflows into `agent/workflows/`;
- changing task ledger shape;
- moving review evidence into `agent/evidence/`;
- generated-block roadmap default;
- repo-wide strict mode default.

## Phased Implementation Plan

### Phase 1: Lifecycle Projection Hardening

Deliverables:

- normalized lifecycle projection helper;
- status includes lifecycle gate summaries;
- continuation recommends drift repair before clean idle;
- tests for orphan workflow, broken link, missing review linkage, stale roadmap.

Acceptance criteria:

- `aspec status --json` exposes workflow and write-back drift consistently.
- `aspec continue` does not report no action when orphan workflow drift exists.
- Existing status, task, run, review, roadmap, and maturity tests keep passing.

### Phase 2: Write-Back Module

Deliverables:

- `agentspec.writeback`;
- reusable completion projection;
- ledger/handoff/roadmap update helpers;
- write-back verification helper.

Acceptance criteria:

- Existing completion behavior is preserved.
- Write-back verification can explain missing ledger, handoff, review, or
  roadmap updates.
- Failure ordering does not mark work complete before required writes succeed.

### Phase 3: Finish Orchestrator

Deliverables:

- `aspec finish <task-selector>`;
- `aspec finish --dry-run`;
- warning mode output;
- strict mode failure behavior behind config.

Acceptance criteria:

- Finish reuses existing review and ledger formats.
- Finish can complete a task with verification and linked review evidence.
- Finish reports repair commands when write-back is missing.

### Phase 4: Native Workflow Creation

Deliverables:

- `aspec workflow create <task-selector>`;
- native `agent/workflows/W-###-<slug>.md` creation;
- bidirectional link update;
- validation tests.

Acceptance criteria:

- Native workflows are additive.
- Existing external workflow scanning still works.
- Broken links are detected and reported.

### Phase 5: Roadmap Preservation Mode

Deliverables:

- optional generated-block roadmap mode;
- config flag;
- preservation tests.

Acceptance criteria:

- Manual content outside generated blocks is preserved.
- Full-file roadmap generation remains available.
- `aspec roadmap --check` works in both modes.

### Phase 6: Strict Lifecycle Enforcement

Deliverables:

- lifecycle enforcement config;
- strict finish failures for blocking drift;
- strict roadmap/review/verification checks.

Acceptance criteria:

- Legacy repos default to warn mode.
- Strict mode is opt-in.
- Blocking findings include repair guidance.

### Phase 7: Migration Tools

Deliverables:

- explicit migration command for external workflows if still needed;
- idempotency tests;
- rollback guidance.

Acceptance criteria:

- Existing HOTL-style workflows can be backfilled safely.
- Migration does not overwrite user content unexpectedly.

### Phase 8: Skill Gates

Deferred until Phases 1-6 are stable.

Skill gates should remain adapters or guidance modules. They should produce
evidence or findings, but should not own lifecycle state.

## MVP Acceptance Criteria

The narrowed MVP is complete when:

1. `aspec status --json` exposes lifecycle drift and write-back readiness.
2. `aspec continue` or `aspec next-action` does not hide orphan workflow drift.
3. Workflow/task broken links are detected.
4. Missing review linkage for completed work can be detected.
5. Missing or stale roadmap state can be detected.
6. Shared write-back helpers update ledger, handoff, and roadmap using existing
   schemas.
7. `aspec finish --dry-run` can explain whether a task is finishable.
8. Existing tests for task creation, run completion, review evidence, status,
   roadmap, outcomes, maturity, and workflow warnings continue to pass.

The MVP does not require:

- skill gates;
- blocking pre-push hooks;
- complete HOTL migration;
- new `agent/evidence/` layout;
- generated-block roadmap default;
- human-only review enforcement;
- branch policy enforcement by default.

## Unresolved Design Decisions

1. Should `aspec finish` eventually replace `aspec task complete`, or remain a
   higher-level orchestration command?
2. Should native workflow IDs use `W-###`, task slug names, or task IDs in file
   names?
3. Should `aspec workflow create` be allowed for completed tasks for historical
   reconstruction?
4. Should roadmap preservation mode become default after it is proven stable?
5. Should lifecycle enforcement be configured through maturity profiles,
   `lifecycle.enforcement`, or both?
6. What review policies should be supported in strict mode: human only, agent
   self-review, designated reviewer profile, or project-specific policy?
7. Should path-policy checks use run touched paths, git diff, or both?
8. Should external workflow backfill attach requirements only when explicitly
   provided?

## Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Duplicate state machines | Make lifecycle projection read existing artifacts instead of owning new execution state |
| Breaking existing repos | Keep current paths and schemas; default to warn mode |
| Review evidence fragmentation | Keep `agent/reviews/` as the review authority |
| Roadmap conflicts | Keep full-file generation initially; add generated-block mode behind config |
| Finish command bypasses existing safety | Implement finish as an orchestrator over existing completion and write-back APIs |
| Strict mode slows development | Make strict mode opt-in with clear repair commands |
| Migration guesses wrong | Prefer explicit repair/backfill commands over automatic fixes |
| Skill gates become too broad | Defer skill gates until lifecycle write-back is stable |

## Recommended Decisions

1. Keep project name `agent-spec-engine`.
2. Keep CLI `aspec`.
3. Keep config path `.agentspec/config.yml`.
4. Keep task context packs under `agent/context-packs/`.
5. Keep review evidence under `agent/reviews/`.
6. Keep `agent/runs/` as execution state.
7. Add native `agent/workflows/` only as an additive workflow location.
8. Build lifecycle projection before adding blocking enforcement.
9. Add `agentspec.writeback` before `aspec finish`.
10. Defer skill gates and hooks until finish/write-back behavior is stable.

## Final Recommendation

Proceed with lifecycle hardening, not with the original broad lifecycle rewrite.

The next approved design slice should be:

```text
lifecycle projection + workflow/task link drift + write-back verification
```

Only after that slice passes tests should AgentSpec add `aspec finish`, native
workflow creation, strict mode, and migration tooling.

Implementation should not begin from this draft until a task context pack is
created or selected and the user explicitly says:

```text
Proceed with implementation.
```
