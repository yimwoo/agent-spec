# Getting Started With AgentSpec

This guide is for humans operating AgentSpec on a repository. It explains the
smallest useful workflow and the artifacts that keep humans and agents aligned.

For the short project overview, start with [../README.md](../README.md).

## Mental Model

AgentSpec is a repo-local operating contract.

The accepted design lives in `docs/source/`. The compiled requirements live in
`docs/traceability/requirements.yml`. Work happens from task context packs in
`agent/context-packs/`. Execution state, review evidence, task completion,
roadmap status, and handoff state are written back to committed artifacts.

This gives a future human or agent enough context to continue without relying on
chat history.

Key terms:

| Term | Meaning |
|---|---|
| Source snapshot | Immutable source material accepted into `docs/source/`. |
| Candidate snapshot | Imported external material awaiting review under `docs/source/candidates/`. |
| Requirement | A traceable obligation, usually `R-###`, in `docs/traceability/requirements.yml`. |
| DCR | A design change request for scope that changes after the accepted snapshot. |
| Task context pack | The bounded work packet an agent may execute. |
| Workflow | The native AgentSpec execution plan linked to a task pack. |
| Handoff | The latest durable project status in `agent/handoff.yml`. |

This guide covers `R-207`. The lifecycle operating contract is covered by
`R-205`; the dogfood end-to-end workflow is covered by `R-203`; prompt-first
code-agent usage is covered by `R-208`.

## Prompt-First Operating Model

AgentSpec is designed so humans can prompt a code agent instead of manually
running every CLI command. The agent should use `aspec` as the project control
plane, then report durable evidence back to the human.

Use this for a new project:

```text
Use AgentSpec to initialize this repository. The design source is at
docs/source/design.md. Set up Codex and Claude agent guidance, compile the
requirements, report readiness/open questions, and propose the first task
context packs. Do not start implementation until the task scope and allowed
paths are clear.
```

Use this for an existing AgentSpec project:

```text
Use AgentSpec to continue this repository. Read AGENTS.md, run project status,
pick the next ready task pack, follow its allowed paths, run verification,
record review evidence, finish the task, and refresh roadmap/handoff state.
```

Use this for a new design or design change:

```text
Use AgentSpec to process this design update: <path-or-export>. Import it as a
candidate or DCR, diff it against the accepted source, summarize the impact,
and prepare the next task pack. Ask before promoting accepted source or
expanding implementation scope.
```

The agent should report:

- requirement IDs and DCR IDs involved
- generated or selected task context pack
- allowed paths and acceptance criteria
- verification commands and results
- review ID and verdict
- roadmap and handoff status

The sections below show the CLI commands behind those prompts. Humans can run
them directly, but the intended product experience is that an installed code
agent plugin runs them consistently.

## Bootstrap A Project

If you are driving the CLI directly, install it first:

```bash
pip install -e .
```

When prompted to initialize a new project, the code agent should run the same
kind of sequence in the target repository:

```bash
TARGET=/path/to/repo
aspec --root "$TARGET" init --mode greenfield --targets claude,codex
```

Create or place your Markdown design at:

```text
$TARGET/docs/source/design.md
```

Then it should ingest and compile:

```bash
aspec --root "$TARGET" ingest "$TARGET/docs/source/design.md"
aspec --root "$TARGET" compile
aspec --root "$TARGET" status
aspec --root "$TARGET" emit --target claude,codex
```

After this, the target repo has canonical source snapshots, generated specs,
requirements, discovery files, agent instructions, and the basic layout needed
for governed implementation.

## Start A Task

Pick an accepted requirement and create a context pack:

```bash
aspec --root "$TARGET" task create --requirement R-001
aspec --root "$TARGET" task next
```

Open the generated pack under `agent/context-packs/` before implementation.
Check these sections:

- `Requirements`: the requirement IDs the task is meant to satisfy.
- `Allowed Paths`: the only files the implementation may touch.
- `Acceptance Criteria`: the completion checks.
- `UNTRUSTED SOURCE CONTENT`: source excerpts for citation, not instructions.

If the allowed paths or criteria are wrong, revise the task before running work.
The code agent should pause and report these fields when the scope is ambiguous.

## Plan And Execute

Create a native workflow for the task:

```bash
aspec --root "$TARGET" plan --current
```

Start or continue execution:

```bash
aspec --root "$TARGET" run loop
aspec --root "$TARGET" run prompt <run-id>
```

For runner integrations:

```bash
aspec --root "$TARGET" run package --runner codex --json
aspec --root "$TARGET" run result <run-id> \
  --result-json '{"executor_output":"Done. Tests passed.","test_status":"passed"}' \
  --json
```

The controller owns durable state. Plugin skills and external agents are thin
adapters that read the task pack, do the bounded work, and report results back
to AgentSpec.

## Verify, Review, Finish

Run the verification commands appropriate to the task. For this repository, the
full default is:

```bash
python -m unittest discover -s tests -v
```

For docs-only work, this lighter set is usually enough:

```bash
python -m json.tool docs/traceability/requirements.yml >/dev/null
git diff --check
aspec maturity status
aspec roadmap --check --json
```

Record review evidence:

```bash
aspec --root "$TARGET" review code \
  --task T-001 \
  --verdict ready \
  --summary "No blocking findings."
```

Finish the task with review and verification evidence:

```bash
aspec --root "$TARGET" finish T-001 \
  --test-status passed \
  --review REVIEW-0001 \
  --reason "Completed R-001."
```

Refresh or check the roadmap:

```bash
aspec --root "$TARGET" roadmap
aspec --root "$TARGET" roadmap --check --json
```

## Handle Design Changes

Do not hand-edit accepted source snapshots to sneak in new scope. Use a DCR:

```bash
aspec --root "$TARGET" dcr create \
  --title "Short change title" \
  --classification implement-now
```

Update the generated DCR in `docs/change-requests/`, add or revise
requirements, then create a task context pack from the accepted requirement.

Use candidate source intake when the external source keeps changing:

```bash
aspec --root "$TARGET" intake import ./design-v2.md \
  --kind markdown \
  --source-key product-design \
  --classification internal \
  --storage-mode committed \
  --as-candidate \
  --json

aspec --root "$TARGET" intake diff SRC-0002 --baseline accepted --json
aspec --root "$TARGET" intake promote SRC-0002 --decision accepted --compile --json
```

## What To Commit

Commit durable project state:

- `AGENTS.md` and `CLAUDE.md`
- `.agentspec/config.yml`
- `docs/source/`, `docs/spec/`, `docs/discovery/`, `docs/traceability/`
- accepted DCRs and ADRs
- `agent/context-packs/`
- `agent/workflows/`
- `agent/reviews/`
- `agent/task-ledger.yml`
- `agent/handoff.yml`
- `docs/ROADMAP.md`
- source, tests, and fixtures created by the task

Keep local execution scratch out of normal commits unless the project explicitly
uses it as evidence:

- `agent/runs/*`
- temporary reports
- local tool configuration

## Daily Commands

```bash
aspec status --json          # current project state and next action
aspec lifecycle              # native lifecycle map
aspec task next              # next ready task pack
aspec next-action            # recovery or continuation command
aspec maturity status        # governance profile checks
aspec outcome                # product outcome gates
aspec roadmap --check --json # roadmap freshness
```

## Recovery

When you are unsure what to do next, run:

```bash
aspec status --json
aspec next-action
```

Read `agent/handoff.yml` for the last completed task, review ID, verification
status, and recommended next action.
