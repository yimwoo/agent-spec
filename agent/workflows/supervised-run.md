# Supervised Run

Task type: `spike` / future `automation`

## Purpose

Keep one executor agent moving through a bounded task context pack by having a
separate reviewer/controller classify each executor response and produce either
a safe continuation message or a human pause.

## Inputs

- `context_pack`: path to exactly one `agent/context-packs/T-*.md`
- `run_id`: stable id for `agent/runs/<run-id>/`
- `max_iterations`: integer cap, default proposed by the task or policy
- `executor_profile`: model/tool profile for the code-writing agent
- `reviewer_profile`: model/tool profile for the reviewer/controller agent
- `policy`: allowed paths, forbidden paths, required tests, approval gates

## Loop

1. Load the context pack and active run state from disk.
2. Invoke or resume the executor with the current task, prior reviewer verdict,
   and the latest run evidence.
3. Collect executor output, touched paths, diff summary, test summary, and any
   explicit user-facing question.
4. Ask the reviewer/controller for a structured verdict.
5. Apply the policy gate.
6. Append executor output, reviewer verdict, policy verdict, and controller
   response to `agent/runs/<run-id>/events.jsonl`.
7. Continue only when the verdict is `auto_continue`; otherwise pause or halt.

## Reviewer Verdict Schema

```json
{
  "schema": "agentspec.supervised_run.verdict.v0",
  "run_id": "supervised-run-spike",
  "iteration": 1,
  "decision": "auto_continue",
  "confidence": "high",
  "reason": "The executor is asking to proceed with the active context pack.",
  "message_to_executor": "Continue with T-008. Work only inside the allowed paths in that context pack, run the listed tests, and report verification evidence.",
  "requires_human": false,
  "policy_flags": [],
  "evidence_refs": [
    "agent/context-packs/T-008-dcr-accept-cascade-fix.md"
  ],
  "next_verification": [
    "python -m unittest discover -s tests -v"
  ]
}
```

## Decision Rules

- `auto_continue`: executor asks for permission to continue the active context
  pack; no new task selection, external access, destructive command, forbidden
  path, or unresolved policy gate is involved.
- `pause_for_human`: executor asks the human to choose among multiple tasks,
  approve a scope expansion, decide a product tradeoff, provide credentials, or
  accept risk.
- `halt`: executor exceeded `max_iterations`, touched forbidden paths, cannot
  identify the active context pack, or attempts an unsafe operation.
- `complete`: acceptance criteria are met and verification evidence is present.

## Dogfood Rule

For a reply like:

```text
Want me to proceed with T-008, or pick one of the others?
```

The controller may answer automatically only if the run state says `T-008` is
the active context pack. The response should be more specific than `continue`:

```text
Continue with T-008. Use the T-008 context pack as the active scope, work only
inside its allowed paths, and run its listed verification before reporting
completion.
```

If there is no active context pack, the controller must pause because choosing
between tasks is a prioritization decision.
