# DCR-0012: Add model-backed continuation reviewer MVP

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-28 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-28 |
| Confidence | medium |

## Summary

Add an optional model-backed continuation reviewer path for supervised runs.
Deterministic policy gates remain authoritative; model review is used only
after policy allows the iteration and the deterministic reviewer would
otherwise pause for a human.

The MVP accepts structured reviewer JSON from a configured reviewer profile,
records the verdict in the run log, and falls back safely to deterministic
pause when no model adapter response is available.

## Motivation

The local control plane can already select tasks, run bounded iterations, and
apply deterministic continuation rules. The next product goal is to let a
separate reviewer model answer low-risk pauses so the executor can continue
without waiting on the human for every routine prompt.

## Proposed Change

- Add a model-review adapter layer with a strict JSON verdict schema.
- Support a deterministic `static` adapter for tests and a best-effort
  `codex`/LiteLLM HTTP adapter for configured local use.
- Add `--reviewer deterministic|model|auto` to `aspec run resume` and
  `aspec run loop`.
- Keep policy halts and verification-completion rules deterministic.
- Record model-backed verdicts as normal reviewer events.

## Impact Assessment

- Supports `R-007` by extending the local CLI.
- Supports `R-127` by preserving bounded run and allowed-path enforcement.
- Supports `R-129` by introducing a structured reviewer verdict path
  consumable by the next iteration.
- Does not fully satisfy `R-129` until prior reviewer findings are fed into
  the next executor prompt.
- Code surface: `agentspec/model_review.py`, `agentspec/review.py`,
  `agentspec/run.py`, `agentspec/cli.py`, `agentspec/config.py`.
- Test surface: model reviewer unit and CLI tests.

## Disposition

Classification: `implement-now`.

This implements an MVP adapter boundary from ADR-0003 without making model
availability a hard dependency.

## Acceptance Criteria

- `aspec run resume --reviewer model` can use a configured reviewer profile to
  return `auto_continue`.
- Policy halt cannot be overridden by a model verdict.
- Invalid or unavailable model output falls back to deterministic pause.
- Model-backed completion cannot bypass failed or missing verification.
- `python -m unittest discover -s tests -v` passes.
