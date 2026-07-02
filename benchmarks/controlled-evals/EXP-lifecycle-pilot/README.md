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

The Claude pair remains unexecuted. The original 2026-06-30 blocker was network
connectivity. On 2026-07-01 the endpoint became reachable, but two minimal
`claude-opus-4-8` probes returned HTTP 401 even though local auth status reported
a logged-in subscription. See the non-sensitive blocker records under
`evidence/blockers/`.

## Capability-aware protocol revision

`manifest-v2.yml` is the immutable rerun protocol prepared after the first
pilot exposed an unenforced token declaration. Its SHA-256 is
`b22aa291b8543f90ca5fbd6050de5e5c663840d507342f6dce271abcd1e79e7d`.

The v2 runner derives models and limits from that manifest. It terminates the
provider process group at the duration deadline, bounds runner retries at zero,
passes Claude's USD ceiling through its native budget flag, and checks token
usage after completion. Codex currently reports usage in its final JSONL event,
so its token threshold is a validity gate rather than a mid-turn spend stop.
Any exceeded or required-but-unobserved threshold makes the runner exit
non-zero and prevents the cell from contributing to valid comparisons.

Run a fresh cell only after provider connectivity succeeds:

```bash
python benchmarks/controlled-evals/EXP-lifecycle-pilot/run_provider.py \
  --manifest benchmarks/controlled-evals/EXP-lifecycle-pilot/manifest-v2.yml \
  --provider codex \
  --condition control \
  --workspace /absolute/path/to/fresh-workspace \
  --output-dir /absolute/path/to/new-raw-evidence
```

The original manifest and run records remain unchanged; v2 observations must
use new workspaces, output directories, experiment IDs, and evidence IDs.

The v2 model pins remain Codex `gpt-5.5` and Claude `claude-opus-4-8`. A
2026-07-01 `gpt-5.6-sol` probe reached the provider but was rejected because it
requires a newer Codex app or CLI than the pinned `0.137.0` environment. The
protocol therefore keeps the last successfully verified Codex model rather
than recording an unexecutable pin.
