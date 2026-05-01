# DCR-0027: Source registry and scheduled drift checks

| Field | Value |
|---|---|
| Status | classified |
| Classification | needs-adr |
| Submitted | 2026-05-01 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-01 |
| Confidence | medium |

## Summary

Add a source registry and scheduled read-only drift checks on top of the
DCR-0026 candidate intake model. The registry records logical source keys,
remote locators, connector kind, classification, storage mode, last accepted
snapshot, and optional polling policy. Drift checks re-fetch registered sources,
compare hashes, and create reviewable candidate snapshots or reports without
promoting anything automatically.

This is the next step after candidate-first intake: DCR-0026 made manual
external-source updates safe; DCR-0027 proposes the control plane that tells a
team when a registered source has changed.

## Motivation

Users may keep the durable product source of truth in Confluence, Google Drive,
GitHub Enterprise, exported PDFs, fixed OpenAPI URLs, or other systems outside
the code repository. DCR-0026 lets an operator manually import a fresh export,
diff it, and promote it after review. That solves safety, but it does not solve
discoverability:

- A stable Confluence URL may change without anyone remembering to run
  `aspec intake import`.
- V1 and V2 design docs may move across URLs while keeping the same logical
  source identity.
- A CI or local audit may want to know that the external source hash differs
  from the last accepted repo snapshot, but must not mutate accepted specs.
- Teams need a durable registry so code agents and scheduled jobs know which
  sources are intentional, which connector kind to use, and what storage policy
  applies.

Without this registry, users must carry source location and polling knowledge in
chat history or tribal process. That weakens AgentSpec's goal of durable,
agent-ready repository context.

## Proposed Change

Introduce a registry-backed source monitoring lane.

### Source Registry

Add `docs/source/source-registry.yml` with records such as:

```json
[
  {
    "source_key": "payments-design",
    "kind": "confluence",
    "remote_uri": "confluence://PAY/pages/12345",
    "classification": "internal",
    "storage_mode": "committed",
    "accepted_snapshot_id": "SRC-0002",
    "last_seen_remote_version": "42",
    "last_seen_content_hash": "sha256:...",
    "poll": {
      "enabled": true,
      "cadence": "daily"
    }
  }
]
```

The registry is the durable repo-local declaration of external sources to
watch. It is not the accepted source body and does not replace
`docs/source/sources.yml`; it points at the latest accepted baseline and remote
locator for re-fetch checks.

### CLI Surface

Candidate commands:

```bash
aspec source add <source-key> <remote-uri> \
  --kind confluence|openapi|markdown|html|pdf|yaml \
  --classification internal \
  --storage-mode committed

aspec source list --json

aspec source check <source-key> --json

aspec source check --all --json
```

`source check` should be read-only with respect to accepted source/spec
artifacts. If a remote hash differs from the registered accepted hash, it may
write a candidate snapshot under `docs/source/candidates/` and an intake/drift
report, but it must not update `docs/source/sources.yml`,
`docs/source/sections.yml`, `docs/spec/**`, requirements, ADRs, or context
packs.

### Scheduled Drift Checks

Add a CI-friendly command or emitted workflow that can run:

```bash
aspec source check --all --json
```

The command should return structured results:

- unchanged source
- changed source with candidate snapshot id
- connector failure with retryability and source key
- policy failure, such as restricted content with an unsafe storage mode

The initial scheduler can be a generated GitHub Actions workflow or a documented
CLI command for external schedulers. The key product rule is that scheduled
checks are read-only audits until a human promotes a candidate.

## Impact Assessment

Affected existing requirements:

- `R-001`: task context must cite durable source identity rather than hidden
  chat history.
- `R-007`: CLI must support local and CI workflows.
- `R-010`: drift checks expand from code diff to external source drift.
- `R-013`: scheduled read-only audits become more concrete.
- `R-025`: source snapshots must keep work auditable when Confluence changes.
- `R-034`: brownfield/read-only behavior should remain safe.
- `R-147`..`R-154`: DCR-0026 candidate intake, promotion, storage policy,
  structured API diff, and connector-adapter contracts become prerequisites.

Likely new requirements:

- `R-155`: AgentSpec stores a source registry for logical external source
  identities, remote locators, connector kind, classification, storage mode,
  and last accepted snapshot metadata.
- `R-156`: AgentSpec can run a read-only source drift check for one registered
  source or all registered sources without mutating accepted compile inputs.
- `R-157`: When a registered source changed, AgentSpec creates or references a
  candidate snapshot and emits a structured drift result.
- `R-158`: Scheduled source drift checks can run in CI and report changed,
  unchanged, failed, and policy-blocked sources.

Likely affected modules:

- `agentspec/source_registry.py`: registry schema, load/save, validation.
- `agentspec/connectors/`: fetch providers reused by source checks.
- `agentspec/intake.py`: shared candidate creation from fetched source bytes.
- `agentspec/cli.py`: `aspec source ...` command group.
- `agentspec/emit.py`: optional scheduled workflow emission.
- `tests/test_source_registry.py` and `tests/test_source_drift.py`.

## Disposition

Recommended classification: `needs-adr`.

This needs an ADR before implementation because it introduces a new durable
registry artifact, a scheduled automation surface, and a subtle boundary
between "read-only audit may create candidate evidence" and "accepted baseline
must not change." The ADR should pin:

- whether `source check` may write candidates by default or only with an
  explicit flag;
- the registry schema and relationship to `docs/source/sources.yml`;
- whether scheduled checks are emitted by AgentSpec or only documented;
- retry/error semantics for connector failures;
- whether changed-source results should auto-create DCR stubs, intake reports,
  or neither.

## Acceptance Criteria

- ADR-0007 or equivalent is accepted before implementation starts.
- A source registry artifact exists with schema validation and examples.
- `aspec source add/list/check` or equivalent CLI commands exist.
- `source check` compares registered source hashes against the accepted
  snapshot metadata without mutating accepted source/spec/requirements.
- Changed sources produce structured JSON and human-readable output pointing to
  a candidate snapshot or next import command.
- Connector failures return structured CLI errors and leave accepted artifacts
  unchanged.
- A scheduled audit path is documented or emitted, and it uses the read-only
  check path rather than promotion.
