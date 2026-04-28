# ADR-0003: Supervised Run Protocol

Status: accepted
Date: 2026-04-28
Related: `DCR-0001-supervised-runs.md`, `T-004-spike-supervised-runs`,
`R-127`, `R-128`, `R-129`, `R-130`

## Context

AgentSpec already creates durable task context packs, role definitions,
requirements, and audit-friendly repository artifacts. The remaining gap is
the inner loop after a code agent starts work: the executor may pause with a
low-risk question such as:

```text
Want me to proceed with T-008, or pick one of the others?
```

Today a human has to read that reply, decide whether the agent should continue,
and manually send a response. `DCR-0001` proposes a supervised run / agent reply
loop to make that handoff explicit and auditable.

The T-004 spike concluded that the system should not use a second agent that
blindly replies `continue`. It should use a bounded controller that reviews
run state, the active context pack, touched paths, verification status, and
policy gates before sending any continuation message.

## Decision

Adopt a **file-backed supervised run protocol** with a single executor and a
separate reviewer/controller.

The protocol has five responsibilities:

1. **Executor** — the code-writing agent that performs work from exactly one
   active context pack.
2. **Collector** — the adapter that records executor output, touched paths,
   diff summaries, test summaries, explicit questions, and model/tool profile
   metadata.
3. **Reviewer/controller** — a model or deterministic checker that classifies
   each iteration into `auto_continue`, `pause_for_human`, `halt`, or
   `complete`, and optionally emits the next message to the executor.
4. **Policy gate** — the deterministic layer that can downgrade or override a
   reviewer verdict based on allowed paths, forbidden paths, required tests,
   iteration caps, source classification, secrets, and approval requirements.
5. **Run state** — durable files under `agent/runs/<run-id>/` containing
   iteration evidence and controller decisions.

The first productized implementation should expose this through future CLI
commands shaped like:

```bash
aspec run start agent/context-packs/T-008-dcr-accept-cascade-fix.md
aspec run resume <run-id>
aspec run inspect <run-id>
aspec run abort <run-id>
```

This ADR does not implement those commands. It defines the protocol those
commands should follow.

## Verdicts

The reviewer/controller returns a structured verdict.

```json
{
  "schema": "agentspec.supervised_run.verdict.v0",
  "run_id": "supervised-run-spike",
  "iteration": 1,
  "decision": "auto_continue",
  "confidence": "high",
  "reason": "T-008 is already the active context pack; proceeding does not select a new task or expand scope.",
  "message_to_executor": "Continue with T-008. Use the T-008 context pack as the active scope, work only inside its allowed paths, and run its listed verification before reporting completion.",
  "requires_human": false,
  "policy_flags": [],
  "evidence_refs": [
    "agent/context-packs/T-008-dcr-accept-cascade-fix.md"
  ]
}
```

`auto_continue` is allowed only when:

- exactly one active context pack is known
- the executor's next step stays inside that pack's allowed paths
- no product, priority, architecture, credential, or risk decision is requested
- no destructive command, forbidden path, or scope expansion is involved
- iteration count remains below `max_iterations`

`pause_for_human` is required when the executor asks the human to pick a task,
approve scope expansion, decide an unresolved product or architecture question,
provide credentials, or accept risk.

`halt` is required when forbidden paths are touched, a required policy gate
fails, the active context pack cannot be found, or the run exhausts its
iteration cap.

`complete` is allowed only when the task acceptance criteria are met,
verification evidence is present, and no blocking reviewer finding remains.

## Dogfood Rule

For the specific dogfood reply:

```text
Want me to proceed with T-008, or pick one of the others?
```

The controller may answer automatically only if the persisted run state already
names `T-008` as the active context pack. The controller should not send a bare
`continue`; it should send a scoped response:

```text
Continue with T-008. Use the T-008 context pack as the active scope, work only
inside its allowed paths, and run its listed verification before reporting
completion.
```

If no active run state exists, the controller must pause for the human because
choosing among tasks is a prioritization decision.

## Model Profiles

Resolve `Q-012` as a proposed decision:

- The **main executor** is the currently interactive code agent and should
  default to that host's active/default model. AgentSpec should not require a
  model setting for it.
- `continuation_reviewer` may use a cheaper/faster model to classify low-risk
  pauses and produce scoped continuation messages.
- `quality_reviewer` should use a stronger model for final diff, requirement,
  and test coverage review.

Both model profiles should be configurable per repository and overridable per
context pack. The executor and reviewer/controller may use different models.

For Codex-hosted runs, secondary agent profiles may resolve provider
configuration from the user's existing Codex setup, such as
`~/.codex/config.toml` and `~/.codex/auth.json`. AgentSpec must not copy API
keys or bearer tokens into repository artifacts. It should store only profile
names, provider ids, model ids, endpoint names, and credential-source
references. Credentials are resolved at runtime by the local adapter.

An example repository-level shape:

```json
{
  "agent_profiles": {
    "main_executor": {
      "adapter": "current-host",
      "model": "host-default"
    },
    "continuation_reviewer": {
      "adapter": "codex",
      "credential_source": "codex-auth",
      "config_source": "codex-config",
      "model": "oca/gpt-5.4-mini",
      "reasoning": "low"
    },
    "quality_reviewer": {
      "adapter": "codex",
      "credential_source": "codex-auth",
      "config_source": "codex-config",
      "model": "oca/gpt-5.5",
      "reasoning": "high"
    }
  },
  "supervised_runs": {
    "executor_profile": "main_executor",
    "continuation_reviewer_profile": "continuation_reviewer",
    "quality_reviewer_profile": "quality_reviewer"
  }
}
```

The concrete model ids are environment-specific. A Codex adapter may discover
available models from the configured provider, but discovery output should be
treated as local runtime state rather than committed project truth.

## Iteration Cap

Resolve `Q-013` as a proposed default:

- small implementation/fix: `max_iterations = 3`
- spike/spec/review task: `max_iterations = 2`
- migration task: no default auto loop until partitioned write scopes exist

The cap counts executor attempts. Reviewer/controller passes do not increment
the cap unless they trigger another executor attempt.

## Run State Retention

Resolve `Q-014` as a proposed split:

- durable audit metadata may be committed: verdicts, diff hashes, touched
  paths, test command names, model profile names, confidence, evidence refs,
  and pause reasons
- raw model transcripts, long logs, terminal output, and sensitive output stay
  local by default

The MVP can begin with `agent/runs/<run-id>/events.jsonl`. A later schema may
add a committed `summary.yml` and ignored raw transcript files.

## Consequences

### Positive

- Low-risk continuation prompts no longer stop useful work.
- The reply loop becomes auditable instead of hidden in chat history.
- Different models can be used for execution, cheap continuation review, and
  final quality review.
- `R-127` through `R-130` gain a concrete protocol boundary before production
  implementation.

### Negative / Costs

- AgentSpec gains a new runtime concept and eventual CLI surface.
- The controller can create false confidence if policy gates are too weak.
- Adapter-specific resume mechanics may differ across Codex, Claude Code,
  Cursor, GitHub agents, and other executors.
- Run-state retention needs careful handling to avoid committing sensitive logs.

### Neutral

- This does not turn AgentSpec into a general-purpose autonomous coding agent.
  The task context pack remains the unit of work.
- This does not allow multiple concurrent writers by default. A supervised run
  has one executor unless a future context pack explicitly partitions writes.

## Implementation Guidance

The first implementation context pack should build the smallest local protocol:

- `agentspec/run.py` for run state and loop orchestration
- `agentspec/review.py` for verdict schema and reviewer adapter boundaries
- `agentspec/policy.py` for deterministic gate evaluation
- `agentspec/cli.py` for `run start | resume | inspect | abort`
- tests covering `auto_continue`, `pause_for_human`, `halt`, `complete`, and
  JSONL run-state replay

The first implementation must not auto-accept DCRs, ADRs, or requirements.
Requirement acceptance remains a separate explicit step.

## Status of this ADR

Accepted on 2026-04-28 by yimwu after the T-004 spike and T-009 ADR draft.
Implementation requirements `R-127` through `R-130` still require verified
implementation packs before they may be promoted.
