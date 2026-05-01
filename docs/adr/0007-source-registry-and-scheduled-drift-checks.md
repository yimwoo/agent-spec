# ADR-0007: Source Registry and Scheduled Source Drift Checks

Status: accepted
Date: 2026-05-01
Related: `DCR-0027-source-registry-and-scheduled-drift-checks.md`,
`ADR-0006-external-spec-intake-protocol.md`,
`ADR-0002-design-change-protocol.md`, `R-007`, `R-010`, `R-013`,
`R-025`, `R-034`, `R-147`, `R-148`, `R-149`, `R-150`, `R-151`,
`R-152`, `R-153`, `R-154`
Builds on: ADR-0006
Supersedes: none

## Context

ADR-0006 made external source updates safe by introducing candidate
snapshots, validation, diff, and human-gated promotion. That protocol still
requires an operator to remember which external sources exist and when to
fetch them again.

Teams often keep the durable source of truth outside the repository:
Confluence pages, Google Drive exports, GitHub Enterprise files, OpenAPI URLs,
PDFs, HTML pages, or YAML contracts. Those sources may change in place, move
between URLs, or split into V1/V2 documents while still representing one
logical product source.

AgentSpec needs a repo-local control plane for these external source
identities. The control plane must support local and CI checks, but it must
not make live external documents into privileged compile inputs.

## Decision

AgentSpec will add a **Source Registry** and **read-only source drift check**
lane on top of ADR-0006.

### 1. Registry records source identity, not source authority

`docs/source/source-registry.yml` is the durable declaration of external
sources AgentSpec should know how to re-check. It does not replace
`docs/source/sources.yml` and it is not an accepted source body.

The registry stores records under schema `agentspec.source_registry.v0`:

```yaml
schema: agentspec.source_registry.v0
sources:
  - source_key: payments-design
    kind: confluence
    remote_uri: ./confluence-page.json
    classification: internal
    storage_mode: committed
    accepted_snapshot_id: SRC-0002
    last_seen_remote_version: "42"
    last_seen_content_hash: sha256:...
    poll:
      enabled: true
      cadence: daily
```

For backwards compatibility with the DCR-0027 sketch, the first
implementation may read a bare list of records, but writes must normalize to
the object form above.

### 2. `source_key` is globally unique per repository

Registry `source_key` values are globally unique in one AgentSpec workspace.
When a URL moves, `aspec source add <source-key> <remote-uri>` updates the
existing registry record instead of creating a second logical source.

If the team intentionally wants V1 and V2 to behave as distinct design
baselines, they must register separate source keys, such as
`payments-design-v1` and `payments-design-v2`.

### 3. Registry baseline metadata points to accepted snapshots

A registry record may name:

- `accepted_snapshot_id`: the latest accepted snapshot for this logical
  source.
- `last_seen_content_hash`: the accepted or last audited content hash used as
  the comparison baseline.
- `last_seen_remote_version`: optional remote version metadata, such as a
  Confluence version, ETag, commit SHA, or API contract version.

When a record omits these fields, `source check` looks up the accepted source
for the same `source_key` in `docs/source/sources.yml`. If neither registry
metadata nor an accepted source exists, the check reports the source as
`changed` with `baseline_content_hash: null` and points the operator at the
candidate import path.

### 4. `source check` is read-only by default

`aspec source check` fetches the registered source through the same connector
and intake adapters used by ADR-0006, computes the current content hash, and
compares it with the registry or accepted snapshot baseline.

By default, `source check` must not write:

- `docs/source/sources.yml`
- `docs/source/sections.yml`
- `docs/spec/**`
- `docs/traceability/requirements.yml`
- `docs/adr/**`
- `docs/change-requests/**`
- `agent/context-packs/**`

The default result is a structured report only.

### 5. Candidate evidence requires an explicit flag

If a registered source changed, `source check --as-candidate` may write a
candidate snapshot under `docs/source/candidates/` by calling the ADR-0006
intake path. This is evidence only. It does not promote the snapshot, update
accepted projections, classify DCRs, accept requirements, or create context
packs.

Without `--as-candidate`, changed results include the next command needed to
write candidate evidence.

### 6. No automatic DCR or requirement creation

Changed-source results may include recommended next commands, such as:

```bash
aspec source check payments-design --as-candidate --json
aspec intake diff SRC-0002 --baseline accepted --json
```

They must not auto-create DCR stubs, ADR stubs, requirements, or tasks. This
preserves ADR-0002 and ADR-0006: intake feeds governance, it does not bypass
governance.

### 7. Failure and policy semantics are structured

`source check` returns one result per source with status:

- `unchanged`: fetched hash equals the baseline hash.
- `changed`: fetched hash differs from the baseline hash, or no baseline hash
  exists.
- `failed`: the connector or source reader could not fetch the source.
- `policy-blocked`: the registry record violates source classification or
  storage-mode policy before candidate evidence can be created.

Single-source checks exit non-zero for `failed` and `policy-blocked`.
`--all` checks emit every result and exit non-zero only if any result is
`failed` or `policy-blocked`. A changed source is a successful audit finding,
not an operational error.

### 8. Scheduler MVP is CLI-first

The first scheduler surface is the CI-safe command:

```bash
aspec source check --all --json
```

This can be called from GitHub Actions, cron, Buildkite, Jenkins, or another
external scheduler. Emitting a first-class workflow file is deferred to a
follow-up DCR unless implementation remains trivial after the CLI lands.

### 9. CLI contract

The source command group is:

```bash
aspec source add <source-key> <remote-uri> \
  --kind confluence|openapi|markdown|html|pdf|yaml \
  --classification public|internal|confidential|restricted \
  --storage-mode committed|pointer-only|local-secure-cache|enterprise-object-store \
  --poll-cadence daily

aspec source list --json

aspec source check <source-key> --json
aspec source check <source-key> --as-candidate --json
aspec source check --all --json
```

`source add` writes or updates only `docs/source/source-registry.yml`.
`source list` is read-only. `source check` is read-only unless
`--as-candidate` is provided, and even then accepted compile inputs remain
unchanged.

## Consequences

### Positive

- External source location knowledge becomes durable repo context rather than
  hidden chat history.
- Scheduled audits can detect Confluence/OpenAPI/PDF/HTML/YAML drift without
  mutating accepted implementation authority.
- Changed-source evidence flows into the same candidate-first protocol already
  reviewed under ADR-0006.
- Moving URLs and V1/V2 source splits have explicit source-key semantics.

### Negative / Costs

- AgentSpec gains another state artifact that must be validated and preserved.
- `source check` now has to distinguish product drift from operational
  failures.
- Registry records may become stale if operators promote a candidate but do
  not update registry baseline metadata. A future promotion enhancement should
  update matching registry records after human approval.

### Neutral

- `aspec ingest` remains unchanged.
- Candidate promotion remains human-gated.
- Workflow emission for scheduled audits is intentionally deferred; the CLI is
  sufficient for CI in the MVP.

## Implementation Guidance

Recommended implementation slices:

1. Register R-155..R-158 with status `proposed-pending-acceptance`, citing
   DCR-0027 and ADR-0007.
2. Add `agentspec/source_registry.py` for schema validation, add/list, and
   check result construction.
3. Add `aspec source add/list/check` to `agentspec/cli.py`.
4. Reuse ADR-0006 intake helpers for explicit `--as-candidate` writes.
5. Document the scheduled audit command in README.
6. Test registry schema validation, default read-only checks, candidate writes
   behind `--as-candidate`, connector failures, policy-blocked records, and
   `--all --json` CI output.

Each implementation pack must cite DCR-0027, ADR-0007, and the requirement IDs
introduced from this ADR.

## Status of this ADR

Accepted on 2026-05-01 by yimwu, drafted during the DCR-0027 source-registry
implementation kickoff.
