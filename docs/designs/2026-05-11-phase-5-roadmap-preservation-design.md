---
design_type: phase
created_at: 2026-05-11
parent_design: docs/source/src-0003-lifecycle-engine-hardening-design.md
originating_dcr: DCR-0064
requirement: R-199
branch: codex/phase5-roadmap-preservation
worktree: /Users/yimwu/Documents/workspace/Apps/agent-spec-engine-phase5-roadmap-preservation
---

# Phase 5: Roadmap Preservation Mode

## Intent Contract

intent: Add opt-in generated-block roadmap mode so AgentSpec can update its managed roadmap projection without overwriting human-authored roadmap content.

constraints:
- Full-file roadmap generation remains the default behavior.
- Generated-block mode uses the existing `docs/ROADMAP.md` path and existing `aspec roadmap` / `aspec roadmap --check` command surface.
- The generated projection remains deterministic and derived from existing handoff, task ledger, and requirement traceability artifacts.
- Manual content outside the managed block is preserved byte-for-byte except for normal file trailing-newline handling.
- No migration runs automatically; projects opt in through configuration.

success_criteria:
- A repo config flag enables generated-block roadmap mode.
- `aspec roadmap` creates or replaces only the managed block when generated-block mode is enabled.
- Manual content before and after the managed block survives repeated roadmap writes.
- `aspec roadmap --check` succeeds when the managed block is current.
- `aspec roadmap --check` fails when the managed block is missing or stale.
- Existing full-file roadmap tests and CLI behavior continue to pass.

risk_level: medium

## Verification Contract

verify_steps:
- run focused tests: `python -m unittest tests/test_roadmap_preservation.py tests/test_workflow_contract.py tests/test_cli_workflow.py -v`
- run related lifecycle tests: `python -m unittest tests/test_writeback.py tests/test_status_cli.py tests/test_finish_cli.py -v`
- run full suite: `python -m unittest discover -s tests -v`
- check formatting: `git diff --check`
- confirm AgentSpec status: `aspec status --json`
- confirm roadmap current: `aspec roadmap --check --json`

## Governance Contract

approval_gates:
- Phase design and executable plan are written before implementation.
- Code review evidence is recorded with `aspec review code` before task completion.
- `aspec task complete` links the ready review evidence.

rollback:
- Revert the Phase 5 commit from branch `codex/phase5-roadmap-preservation`.
- Because the mode is config-gated, disabling the config flag returns projects to full-file generation.
- No persisted schema migration is required.

ownership: AgentSpec maintainer and current code agent.

## Scope

| Area | In scope | Out of scope |
|---|---|---|
| Roadmap write mode | Add config-gated generated-block preservation mode | Make generated-block mode default |
| Roadmap check mode | Check only the managed block when preservation mode is enabled | Add semantic diff or partial repair commands |
| Manual content | Preserve content outside the managed block | Reformat or validate human-authored sections |
| CLI | Keep `aspec roadmap` and `aspec roadmap --check` stable | Add new public roadmap subcommands |
| Workflow discipline | Design doc, plan doc, AgentSpec task pack, worktree branch | Build a full HOTL runtime clone |

## Decisions

| # | Decision | Choice | Rejected alternatives |
|---|---|---|---|
| 1 | Default mode | Keep current full-file generation default | Switch all repos to generated-block mode immediately |
| 2 | Opt-in config | Read a roadmap mode flag from `.agentspec/config.yml` | Add a CLI-only flag that cannot be checked deterministically later |
| 3 | Managed block | Use stable begin/end markers around the generated projection | Split roadmap into separate generated and manual files |
| 4 | Missing block behavior | In preservation mode, write inserts the block; check fails until write runs | Silently pass check when the block is missing |
| 5 | Manual content | Preserve outside-block content and only normalize final newline | Re-render the whole file and attempt to merge headings |
| 6 | Risk level | Medium because roadmap write semantics change behind config | High because no security or data-destructive operation is involved |

## Surface

`agentspec/roadmap.py` remains the roadmap authority. The module should expose a small internal mode resolution boundary, keep `build_roadmap` as the deterministic generated projection, and route `write_roadmap` / `check_roadmap` through full-file or generated-block behavior based on config.

`agentspec/config.py` should define default roadmap config so callers can merge missing keys consistently. The expected shape is a nested roadmap config with a mode that defaults to full-file generation and accepts a generated-block value.

`agentspec/cli.py` should keep the existing command surface. Human-facing output can remain the same because the command target is still `docs/ROADMAP.md`; JSON output should remain compatible.

`tests/test_roadmap_preservation.py` should cover generated-block insertion, replacement, manual content preservation, missing-block check failure, stale-block check failure, and default full-file compatibility. Existing roadmap tests should continue to prove backward compatibility.

## Risks & Open Questions

Risks:
- Marker collisions are possible if a human writes the exact managed marker text. Mitigation: use explicit AgentSpec marker strings and tests for replacement behavior.
- Generated-block mode may leave stale manual prose around a current generated block. Mitigation: that is intentional; AgentSpec owns only the marked block.
- Config drift can make teams unsure which mode is active. Mitigation: default remains full-file, and check/write use the same config resolution path.

Open questions:
- Should generated-block mode become the default after dogfooding?
- Should future roadmap preservation support multiple generated blocks?
- Should `aspec roadmap --check --json` report the active mode explicitly?
