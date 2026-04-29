# DCR-0023: Globstar path matching for policy and drift

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-29 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-29 |
| Confidence | medium |

## Summary

Fix path-pattern semantics shared by policy enforcement and drift analysis.
Generated non-self-host context packs use patterns such as `src/**/*.py`;
those should match files directly under `src/` as well as nested files, while
single-star patterns such as `src/*.py` should not traverse subdirectories.

This DCR introduces one implementation requirement, `R-145`, and a small
shared matcher so the two enforcement surfaces cannot drift apart again.

## Motivation

`agentspec/archetype.py` emits recursive extension patterns like
`src/**/*.{py,ts,go,...}` for target inference. Today the policy gate and
drift checker disagree with standard globstar behavior:

- `agentspec/policy.py` uses `fnmatch`, so `src/**/*.py` misses `src/foo.py`
  and `src/*.py` over-matches `src/sub/bar.py`.
- `agentspec/drift.py` hand-rolls prefix matching, so `src/**/*.py` matches
  nothing.

This affects generated AgentSpec workspaces for TypeScript, Go, Java, Ruby,
Rust, and future adopters, especially autonomous allowed-path enforcement and
spec-drift impact mapping.

## Proposed Change

- Add a dependency-free shared helper for AgentSpec path-pattern matching.
- Treat `**` as "zero or more path segments."
- Treat `*` as "within one path segment" and never as a `/` traversal.
- Preserve the existing `src/**` directory-tree behavior.
- Replace both `policy._is_allowed` and `drift._path_matches` with the shared
  helper.
- Add focused tests that exercise the generated `src/**/*.py` shape.

## Impact Assessment

- New requirement: `R-145`.
- Existing requirements strengthened: `R-010` (drift), `R-127` and `R-135`
  (allowed-path policy), `R-136`/`R-137` (archetype-inferred pattern scope).
- Code surface: `agentspec/paths.py`, `agentspec/policy.py`,
  `agentspec/drift.py`.
- Test surface: new `tests/test_glob_semantics.py`.

## Disposition

Classification: `implement-now`.

This is a confirmed correctness defect in safety and review surfaces. No ADR
is required because the intended behavior matches existing generated pattern
shape and common globstar semantics.

## Acceptance Criteria

- `src/foo.py` matches `src/**/*.py`.
- `src/sub/bar.py` matches `src/**/*.py`.
- `src/sub/bar.py` does not match `src/*.py`.
- `src/foo.py` matches `src/*.py`.
- Existing `src/**` tree matching still works.
- Policy and drift both call the same shared matcher helper.
- Tests cover both policy allowed-path decisions and drift path matching.
