# Controlled Lifecycle Evaluation Pilot

`EXP-lifecycle-pilot` is a one-task, one-replicate smoke evaluation of the
AgentSpec lifecycle treatment against a direct-prompt control for both Codex
and Claude Code. It is designed to validate the experiment procedure and
evidence pipeline, not to establish a general performance claim.

## Fixed task

The provider receives a small Python repository containing a deliberately
incomplete `slugify` implementation. The requested change must:

- preserve the existing ASCII behavior;
- normalize accented Latin text using the Python standard library;
- keep separator collapsing and fallback behavior;
- add or update public tests; and
- avoid new dependencies.

The provider workspace contains `task.md`, `src/identifier.py`, and the public
tests under `tests/`. The oracle in `oracle/identifier_oracle.py` remains
outside the provider workspace and is run only after the provider exits.

## Conditions

- `with-agentspec`: the fixture is initialized through AgentSpec, the task is
  represented by a ready context pack and workflow, and the provider is asked
  to use the AgentSpec continuation skill.
- `control`: the same fixture and task text are provided without AgentSpec
  project artifacts or plugin instructions.

Each provider/condition cell runs in a separate temporary Git repository. The
manifest pins the provider model, environment, task digest, oracle digest,
limits, and replicate. AgentSpec records evidence after execution; it does not
grant provider credentials, execute the providers, or expand their authority.

## Scoring

Completion requires both the public tests and the hidden oracle to pass. A
failed hidden assertion counts as an escaped defect. Regressions are failed
public tests. Retries and human interventions are recorded from the execution
log; unavailable cost fields remain explicit rather than estimated.

The public result is summarized in
`docs/evaluations/EXP-lifecycle-pilot.md`. Raw provider transcripts and
temporary workspaces remain outside the repository.

## Current execution status

The first Codex control and AgentSpec cells were recorded on 2026-06-30. Both
passed the public suite and hidden oracle, while the AgentSpec condition also
completed lifecycle review and write-back. The observations are limited: the
CLI did not report actual cost, and the runner did not enforce the manifest's
nominal token cap.

The Claude pair remains unexecuted because this host could authenticate Claude
Code but could not connect to `api.anthropic.com:443`. See the public report and
the non-sensitive blocker record under `agent/evals/EXP-lifecycle-pilot/`.
