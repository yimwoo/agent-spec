# ADR-0004: Autonomous Execution Profile

Status: accepted
Date: 2026-04-28
Related: `ADR-0003-supervised-run-protocol.md`,
`DCR-0019-agentracing-dogfood-learnings-and-autonomous-mode.md`,
`R-135` through `R-141`
Builds on: ADR-0003 (supervised run protocol)

## Context

ADR-0003 defined the supervised run protocol: an executor produces work, a
collector records evidence, a reviewer/controller emits one of four verdicts
(`auto_continue`, `pause_for_human`, `halt`, `complete`), and a deterministic
policy gate can downgrade or override that verdict. The default flow has a
human in the inner loop on every `pause_for_human`.

The `agentracing` dogfood run (DCR-0019) demonstrated that the human-in-loop
default is the right behavior for design-shaping pauses but slows down
otherwise-bounded work. The user requested an explicit **no-human-gate
execution mode** for recurring, fully autonomous contribution loops.

Two failure modes must be avoided:

- A "YOLO" run that silently makes architecture, security, or scope decisions
  without producing an artifact for human review.
- A run that halts on every minor uncertainty and never makes progress.

ADR-0004 picks a deliberate middle: autonomous mode keeps every hard policy
gate; transforms `pause_for_human` from "wait for input" into "log a durable
finding and stop"; and never auto-accepts DCRs, ADRs, or requirements.

## Decision

Add an **execution profile** to the supervised run protocol with two named
modes:

- `supervised` (current default) — `pause_for_human` blocks the run until a
  human responds.
- `autonomous` — `pause_for_human` is converted into a structured **blocked
  finding** (open question, DCR stub, or pause record) and the run halts.

The mode is a property of a single supervised run, not a global toggle. It is
selected when the run is started:

```bash
aspec run start <pack> --mode supervised   # default
aspec run start <pack> --mode autonomous
aspec run loop --mode autonomous
```

The repository config (per ADR-0003 model profiles) MAY also set
`supervised_runs.default_mode` for a project that wants autonomous as the
default. The default of the default is `supervised`.

`yolo` is allowed as a profile alias for `autonomous` only when the safety
contract below is unchanged. AgentSpec MUST NOT introduce a "yolo" mode that
weakens any limit in this ADR.

## Pause-Handling Transformation

In `autonomous` mode, the controller MUST NOT block on a `pause_for_human`
verdict. Instead, the controller decides between:

| Trigger | Action |
|---|---|
| Reviewer asks the human to pick among tasks or decide priority | record blocked finding (open question), `halt` the run, leave PPA requirements untouched |
| Reviewer asks for a product, architecture, or risk decision | record blocked finding (DCR stub draft under `docs/change-requests/` or `docs/discovery/open-questions.yml`), `halt` |
| Reviewer asks for credentials | always `halt`; never log the credential request as a recoverable artifact |
| Reviewer asks for scope expansion | `halt`; require a follow-up context pack with the expanded scope |
| Reviewer asks "should I continue with the active pack?" | controller answers the same way ADR-0003 prescribes (auto-continue if active pack is unambiguous), unchanged from supervised mode |

The controller MUST NOT invent product, architecture, security, or scope
answers in autonomous mode. Every blocked finding becomes a durable artifact
the human can review later.

## Hard Limits (always enforced, both modes)

These limits are part of the protocol and cannot be relaxed by any profile,
flag, or repository config:

1. **Allowed-paths only.** Writes are confined to the active context pack's
   `Allowed Paths`. Path violations halt the run.
2. **No destructive git.** No `--force` push, no `reset --hard` on shared
   branches, no `branch -D`, no `clean -f`, no `--no-verify`, no
   `--no-gpg-sign` unless the repository config explicitly opts in via a
   reviewed flag.
3. **No remote pushes.** The runner does not push to a remote unless
   `supervised_runs.allow_remote_push: true` is set in repo config AND the
   active context pack opts in. Default is local-only.
4. **No credential exfiltration.** Run state, blocked findings, and audit
   logs MUST NOT contain API keys, tokens, or other secrets. Credential
   resolution remains a runtime concern of the local adapter (per ADR-0003).
5. **Iteration cap.** ADR-0003's `max_iterations` applies. Hitting the cap
   in autonomous mode produces a `halt` with a "cap-exceeded" blocked
   finding rather than `pause_for_human`.
6. **Required-tests gate.** If the context pack lists tests, those tests
   must pass before `complete` can be emitted, in either mode.
7. **No artifact auto-acceptance.** Autonomous mode MUST NOT call
   `aspec dcr accept`, `aspec requirement accept`, or otherwise change
   the status of a DCR / ADR / requirement. Acceptance remains a
   deliberate human action, per ADR-0003.

## Soft Limits (mode-configurable)

These are policy decisions a repository may tune; defaults are conservative.

| Setting | Default | Notes |
|---|---|---|
| `supervised_runs.default_mode` | `supervised` | repo-wide default |
| `autonomous_mode.findings_dir` | `docs/discovery/open-questions.yml` for low-risk findings; `docs/change-requests/` for product/architecture findings | controller decides which artifact based on finding severity |
| `autonomous_mode.allow_remote_push` | `false` | belt-and-braces with the hard limit above |
| `autonomous_mode.max_consecutive_blocks` | `3` | if the loop produces N blocked findings without progress, the loop halts even before `max_iterations` |

## Audit Requirements

An autonomous run produces, at minimum:

- `agent/runs/<run-id>/events.jsonl` — per ADR-0003
- `agent/runs/<run-id>/summary.yml` — committed projection (mode, verdict
  counts, blocked findings, terminal status)
- One artifact per blocked finding: an open-question entry with
  `raised_by: <run-id>` or a DCR stub under `docs/change-requests/`

Every autonomous run that ends in `halt` due to a blocked finding MUST cite
the artifact id (Q-XXX or DCR-NNNN) it produced.

## Deferred Decisions

Q-020 (newly recorded) — Should autonomous mode operate strictly
one-pack-per-invocation, or may a single autonomous loop run drain the entire
ready queue (`aspec task next` until none) within one session? The MVP
chooses **one pack per invocation**. Multi-pack drains require an explicit
follow-up DCR.

The dogfood-learning capture mechanism (DCR-0019 finding #3) is also
deferred: it can be `reports/dogfood/` notes, an `aspec dogfood record`
subcommand, or both. The choice does not gate this ADR.

## Relationship to ADR-0003

ADR-0004 does not change ADR-0003's verdict schema, run-state layout,
iteration-cap definitions, or model-profile structure. It adds:

- a new `mode` field on run state (`supervised` | `autonomous`)
- a new transformation rule for `pause_for_human` when `mode == autonomous`
- the soft-limits table above
- the hard limits restated for emphasis

ADR-0003's `auto_continue / pause_for_human / halt / complete` verdict shape
remains the source of truth.

## Consequences

### Positive

- Recurring contribution loops can run unattended without weakening review.
- Every uncertainty produces a durable artifact a human can triage later.
- The "YOLO" naming is owned by AgentSpec rather than the agent ad-hoc.
- Hard limits are written down once and apply to both modes — easier to
  review, easier to test.

### Negative / Costs

- Autonomous runs may halt frequently in early iterations until target
  inference (R-135), allowed-path validation (R-137), and similar
  prerequisites mature.
- The blocked-finding signal can become noisy if the reviewer is too eager
  to escalate.
- Repositories that adopt autonomous-as-default need disciplined human
  triage of `docs/discovery/open-questions.yml` and `docs/change-requests/`.

### Neutral

- Autonomous mode does not weaken acceptance discipline. ADR-0003's "no
  auto-accept" rule continues; humans still flip DCRs and requirements.
- Autonomous mode does not turn AgentSpec into a general-purpose agent.
  The context pack remains the unit of work.

## Implementation Guidance

The first implementation pack should add:

- `agentspec/run.py` — accept a `mode` field on run state; switch
  `pause_for_human` handling based on mode.
- `agentspec/policy.py` — encode the hard limits as deterministic gates,
  not as advisory checks.
- `agentspec/cli.py` — `--mode` flag on `run start | run loop`.
- `agentspec/init.py` — write the new soft-limit defaults into
  `.agentspec/config.yml`.
- Tests in `tests/test_supervised_run.py` and a new
  `tests/test_autonomous_mode.py` covering all hard limits and the
  pause-to-finding transformation.

The autonomous mode MUST NOT ship before:

- R-136 (repository-aware target inference) and R-137 (allowed-path
  validation) are in `accepted` status. Without those, an autonomous run on
  a non-AgentSpec repo could write to the wrong paths even within the
  protocol.

## Status of this ADR

Accepted on 2026-04-28 by yimwu after the `agentracing` dogfood run captured
in DCR-0019. Implementation requirements R-135 through R-141 are recorded
with status `proposed-pending-acceptance` and require verified
implementation packs before promotion.
