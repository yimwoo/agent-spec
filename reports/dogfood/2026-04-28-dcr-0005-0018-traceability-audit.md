# DCR-0005..DCR-0018 Traceability Audit

Date: 2026-04-28
Authored by: continuous Claude pilot, in coordination with yimwu
Originating context pack: `agent/context-packs/T-039-dcr-0005-0018-traceability-audit.md`

## Summary

Audit of 14 accepted DCRs (DCR-0005 through DCR-0018) that, per the
post-T-033 consolidation pass, shipped without filing any new
requirements. The question this audit answers: is that correct, or do
some of them owe a backfilled requirement record?

**Verdict: zero backfills needed.** All 14 DCRs are tactical
implementations, refinements, or ergonomics knobs over already-accepted
requirements (predominantly R-003, R-006, R-007, R-127, R-129). Each
DCR's own "Impact Assessment" section already names the existing R-IDs
it strengthens, so the traceability link is captured at the DCR level
even though `requirements.yml` records no `originating_dcr` for those
fourteen.

## Verifiable state at audit time

`requirements.yml` `originating_dcr` distribution (run
`python -c "import json; from collections import Counter;
print(sorted(Counter(r.get('originating_dcr','none') for r in
json.load(open('docs/traceability/requirements.yml'))).items()))"`):

- `none` (pre-DCR-protocol): 120 — original src-0001 ingestion
- `DCR-0001`: 4 — R-127..R-130 (supervised-run protocol)
- `DCR-0002`: 6 — R-121..R-124 (DCR schema) + others
- `DCR-0003`: 2 — compile-merge preservation
- `DCR-0004`: 2 — R-131, R-132 (DCR cascade semantics)
- `DCR-0019`: 10 — R-135..R-144 (autonomous + research mode)

Total accepted: 144. PPA: 0.

## Per-DCR verdicts

Format: `verdict — strengthens — rationale`.

| DCR | Title | Verdict | Strengthens | Rationale |
|---|---|---|---|---|
| 0005 | Add aspec CLI alias | (a) no new req | R-006, R-007 | Pure ergonomics. Adds a console-script alias over the existing CLI. R-007 (local/CI CLI) is the right home; no new product surface. |
| 0006 | Agent model profile config | (a) no new req | R-127, R-129, R-007 | Implements the model-profile shape ADR-0003 already specifies. Configuration defaults, no new behavioral claim. |
| 0007 | Task queue + next | (a) no new req | R-003, R-007, R-127 | Borderline candidate (new CLI surface), but `aspec task list/next` is the operational expression of "context-pack templates" (R-003) and "local CLI" (R-007). No fresh product claim. |
| 0008 | Supervised run loop MVP | (a) no new req | R-003, R-007, R-127, R-129 | Direct implementation of ADR-0003 protocol. R-127/R-129 are the load-bearing reqs; this DCR ships them. |
| 0009 | Task completion backfill | (a) no new req | R-003, R-007, R-127 | Operational command for queue hygiene. No new acceptance criterion beyond "supervised-run state is the source of truth" (R-127). |
| 0010 | Committed task ledger | (a) no new req | R-003, R-007, R-127 | Borderline candidate (new durable artifact `agent/task-ledger.yml`), but the artifact is a status projection of supervised-run state (R-127), not a fresh contract. No backfill needed. |
| 0011 | Review findings + status hygiene | (a) no new req | R-007, R-127 | Cleanup and doc-refresh slice. No product surface added. |
| 0012 | Model-backed continuation reviewer MVP | (a) no new req | R-007, R-127, R-129 | Implements R-129's reviewer branch with model fallback. Protocol surface defined by ADR-0003; no new req. |
| 0013 | Next executor prompt handoff | (a) no new req | R-007, R-127, R-129 | Read-only `aspec run prompt` derived from existing run state. No new behavior. |
| 0014 | Harness step command | (a) no new req | R-007, R-127, R-129 | Wraps `run loop` + `run prompt` for harness consumers. Shape over existing primitives. |
| 0015 | Runner package adapter | (a) no new req | R-007, R-127, R-129 | Borderline candidate (new runner protocol layer), but the package envelope is a presentation contract over R-127/R-129 state. The adapter does not execute; no new product claim. |
| 0016 | Runner result ingestion | (a) no new req | R-007, R-127, R-129 | Closes the package/result handshake. Schema validation over existing surface; no new req. |
| 0017 | Local runner demo e2e | (a) no new req | R-007, R-127, R-129 | Deterministic fixture proving the package/result flow. Test/demo scaffolding is not a product surface. |
| 0018 | Local subprocess runner | (a) no new req | R-007, R-127, R-129 | Concrete subprocess adapter for the existing runner protocol. Reuses `submit_runner_result`; no new contract. |

**Counts:** 14 (a) "no new requirement needed", 0 (b) "backfill needed".

## Borderline cases reviewed

Three DCRs were close enough to the line that I want the rationale on
record:

- **DCR-0007 (`aspec task list/next`):** introduces a new top-level
  CLI verb (`task`) and a status-overlay rule. Folds under R-003
  (context-pack templates → context-pack progress) and R-007 (local
  CLI). Filing a fresh "task queue" requirement now would be retro-
  fitting; the behavior is already covered by the broader requirements
  the DCR cites.
- **DCR-0010 (`agent/task-ledger.yml`):** introduces a durable
  committed artifact. It's a status projection over supervised-run
  state (R-127) rather than a new product claim. Future drift checks
  can assert ledger correctness against R-127 without needing a
  dedicated requirement.
- **DCR-0015 (runner package adapter):** introduces a runner-protocol
  layer. The adapter is presentation, not new behavior; it carries
  R-127/R-129 state into a runner-consumable shape. No new req.

If, in a later session, drift reviewers find the absence of a
dedicated R-ID makes one of these borderline cases ambiguous, the
remedy is a new DCR that proposes the missing requirement and lets the
human accept it explicitly. That is the same lane every other DCR has
gone through; this audit does not preempt it.

## Follow-ups

- None blocking.
- Optional polish: update each of the 14 DCR files with a one-line
  "Audit (T-039): no new requirement needed; see report" pointer.
  Skipped for now — touching 14 accepted DCR files for a one-line
  pointer is more churn than the audit decision warrants. The report
  itself is durable and discoverable via `reports/dogfood/`.

## Verification

- `python -m pytest -q -p no:cacheprovider` — 173/173 pass.
- `python -m agentspec.cli compile` — idempotent on the live repo.
- `requirements.yml` originating_dcr distribution unchanged (no
  backfill written).
