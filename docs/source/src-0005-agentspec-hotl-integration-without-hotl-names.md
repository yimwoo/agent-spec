# AgentSpec Engine: Integrating HOTL Capabilities Without HOTL Naming

## Status

Draft

## Owner

Yiming Wu

## Summary

This document describes how to integrate useful HOTL plugin capabilities into
`agent-spec-engine` while keeping AgentSpec as the single public product, code
repository, CLI, artifact model, and terminology system.

This revision is constrained by the current AgentSpec lifecycle architecture:

- preserve `.agentspec/config.yml`;
- preserve task context packs as the durable work unit;
- preserve `agent/runs/`, `agent/sessions/active|archived/`,
  `agent/reviews/`, `agent/task-ledger.yml`, `agent/handoff.yml`, and
  `docs/ROADMAP.md` as existing lifecycle authorities;
- treat workflow support as an additive contract linked to task context packs;
- avoid adding a second session, review, or evidence state system.

The integration goal is not to embed a `.hotl/` folder or expose HOTL names.
Instead, AgentSpec should absorb useful lifecycle behavior and express it
through AgentSpec-native concepts:

```text
HOTL concept       -> AgentSpec concept
brainstorm         -> discovery
workflow           -> workflow / execution plan wording
execute            -> implementation loop
review             -> review gate
finish             -> completion / write-back
HOTL state         -> AgentSpec run/session projection
HOTL hooks         -> AgentSpec lifecycle checks
HOTL skills        -> AgentSpec lifecycle skills
```

The user-facing CLI remains:

```bash
aspec
```

The code repo remains:

```text
agent-spec-engine
```

New projects should contain no `.hotl/` directory, no HOTL-specific file names,
and no HOTL-specific generated docs. All generated state and docs should align
with AgentSpec vocabulary and the current AgentSpec artifact layout.

---

## Goals

1. Keep `agent-spec-engine` as the main repository and public project.
2. Keep `aspec` as the primary CLI.
3. Absorb HOTL's execution lifecycle into AgentSpec-native modules.
4. Remove `.hotl/` from new project layout.
5. Avoid HOTL names in generated files, commands, templates, and docs.
6. Preserve the valuable HOTL behavior:
   - staged development loop
   - workflow planning
   - execution state
   - review stage
   - branch finishing protocol
   - hooks
   - step-by-step evidence
7. Make AgentSpec the source of truth for durable state and execution state by
   extending existing artifacts rather than replacing them.
8. Provide migration from existing HOTL projects into AgentSpec-native workflow
   and task context pack artifacts.

---

## Non-Goals

1. Do not expose `hotl` commands in the final CLI.
2. Do not generate `.hotl/` in new projects.
3. Do not require users to install HOTL separately for new AgentSpec projects.
4. Do not preserve HOTL vocabulary in user-facing docs except migration notes.
5. Do not maintain two independent state systems.
6. Do not allow HOTL-style workflows to become a parallel source of truth after
   migration.
7. Do not rename `.agentspec/` to `.agent-spec/` as part of this design.
8. Do not replace `agent/reviews/` with a new `agent/evidence/` review
   authority.
9. Do not replace `agent/runs/` or `agent/sessions/active|archived/` with a new
   execution state store.

---

## Product Positioning

AgentSpec becomes:

> A repo-local lifecycle engine for spec-driven agent development.

Expanded message:

> AgentSpec turns specs into linked tasks, execution plans, implementation loops, verification evidence, review gates, handoff, and roadmap write-back for humans and coding agents.

The important positioning shift:

```text
Before:
AgentSpec owns durable state.
HOTL owns execution.

After:
AgentSpec owns durable state and execution lifecycle.
```

---

## Concept Mapping

| HOTL Concept | AgentSpec Replacement | Notes |
|---|---|---|
| HOTL plugin | AgentSpec lifecycle engine | No separate runtime required |
| `.hotl/` | `.agentspec/` + `agent/` artifacts | Keep existing `.agentspec/config.yml`; committed lifecycle state stays under `agent/` |
| HOTL workflow file | AgentSpec workflow, optionally described as an execution plan | `agent/workflows/W-001.md` or accepted legacy workflow path |
| `writing-plans` skill | workflow planning | Existing workflow contract first; `aspec plan` can be a future alias |
| `loop-execution` | supervised run / implementation loop | Existing `aspec run ...` surfaces remain authoritative |
| `subagent-execution` | delegated implementation loop | Optional future adapter |
| `review` | `aspec review code` | Review evidence gate using `agent/reviews/REVIEW-####.yml` |
| `finishing-a-development-branch` | `aspec finish` | Future completion/write-back orchestrator |
| session-start hook | AgentSpec session-start check | Existing `aspec session start` lease behavior first |
| HOTL state JSON | AgentSpec run/session projection | `agent/runs/*` and `agent/sessions/active|archived/*` |
| HOTL runtime | AgentSpec lifecycle projection/runtime helpers | Derived from existing artifacts first |
| HOTL final summary script | AgentSpec write-back engine | `agentspec.writeback` |

---

## Terminology Decision

AgentSpec should use the following terms consistently.

| Term | Definition |
|---|---|
| Spec | Requirement or intent to be developed |
| Task Pack | Durable unit of work derived from a spec |
| Workflow | Linked plan or execution artifact for a task context pack |
| Execution Plan | User-facing wording for a workflow when avoiding HOTL-adjacent naming |
| Session | A bounded human/agent work session |
| Implementation Loop | Iterative code-edit/test/reason cycle |
| Verification | Proof that the work meets acceptance criteria |
| Review | Critique and approval before completion |
| Completion | Final lifecycle stage that performs write-back |
| Write-Back | Updates to handoff, ledger, roadmap, verification status, and review linkage |
| Drift | Any mismatch between repo state and AgentSpec lifecycle state |

Recommended naming choice:

- Keep **Workflow** as the durable artifact contract because current AgentSpec
  already implements workflow scanning, workflow/task linkage, and workflow
  backfill.
- Use **Execution Plan** as product wording in docs or UI where "workflow" feels
  too HOTL-adjacent, but make it an alias over the workflow contract rather than
  a new artifact family.

This document uses **workflow/execution plan** where the distinction matters.

---

## Target Repository Layout for User Projects

New AgentSpec-enabled projects should build on the current layout:

```text
repo/
├── AGENTS.md
├── agent/
│   ├── handoff.yml
│   ├── task-ledger.yml
│   ├── context-packs/
│   │   ├── _TEMPLATE.md
│   │   └── T-001.md
│   ├── workflows/
│   │   ├── implement-feature.md
│   │   └── W-001.md
│   ├── runs/
│   │   └── <run-id>/
│   ├── sessions/
│   │   ├── active/
│   │   └── archived/
│   ├── reviews/
│   │   └── REVIEW-0001.yml
│   ├── outcomes.yml
│   └── maturity.yml
├── docs/
│   ├── source/
│   ├── traceability/
│   ├── ROADMAP.md
│   └── discovery/
├── .agentspec/
│   ├── config.yml
│   ├── cache/
│   └── locks/
└── reports/
```

Important properties:

- No `.hotl/`.
- No HOTL-specific generated file names.
- Workflows are first-class AgentSpec artifacts; "execution plan" may be used as
  user-facing wording.
- Run and session state are owned by AgentSpec through existing `agent/runs/`
  and `agent/sessions/active|archived/` artifacts.
- Review evidence stays under `agent/reviews/`.
- `.agentspec/` remains the config/cache/lock namespace.

---

## AgentSpec Engine Internal Architecture

Inside the `agent-spec-engine` repository, integration should be incremental and
aligned with the current flat `agentspec/` package:

```text
agent-spec-engine/
├── agentspec/
│   ├── cli.py
│   ├── config.py
│   ├── drift.py
│   ├── handoff.py
│   ├── init.py
│   ├── review.py
│   ├── roadmap.py
│   ├── run.py
│   ├── session.py
│   ├── status.py
│   ├── task.py
│   ├── workflow.py
│   └── writeback.py
├── agent/
│   ├── context-packs/
│   ├── reviews/
│   ├── runs/
│   ├── sessions/
│   ├── handoff.yml
│   └── task-ledger.yml
└── docs/
    ├── source/
    ├── traceability/
    └── ROADMAP.md
```

Near-term additions should prefer extending these modules:

| Capability | Current owner |
|---|---|
| workflow/task link validation | `agentspec/workflow.py` |
| next-action/status projection | `agentspec/status.py` |
| completion ledger state | `agentspec/task.py` |
| review evidence | `agentspec/review.py` + `agent/reviews/` |
| run state | `agentspec/run.py` + `agent/runs/` |
| session leases | `agentspec/session.py` + `agent/sessions/active|archived/` |
| handoff/roadmap write-back | `agentspec/handoff.py`, `agentspec/roadmap.py`, `agentspec/writeback.py` |

New packages such as `agentspec/lifecycle/` or `agentspec/gates/` should only be
introduced when the flat modules become meaningfully hard to maintain. They
should not create new authoritative state stores.

No public or generated artifact needs to be named `hotl`. For migration-only
code, prefer:

```text
migration/legacy_execution_import.py
```

---

## Public CLI Design

The public CLI should expose AgentSpec lifecycle commands only. Existing
commands remain the compatibility baseline:

```bash
aspec init
aspec status
aspec next-action
aspec continue
aspec task create
aspec task next
aspec task complete
aspec run loop
aspec run step
aspec review code
aspec drift
aspec roadmap
aspec session start
aspec session finish
```

No public commands should include `hotl`.

Future commands such as `aspec plan`, `aspec execute`, `aspec verify-work`,
`aspec finish`, or `aspec migrate legacy-execution` should be introduced only
through accepted DCRs. They should delegate to the same task, workflow, run,
review, and write-back modules instead of creating parallel state.

### Command Mapping from HOTL Capabilities

| Old HOTL Action | New AgentSpec Command |
|---|---|
| setup project | `aspec init` |
| brainstorm | source intake / task creation flow |
| write plan | workflow creation or future `aspec plan` alias |
| run workflow | `aspec run loop` / future `aspec execute` alias |
| review work | `aspec review code` |
| finish branch | `aspec task complete` now; future `aspec finish` orchestrator |
| session start hook | `aspec session start` |
| session end summary | `aspec session finish` |

Optional: avoid adding `aspec discover` if you want to keep the CLI smaller.
Discovery can remain part of existing source intake and task creation flows.

---

## Lifecycle Model

AgentSpec should project the full lifecycle from existing native stages:

```text
source/spec -> task context pack -> workflow reference -> run/session
  -> verification -> review -> completion -> handoff -> roadmap/status
```

These stages absorb the HOTL execution sequence while preserving current
AgentSpec artifacts.

| Stage | Purpose | Primary Command | Main Artifact |
|---|---|---|---|
| Discovery | Understand problem and context | `aspec ingest`, `aspec intake ...`, `aspec compile` | `docs/source/*`, `docs/traceability/requirements.yml` |
| Specification | Define desired outcome | `aspec task create` | `agent/context-packs/T-*.md` |
| Planning | Link execution aid to task | workflow scanner / future `aspec plan` | `agent/workflows/*.md` or accepted legacy workflow path |
| Implementation | Run coding loop | `aspec run loop` / future `aspec execute` | `agent/runs/*`, active session lease |
| Verification | Prove work | run result / future `aspec verify-work` | task ledger verification status |
| Review | Critique and approve | `aspec review code` | `agent/reviews/REVIEW-####.yml` |
| Completion | Finalize and write back | `aspec task complete` / future `aspec finish` | ledger, handoff, roadmap, final summary |
| Handoff | Prepare next session | completion/write-back helpers | `agent/handoff.yml` |

---

## Workflow / Execution Plan Artifact

Recommended path:

```text
agent/workflows/W-001.md
```

Legacy paths such as `docs/**/plans/**workflow.md` remain valid scanner inputs
for migration and drift reporting. "Execution plan" should be treated as display
wording over the workflow contract, not a new required directory.

Example:

```markdown
---
workflow_id: W-001
display_name: Execution Plan
task_pack: agent/context-packs/T-001.md
status: planned
current_stage: planning
stream: billing
milestone: M2.1
slice: 4
branch: feat/billing-M2.1-slice-4-invoice-retry
created_at: 2026-05-10T09:30:00-07:00
updated_at: 2026-05-10T09:30:00-07:00
allowed_paths:
  - services/billing/**
  - tests/billing/**
protected_paths:
  - infra/prod/**
verification:
  commands:
    - npm test -- billing
    - npm run typecheck
writeback:
  required:
    - agent/handoff.yml
    - agent/task-ledger.yml
    - docs/ROADMAP.md
required_gates:
  - context
  - path
  - verification
  - review
  - writeback
---

# Workflow W-001: Add invoice retry policy

## Linked Task Pack

`agent/context-packs/T-001.md`

## Objective

Implement retry policy support for transient invoice submission failures.

## Plan

1. Inspect current billing submission flow.
2. Identify transient vs permanent failure classification.
3. Add retry configuration.
4. Implement retry wrapper.
5. Add tests.
6. Run verification.
7. Update handoff and roadmap.

## Implementation Loop

### Iteration 1

- Goal: Inspect current flow.
- Status: pending
- Notes:

### Iteration 2

- Goal: Implement retry wrapper.
- Status: pending
- Notes:

## Verification Plan

```bash
npm test -- billing
npm run typecheck
```

## Review Checklist

- [ ] Path scope respected
- [ ] Retry behavior is idempotent
- [ ] Tests cover transient and permanent failures
- [ ] Verification evidence recorded
- [ ] Handoff and roadmap updated

## Completion Checklist

- [ ] `agent/handoff.yml` updated
- [ ] `agent/task-ledger.yml` updated
- [ ] `docs/ROADMAP.md` regenerated
- [ ] final summary written
```

---

## Task Pack Changes

Task packs should link to workflows. User-facing docs may call the linked
workflow an execution plan, but the durable context-pack field should remain
compatible with existing workflow-pack support.

Path:

```text
agent/context-packs/T-001.md
```

Header fields:

```markdown
# T-001: Add invoice retry policy

Type: `implementation`
Stream: `billing`
Milestone: `M2.1`
Slice: `4`
Branch: `feat/billing-M2.1-slice-4-invoice-retry`
Workflow: `agent/workflows/W-001.md`
```

Bidirectional invariant:

```text
Task pack `Workflow:` must point to a workflow/execution plan.
Workflow front matter `task_pack` must point back to the task pack.
```

---

## Session State Model

HOTL's runtime state should be projected into existing AgentSpec run and session
state. Do not add a new `.agent-spec/sessions/*.json` authority.

### Machine-Readable Session Lease

Path:

```text
agent/sessions/active/2026-05-10T093000-0700.yml
```

Example:

```yaml
schema: agentspec.session_lease.v0
session_id: 2026-05-10T093000-0700
status: active
owner: yim
mode: owner
task_id: T-001
context_pack: agent/context-packs/T-001.md
branch: feat/billing-M2.1-slice-4-invoice-retry
run_id: run-t-001-20260510
allowed_paths:
  - services/billing/**
  - tests/billing/**
```

Run details and implementation loop state should stay under `agent/runs/*`.
Session leases should point to the run when the two concepts are related.

### Human-Readable Summary

Path:

```text
agent/runs/<run-id>/summary.yml
```

Optional human-facing summaries can be emitted as reports, but they should not
supersede run summaries, handoff, reviews, or the task ledger.

---

## Lifecycle Runtime

The old HOTL runtime behavior should become projection and orchestration helpers
over existing AgentSpec state:

```text
agentspec.writeback
agentspec.status
agentspec.run
agentspec.session
```

Responsibilities:

1. Load repo config.
2. Determine active task.
3. Determine linked workflow/execution plan.
4. Create or inspect session leases.
5. Read run state and completion summaries.
6. Capture changed files through existing run/session metadata when available.
7. Run lifecycle checks at stage boundaries.
8. Update handoff summaries when configured.
9. Emit next-action recommendations.

Suggested runtime API:

```python
class LifecycleProjection:
    def linked_workflow(self, task_id: str) -> WorkflowStatus: ...
    def run_status(self, task_id: str) -> RunStatus: ...
    def session_status(self, task_id: str) -> SessionStatus: ...
    def writeback_readiness(self, task_id: str) -> WriteBackReadiness: ...
    def next_action(self) -> NextAction: ...
```

---

## Implementation Loop

HOTL's execution loop should be reframed as AgentSpec's implementation loop.

Command:

```bash
aspec run loop
aspec run step --json
aspec run prompt <run-id>
```

Initial implementation can be lightweight and non-invasive:

- It does not need to run a coding agent.
- It can print instructions and update existing run/session state.
- Agents use run result ingestion or task completion to record progress.

Future `aspec execute` commands can be added as aliases over `aspec run ...`
once the run/session projection is stable.

### Example Output

```text
Task: T-001 Add invoice retry policy
Workflow: W-001
Current stage: implementation
Current iteration: 2

Allowed paths:
  - services/billing/**
  - tests/billing/**

Verification commands:
  - npm test -- billing
  - npm run typecheck

Next step:
  Implement retry wrapper and add tests.

After editing, run:
  aspec run result <run-id> --result-json '{"test_status":"passed"}'
  aspec review code --task T-001 --verdict ready --summary "No blocking findings."
```

---

## Review and Finish Integration

HOTL's review and finish behavior should map to AgentSpec-native gates.

### Review

Command:

```bash
aspec review code --task T-001 --verdict ready --summary "No blocking findings."
aspec review code --task T-001 --verdict needs-changes --summary "Blocking issue found."
```

Produces:

```text
agent/reviews/REVIEW-####.yml
```

Review gate checks:

- changed files are in scope
- protected paths are approved
- verification evidence exists
- known risks are recorded
- acceptance criteria are mapped to evidence

### Finish

Command:

```bash
aspec finish T-001
aspec finish T-001 --dry-run
```

This is a future orchestration command. Until it exists, `aspec task complete`
and the write-back helpers remain the authoritative completion path.

Finish must:

1. Validate task pack exists.
2. Validate linked workflow/execution plan exists when required.
3. Validate bidirectional links.
4. Validate branch policy.
5. Validate changed files against allowed paths.
6. Validate protected path approvals.
7. Validate verification evidence.
8. Validate linked review evidence under `agent/reviews/`.
9. Update `agent/handoff.yml`.
10. Update `agent/task-ledger.yml`.
11. Regenerate `docs/ROADMAP.md`.
12. Write or preserve final run/task summary.
13. Mark task and workflow/execution plan as complete.
14. Finish or release active session if one exists.

---

## Lifecycle Hooks

HOTL hooks should become AgentSpec lifecycle checks. Blocking shell hooks should
remain deferred until warning-mode checks and repair commands are stable.

Hook directory:

```text
.agentspec/hooks/
```

The hook directory is optional future state. Fresh projects should not install
blocking hooks by default.

Built-in hook events:

```text
session_start
session_end
before_plan
before_execute
after_execute
before_verify
after_verify
before_review
after_review
before_finish
after_finish
```

Config:

```yaml
hooks:
  session_start:
    enabled: true
    checks:
      - drift
      - active_task
      - stale_session
  before_finish:
    enabled: true
    checks:
      - verification
      - review
      - writeback
```

### Session Start Hook

Command:

```bash
aspec session start
```

Behavior:

1. Run drift scan.
2. Detect active task.
3. Detect orphan workflows/execution plans.
4. Detect stale sessions.
5. Print next action.
6. Create machine-readable session lease under `agent/sessions/active/`.
7. Link the session to the active run when one exists.

Example output:

```text
AgentSpec session started.

Active task: T-001 Add invoice retry policy
Workflow: W-001
Current stage: implementation

Warnings:
  - Verification evidence is missing.

Next:
  Run verification and record the result before review.
```

---

## Drift Detection Without HOTL Naming

Drift checks should refer to AgentSpec artifacts only.

| Drift Type | Meaning |
|---|---|
| `orphan_workflow` | Workflow/execution plan exists without linked task pack |
| `unplanned_active_task` | Task is active but has no linked workflow when one is required |
| `broken_workflow_link` | Task and workflow do not reference each other |
| `stale_session` | Session state references missing or completed task |
| `missing_verification_evidence` | Task requires verification but no evidence exists |
| `missing_review_evidence` | Task requires review but no evidence exists |
| `missing_writeback` | Task completion did not update required files |
| `roadmap_stale` | Roadmap generated block does not match canonical state |
| `handoff_stale` | Handoff does not reflect active/completed state |

### Legacy HOTL Import Detection

For migration only, AgentSpec may scan legacy paths:

```text
docs/**/plans/**workflow.md
.hotl/state/**/*.json
```

But user-facing output should avoid HOTL naming where possible.

Instead of:

```text
Found orphan HOTL workflow
```

Use:

```text
Found legacy execution plan without an AgentSpec task pack
```

Recommended repair:

```bash
aspec task create --from-workflow <file>
```

or:

```bash
aspec migrate legacy-execution
```

---

## Migration Design

## Command

```bash
aspec migrate legacy-execution
aspec migrate legacy-execution --from docs/streams/billing/plans/foo-workflow.md
aspec migrate legacy-execution --write
```

No public command should say `hotl`.

## Migration Inputs

Supported legacy inputs:

```text
docs/**/plans/**workflow.md
.hotl/state/**/*.json
```

## Migration Outputs

```text
agent/context-packs/T-*.md
agent/workflows/W-*.md
agent/reviews/REVIEW-####.yml or reports/migration/<task>.md
```

## Migration Behavior

For each legacy workflow file:

1. Parse front matter if present.
2. Extract title from heading or filename.
3. Extract stream/milestone/slice from path or filename.
4. Extract allowed paths if present.
5. Extract verification commands if present.
6. Create task pack if no matching task exists.
7. Create or link workflow/execution plan preserving original plan content.
8. Add bidirectional references.
9. Write migration notes.
10. Mark source path in metadata as `migrated_from`.

Example generated metadata:

```yaml
migrated_from:
  type: legacy_workflow
  path: docs/streams/billing/plans/billing-M2.1-slice-4-retry-workflow.md
  migrated_at: 2026-05-10T12:00:00-07:00
```

This avoids HOTL naming while preserving provenance.

---

## Generated AGENTS.md Rules

AgentSpec should generate rules that make the absorbed execution lifecycle obvious to coding agents.

```markdown
<!-- aspec:agents:start -->
## AgentSpec Lifecycle Rules

Before making changes:

1. Run `aspec status`.
2. If no active task exists, create or select a task pack.
3. Do not start implementation without a task context pack.
4. Keep task packs and linked workflows bidirectionally linked when a workflow is used.
5. Respect `allowed_paths` and `protected_paths` in the active task pack.
6. Record implementation progress through `aspec run ...` or session notes when useful.
7. Record passed verification before review.
8. Run `aspec review code` before completion.
9. Complete through `aspec task complete` or future `aspec finish` so handoff, ledger, roadmap, and final summary stay current.

Completion is not done until write-back is complete.
<!-- aspec:agents:end -->
```

---

## Config Design

Path:

```text
.agentspec/config.yml
```

Example:

```yaml
version: 1
project:
  name: example-service

paths:
  sources: docs/source
  requirements: docs/traceability/requirements.yml
  task_packs: agent/context-packs
  workflows: agent/workflows
  runs: agent/runs
  sessions: agent/sessions
  reviews: agent/reviews
  handoff: agent/handoff.yml
  ledger: agent/task-ledger.yml
  roadmap: docs/ROADMAP.md

lifecycle:
  strict: false
  require_task_for_workflow: true
  require_workflow_for_execution: false
  require_verification_for_review: true
  require_review_for_finish: true
  require_writeback_for_finish: true

execution:
  record_sessions: true
  record_runs: true
  update_handoff_on_stage_change: false

branch_policy:
  enabled: true
  pattern: "^(feat|fix|chore|docs)/[a-z0-9-]+-M[0-9]+\\.[0-9]+-slice-[0-9]+-[a-z0-9-]+$"

writeback:
  required_files:
    - agent/handoff.yml
    - agent/task-ledger.yml
    - docs/ROADMAP.md

hooks:
  session_start:
    enabled: true
    checks:
      - drift
      - stale_session
      - active_task
  before_finish:
    enabled: true
    checks:
      - verification
      - review
      - writeback
```

---

## Code Refactoring Strategy

If HOTL code already exists in a separate repository, integrate by refactoring concepts, not copying names.

### Step 1: Identify Reusable Behaviors

Reusable behavior categories:

```text
plan template generation
step/loop state recording
session hooks
execution progress summaries
review checklist generation
finish branch write-back
```

### Step 2: Rename During Import

| Existing HOTL Module | New AgentSpec Module |
|---|---|
| `hotl_rt` | `status` / `run` / `session` projection helpers |
| `writing_plans` | `workflow` planning helpers |
| `loop_execution` | `run` implementation-loop helpers |
| `subagent_execution` | future delegated run adapter |
| `review` | `review` evidence helpers |
| `finishing_branch` | `writeback` completion helpers |
| `session_start` | `session` lease helpers |

### Step 3: Replace HOTL File Paths

| Old Path | New Path |
|---|---|
| `.hotl/state/*.json` | `agent/runs/*` and `agent/sessions/active|archived/*.yml` projections |
| `.hotl/contract-enforced` | `.agentspec/config.yml` lifecycle settings |
| `docs/**/plans/*workflow.md` | accepted legacy workflow input or `agent/workflows/W-*.md` |
| HOTL summary scripts | `agentspec.writeback` helpers |

### Step 4: Replace HOTL Terms in User-Facing Text

| Avoid | Use |
|---|---|
| HOTL | AgentSpec |
| HOTL workflow | AgentSpec workflow or execution plan |
| HOTL state | run/session state |
| finishing branch | finish / completion |
| loop execution | implementation loop |
| writing plans | planning |

---

## Backward Compatibility

AgentSpec should support reading legacy artifacts for migration and drift reporting, but should not create new legacy artifacts.

Compatibility modes:

| Mode | Behavior |
|---|---|
| `read_legacy` | Detect and read legacy execution files for drift/migration |
| `migrate_legacy` | Convert legacy artifacts into AgentSpec artifacts |
| `write_legacy` | Not supported by default |

Config:

```yaml
legacy:
  read_legacy_workflows: true
  write_legacy_artifacts: false
```

---

## Strict Mode Behavior

Strict mode should enforce AgentSpec-native lifecycle rules.

When strict mode is enabled:

1. Implementation commands refuse to run without a task pack.
2. Workflow-aware commands refuse to use broken task/workflow links.
3. Future planning commands refuse to create unlinked workflows.
4. Future finish orchestration refuses completion without passed verification.
5. Future finish orchestration refuses completion without linked review evidence unless explicitly waived.
6. Future finish orchestration refuses completion if write-back is stale.
7. Future finish orchestration refuses completion if changed files exceed allowed paths.
8. Future finish orchestration refuses completion if protected paths changed without approval.

No strict-mode error should mention HOTL.

Example:

```text
Cannot continue implementation.

Reason:
  Linked workflow is missing for active task T-001.

Fix:
  aspec task create --from-workflow <file>
```

---

## Detailed Command Behavior

## Future `aspec plan`

Purpose:

Create or update an AgentSpec workflow/execution plan.

```bash
aspec plan T-001
aspec plan --current
aspec plan --from-task agent/context-packs/T-001.md
```

Behavior:

- Requires task pack.
- Creates `agent/workflows/W-*.md`.
- Copies relevant task metadata.
- Adds bidirectional links.
- Sets task status to `planned`.
- Emits next command: `aspec run loop` or future `aspec execute T-001`.

## Future `aspec execute`

Purpose:

Guide and record implementation progress.

```bash
aspec execute T-001
aspec execute --current
aspec execute --record "Implemented retry wrapper"
aspec execute --stage implementation
```

Behavior:

- Requires task and valid workflow link in strict mode when configured.
- Starts session if none exists.
- Updates existing run/session state.
- Records implementation notes.
- Captures changed files.
- Prints allowed paths and verification commands.

## `aspec session start`

Purpose:

Start an AgentSpec-aware work session.

```bash
aspec session start
aspec session start T-001
```

Behavior:

- Runs drift check.
- Detects active task.
- Creates session state file.
- Prints next action.
- Warns on stale state.

## `aspec session finish`

Purpose:

Finish a session lease with a disposition.

```bash
aspec session finish <session-id> --disposition keep
aspec session finish <session-id> --disposition pr --test-status passed
```

Behavior:

- Archives active session state.
- Records disposition, review id, test status, and finish note.
- Leaves handoff, roadmap, and task completion to write-back commands.

## `aspec finish`

Purpose:

Complete task lifecycle and write back canonical state.

Behavior described earlier.

This command replaces HOTL branch finishing behavior only after the shared
write-back module is stable. It should orchestrate existing review, ledger,
handoff, roadmap, run, and session artifacts.

---

## Migration Examples

## Legacy Plan Exists Without Task Pack

Input:

```text
docs/streams/billing/plans/billing-M2.1-slice-4-retry-workflow.md
```

Command:

```bash
aspec migrate legacy-execution --from docs/streams/billing/plans/billing-M2.1-slice-4-retry-workflow.md --write
```

Output:

```text
agent/context-packs/T-001.md
agent/workflows/W-001.md
reports/migration/T-001.md
```

Reported message:

```text
Imported legacy workflow as AgentSpec planning evidence.

Created:
  Task pack: agent/context-packs/T-001.md
  Workflow: agent/workflows/W-001.md

Next:
  aspec status
```

## Existing Task Pack and Legacy Plan

If a matching task already exists, AgentSpec should link the generated workflow
to the existing task rather than creating a duplicate.

Matching heuristics:

- task ID in legacy file
- title similarity
- branch name
- stream/milestone/slice
- changed paths

---

## Testing Strategy

## Unit Tests

Test:

- workflow parsing
- task/workflow bidirectional link validation
- session lease creation
- drift detectors
- write-back functions
- migration parser
- strict-mode gate behavior

## Integration Tests

Fixture repos:

```text
fixtures/new_project_empty
fixtures/project_with_task_no_workflow
fixtures/project_with_workflow_no_task
fixtures/project_with_active_session
fixtures/project_with_legacy_workflow
fixtures/project_with_missing_writeback
fixtures/project_strict_mode
```

Test flows:

1. `aspec init`
2. `aspec task create`
3. workflow link or future `aspec plan`
4. `aspec session start`
5. `aspec run loop`
6. record passed verification
7. `aspec review code`
8. `aspec task complete` or future `aspec finish`
9. `aspec drift`
10. `aspec migrate legacy-execution`

## Golden File Tests

Use golden files for:

- generated task pack
- generated workflow/execution plan
- generated roadmap block
- generated AGENTS.md block
- migration output

---

## Implementation Phases

## Phase 1: Terminology and File Model

Deliverables:

- Confirm workflow/execution-plan terminology over the existing workflow model.
- Reuse `agent/workflows/` for new planning artifacts.
- Extend front matter parsing only where current workflow parsing is insufficient.
- Add task/workflow bidirectional links.
- Update docs and templates to AgentSpec terminology.

Acceptance criteria:

- No new generated file contains HOTL naming.
- Task packs can link to workflows/execution plans.
- Workflows can link to task packs.

## Phase 2: Native Planning Command

Deliverables:

- future `aspec plan` alias
- workflow creation from task pack
- link validation
- status integration

Acceptance criteria:

- `aspec plan T-001` creates or links `agent/workflows/W-001.md`.
- `aspec status` shows task and linked workflow state.

## Phase 3: Session Runtime

Deliverables:

- `aspec session start`
- `aspec session finish`
- `agent/sessions/active/*.yml`
- `agent/sessions/archived/*.yml`
- implementation loop recording

Acceptance criteria:

- Sessions can be started and finished.
- Changed files are captured.
- Session dispositions are archived.

## Phase 4: Execute Command

Deliverables:

- future `aspec execute` alias over `aspec run ...`
- implementation loop state
- allowed path display
- verification command display
- progress recording

Acceptance criteria:

- Agents can use AgentSpec commands to understand and record implementation progress.
- Strict mode blocks execution without task and required workflow link.

## Phase 5: Review and Finish

Deliverables:

- `aspec review code`
- `aspec finish`
- write-back integration
- final summary generation
- session finish integration

Acceptance criteria:

- Completion updates handoff, ledger, roadmap, review linkage, task status, and workflow status.

## Phase 6: Drift and Next Action

Deliverables:

- orphan workflow detector
- unplanned active task detector
- stale session detector
- missing write-back detector
- `aspec next-action` / `aspec continue` integration

Acceptance criteria:

- `aspec next-action` does not report no work when orphan workflow or lifecycle drift exists.

## Phase 7: Legacy Migration

Deliverables:

- `aspec migrate legacy-execution`
- parser for legacy workflow files
- parser for legacy state JSON
- migration notes
- idempotent migration

Acceptance criteria:

- Existing HOTL-style projects can be converted without keeping `.hotl/` as source of truth.
- User-facing migration output uses AgentSpec terminology.

---

## Acceptance Criteria

The integration is successful when:

1. New AgentSpec projects do not generate `.hotl/`.
2. New AgentSpec projects do not expose HOTL terminology.
3. AgentSpec has native workflows that can be described as execution plans.
4. AgentSpec has native run and session lease state.
5. AgentSpec can guide implementation loops.
6. AgentSpec can record verification and review evidence.
7. AgentSpec finish performs write-back.
8. AgentSpec drift detects orphan workflows and unplanned active tasks.
9. AgentSpec can migrate legacy execution artifacts into AgentSpec artifacts.
10. `aspec status` and `aspec next-action` reflect the full lifecycle state.

---

## Unresolved Design Decisions

1. Where should user-facing copy say `execution plan` while durable artifacts keep `workflow`?
2. Should new native workflow files use only `agent/workflows/`, or should external workflow paths remain authorable?
3. Should optional human-readable run/session summaries be committed by default?
4. Should future `aspec execute` invoke coding agents later, or remain an alias over run guidance/recording?
5. Should legacy HOTL import preserve original file paths or always copy to AgentSpec paths?
6. Should workflow IDs remain `W-001` or become task-derived such as `T-001-plan`?
7. Should strict mode be enabled by `aspec init --strict` only, or can individual streams opt in?
8. Should handoff be updated on every implementation loop iteration or only at finish/session end?
9. Should generated session summaries be included in roadmap inputs?
10. Should review evidence support multiple reviewers and approval types in MVP?

---

## Recommended Decisions

1. Keep `workflow` as the durable AgentSpec contract; use `execution plan` as optional user-facing wording.
2. Use `agent/workflows/` for new native workflow artifacts.
3. Use `agent/sessions/active|archived/` for machine-readable session leases.
4. Use `agent/runs/*/summary.yml` and `agent/handoff.yml` for durable summaries.
5. Preserve existing `aspec run`, `aspec review code`, and `aspec task complete` commands; add `aspec plan`, `aspec execute`, and `aspec finish` only as DCR-backed aliases/orchestrators.
6. Do not expose HOTL naming in public commands or generated files.
7. Use `aspec migrate legacy-execution` for migration.
8. Preserve legacy source paths only in metadata as `migrated_from`.
9. Make strict execution enforcement opt-in.
10. Implement drift and finish write-back before advanced agent delegation.

---

## End-to-End Example

```bash
aspec init
aspec task create "Add invoice retry policy"
aspec task create --from-workflow agent/workflows/W-001.md
aspec session start T-001
aspec run loop
aspec review code --task T-001 --verdict ready --summary "No blocking findings."
aspec task complete T-001 --test-status passed
aspec status
```

Generated/updated files:

```text
agent/context-packs/T-001.md
agent/workflows/W-001.md
agent/sessions/active/2026-05-10T093000-0700.yml
agent/runs/<run-id>/summary.yml
agent/reviews/REVIEW-####.yml
agent/handoff.yml
agent/task-ledger.yml
docs/ROADMAP.md
```

No `.hotl/` files are generated.

---

## Final Recommendation

Keep `agent-spec-engine` as the main repo and `aspec` as the CLI.

Do not integrate HOTL as a named dependency or public concept. Instead, absorb
the useful execution lifecycle into AgentSpec as native lifecycle behavior:

```text
discovery
specification
planning
implementation loop
verification
review
completion
handoff
```

Use AgentSpec-native artifacts:

```text
task packs
workflows / execution-plan wording
runs
session leases
reviews
handoff
ledger
roadmap
```

The result is a single coherent product:

> AgentSpec is a repo-local lifecycle engine for spec-driven agent development.

It keeps the familiar `aspec` interface, avoids naming collisions, removes `.hotl/` from new projects, and preserves the core HOTL value: structured execution, review, finishing, hooks, and stateful progress across agent sessions.
