# DCR-0026: External spec intake and candidate snapshots

| Field | Value |
|---|---|
| Status | accepted |
| Classification | needs-adr |
| Submitted | 2026-05-01 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-01 |
| Confidence | medium |

## Summary

Introduce an External Spec Intake lane so AgentSpec can safely ingest design
updates from changing external sources such as Confluence pages, exported PDFs,
HTML docs, YAML files, OpenAPI specs, or fixed URLs before those updates alter
the repository's accepted spec baseline.

The core change is to separate three concepts that are currently blurred by
`aspec ingest`: a logical external source, an immutable fetched snapshot, and
the accepted repo-local spec projection. Automation may fetch, normalize,
validate, and diff candidate snapshots, but promotion into `docs/source/`,
`docs/spec/`, requirements, plans, ADRs, or context packs requires human
approval. Policy-based auto-promotion is intentionally out of scope for this
DCR.

## Motivation

Users often keep the product source of truth outside the code repository. A
single Confluence page may be refined over weeks; a design may move from PDF to
HTML; an API contract may be a YAML/OpenAPI file; V1 and V2 may live at
different URLs; or a stable URL may keep serving a newer document version.

The current MVP supports local Markdown/text ingest and records content hashes,
but it treats ingest as direct canonical-source mutation:

- `aspec ingest <path>` writes into `docs/source/`, records one source entry,
  and replaces sections for that source id.
- `aspec compile` regenerates repo-local spec shards and requirements from
  whatever is already in `docs/source/sections.yml`.
- There is no candidate snapshot state, no reviewable external-source diff,
  no promotion command, and no connector boundary for Confluence/PDF/HTML/YAML.

This leaves two unsafe extremes:

- A user or agent re-ingests the latest external design and silently changes
  the repo-local spec baseline.
- A user avoids re-ingest, so AgentSpec runs from stale snapshots even when the
  external source of truth has evolved.

AgentSpec needs an explicit intake lane between "external document changed" and
"accepted repo spec changed".

## Proposed Change

Add a new intake subsystem with a candidate-first state model.

### Product Rule

External sources are evidence, not the accepted spec. The accepted repo-local
spec is only the material that has passed promotion into the AgentSpec
workspace.

### Source Model

Introduce these logical layers:

- **Source identity**: a stable logical source key, such as
  `payments-design`, independent from any one URL or export path.
- **Remote locator**: where content came from for this fetch, such as
  `confluence://SPACE/page-id`, `https://.../design.html`,
  `/tmp/export.pdf`, or `/tmp/openapi.yaml`.
- **Snapshot**: an immutable normalized capture with `snapshot_id`,
  `source_key`, `remote_uri`, `remote_version`, `content_hash`,
  `normalized_hash`, `fetched_at`, `classification`, `storage_mode`, and
  `state`.
- **Accepted baseline**: the set of promoted snapshots used by `aspec compile`
  to generate `docs/spec/`, requirements, questions, plans, and context packs.
- **Candidate**: a snapshot that can be inspected and diffed but does not feed
  `compile` until promoted.

Candidate files should not be written into `docs/source/sections.yml`, because
that file is currently treated as canonical compile input. Store candidates
under a separate namespace, for example:

```text
docs/source/candidates/
  SRC-0002/
    source.md
    spec-document.yml
    sections.yml
    validation.yml
    diff.yml
    intake-report.md
```

Accepted snapshots continue to appear in `docs/source/sources.yml` and
`docs/source/sections.yml`. Existing records without an explicit `state` are
treated as `accepted` for backward compatibility.

### SpecDocument Normalization

Add a structured intermediate representation:

```yaml
schema: agentspec.spec_document.v0
source_key: payments-design
snapshot_id: SRC-0002
kind: confluence | markdown | html | pdf | yaml | openapi
title: Payments API V2 Design
remote_uri: confluence://SPACE/page-id
remote_version: "42"
content_hash: sha256:...
normalized_hash: sha256:...
sections:
  - local_id: D-01
    stable_key: payments-api-v2/overview
    heading_path: ["Overview"]
    content_hash: sha256:...
    body_ref: source.md#L1-L40
requirements:
  - candidate_id: CAND-R-001
    text: The API must accept idempotency keys.
    source_sections: ["D-03"]
api_contracts:
  - method: POST
    path: /v2/payments
    schema_hash: sha256:...
open_questions: []
```

Normalizers are responsible for parsing source-specific syntax into this
shape. Early implementation should support file-based Markdown plus HTML/YAML
or OpenAPI. PDF and live Confluence can follow once the intake state machine is
working.

### Source Classification And Storage Modes

Intake uses the existing source classification enum:

- `public`
- `internal`
- `confidential`
- `restricted`

It also uses the storage-mode enum defined by the security/governance spec:

- `committed`
- `pointer-only`
- `local-secure-cache`
- `enterprise-object-store`

### Validation

Add schema validation before diffing or promotion:

- Required metadata is present: source key, kind, hash, fetched timestamp,
  classification, storage mode.
- Candidate sections have stable local IDs and content hashes.
- Restricted/confidential sources obey storage policy. For example,
  `pointer-only` may record URI/hash without committing full text.
- Retrieved source content is always treated as untrusted and delimited before
  entering task context packs.
- OpenAPI/YAML inputs pass structural validation before prose extraction.

Validation failures write `validation.yml` and return a structured CLI error.
They do not update the accepted baseline.

### Diff

Add a candidate diff against the current accepted baseline for the same
`source_key` or an explicitly selected baseline:

```bash
aspec intake diff SRC-0002 --baseline accepted --json
```

Diff output should classify changes at more than one level:

- source metadata changed: URL, remote version, classification, storage mode
- section changed: added, removed, renamed, moved, body changed
- requirement changed: added, removed, strengthened, weakened, superseded
- API contract changed: endpoint added/removed, method changed, path changed,
  request/response schema changed, auth scope changed, enum changed
- intake recommendation: doc-only, clarification, implement-now, defer, spike,
  needs-adr, reject, needs-review

The first implementation can use deterministic structural and hash-based diff.
Semantic recommendation can be conservative: when unsure, label as
`needs-review` and require human review.

### Intake Recommendation vs DCR Classification

The intake recommendation enum is a review aid, not a replacement for the
ADR-0002 DCR classification enum.

- `implement-now`, `defer`, `spike`, `needs-adr`, and `reject` map to the
  existing DCR classifications only when the operator deliberately creates or
  classifies a DCR.
- `doc-only` and `clarification` are intake-only outcomes that may update the
  accepted source/spec projection after human promotion, but do not produce a
  DCR unless implementation scope changes.
- `needs-review` is a non-terminal pending state and is never written to a
  DCR.

`aspec intake` may write an intake report with suggested DCR fields, but it
must not call `aspec dcr classify`, `aspec dcr accept`, or
`aspec requirement accept` during promotion.

### CLI Surface

Add an `intake` command group:

```bash
aspec intake import <path-or-uri> \
  --kind markdown|html|pdf|yaml|openapi|confluence \
  --source-key payments-design \
  --classification internal \
  --storage-mode committed \
  --as-candidate \
  --json

aspec intake validate SRC-0002 --json

aspec intake diff SRC-0002 --baseline accepted --json

aspec intake classify SRC-0002 \
  --recommendation doc-only|clarification|implement-now|defer|spike|needs-adr|reject \
  --json

aspec intake promote SRC-0002 \
  --decision accepted \
  --compile \
  --json
```

`--decision` accepts `accepted` only under this DCR. Candidate rejection is
handled by `aspec intake classify --recommendation reject`, which leaves the
candidate un-promoted. A future DCR may extend `--decision` to include
`superseded`.

Automation may run `import`, `validate`, and `diff`. `promote` requires a human
approval gate. Policy-based auto-promotion is out of scope for DCR-0026 and
would need a follow-up DCR or ADR.

Add an optional `source` command group later for persistent source registry:

```bash
aspec source add payments-design confluence://SPACE/page-id
aspec source list
aspec source status payments-design
```

### Promotion Semantics

Promotion converts a candidate into the accepted baseline:

1. Record the candidate as an accepted source snapshot.
2. Preserve prior accepted snapshots for audit; do not destroy old source
   files or hashes.
3. Update the canonical compile projection for the promoted source using an
   atomic filesystem boundary such as temp-file writes plus rename.
4. If `--compile` is set, run `aspec compile` after the accepted projection is
   updated; otherwise print the exact compile command for the operator.
5. Preserve DCR-originated and human-curated requirements per R-131/R-132
   during compile.
6. Write recommended follow-up DCR/ADR/task commands according to the intake
   recommendation. Do not auto-classify or auto-accept those artifacts.

Promotion should support at least these decisions:

- `doc-only`: update accepted snapshot/spec notes, no implementation pack.
- `clarification`: update accepted snapshot/spec and maybe strengthen existing
  requirements, with human review.
- `implement-now`: recommend a DCR with proposed requirements and task context
  packs.
- `needs-adr`: recommend a DCR plus ADR follow-up; no implementation pack
  until accepted.
- `defer`: record diff and backlog item only.
- `reject`: keep candidate record for audit but do not alter accepted baseline.

### Section Identity

This feature needs an ADR because section identity across repeated snapshots is
load-bearing. The ADR should decide how `D-*` references behave when the same
external source changes over time.

Recommended direction:

- Keep bare `D-*` IDs as a single-source compatibility path only.
- Once more than one accepted `source_key` exists, generated artifacts cite
  accepted sections as `source_key:D-*` to avoid collisions.
- Add snapshot-qualified IDs internally, for example `SRC-0002:D-03`, so old
  snapshots remain auditable even if the accepted projection now points at a
  newer body.
- Add `source_key`, `snapshot_id`, `stable_key`, and optional `supersedes` to
  section records.
- On promotion, map candidate sections to existing canonical section IDs when
  the stable key/heading lineage matches; create new canonical IDs for new
  concepts; mark removed concepts as superseded rather than deleting audit
  history.

### Implementation Slices

Recommended delivery sequence is defined canonically in ADR-0006's
Implementation Guidance. This DCR deliberately does not duplicate the sequence
so the ADR remains the single source for implementation ordering.

### HOTL Contracts

Intent:

```yaml
intent: Add a candidate-first external spec intake lane that lets AgentSpec
  ingest changing design sources without silently mutating the accepted repo
  spec.
constraints:
  - Accepted specs, requirements, ADRs, and context packs change only after
    promotion.
  - Candidate source content is untrusted and must not become instructions.
  - Existing `aspec ingest` / `aspec compile` behavior remains backward
    compatible for simple Markdown MVP users unless a future accepted DCR
    changes that contract.
success_criteria:
  - A changed external design can be imported, validated, diffed, reviewed,
    promoted, compiled, and turned into DCR/task work with traceable hashes.
risk_level: high
```

Verification:

```yaml
verify_steps:
  - run tests: python -m unittest discover -s tests -v
  - check: candidate import does not alter docs/source/sections.yml
  - check: promote updates accepted source projection and compile output
  - check: rejected candidates leave accepted requirements unchanged
  - check: old snapshots remain addressable by snapshot id and hash
  - confirm: DCR/ADR/task outputs cite source_key, snapshot_id, and requirement ids
```

Governance:

```yaml
approval_gates:
  - ADR-0006 accepted before implementation packs are created
  - human promotion required for candidate snapshots
  - needs-adr and implement-now recommendations produce DCR-governed work
rollback:
  - revert the promotion commit to restore prior accepted baseline
  - keep candidate snapshot records so the rejected or reverted source remains
    auditable
ownership:
  - coordinator owns intake workflow
  - spec-compiler owns normalization, validation, and compile integration
  - security-reviewer owns storage-mode and untrusted-content gates
```

## Impact Assessment

Affected existing requirements:

- `R-007`: CLI must support local/CI workflows; intake commands become a new
  local and automation surface.
- `R-010`: drift checking should expand from code-diff drift to source-diff
  and candidate-vs-baseline drift reports.
- `R-025`: snapshots must keep work auditable even when Confluence changes.
- `R-034`: brownfield/read-only behavior should remain safe; candidate import
  and diff can run without changing accepted code/spec.
- `R-035`: dogfood AgentSpec on its own repo; this DCR is an intake dogfood
  case.
- `R-096`: enterprise snapshot storage policy must be resolved before
  confidential/restricted source support is complete.
- `R-121`..`R-123`: post-implementation design changes must flow through DCRs
  before downstream artifacts change.
- `R-131`..`R-132`: compile must preserve DCR-originated material and fail
  loudly on unreconcilable conflicts.

Proposed new requirements:

- `R-147`: AgentSpec supports candidate source snapshots that can be imported
  and diffed without changing accepted compile inputs.
- `R-148`: AgentSpec normalizes supported external sources into a validated
  `SpecDocument` schema before diff or promotion.
- `R-149`: AgentSpec produces a reviewable diff between a candidate snapshot
  and the accepted baseline for the same source identity.
- `R-150`: AgentSpec requires human approval before a candidate snapshot is
  promoted into accepted repo spec artifacts. Policy-based auto-promotion is
  out of scope until a follow-up DCR or ADR defines the policy surface.
- `R-151`: Promotion preserves prior accepted snapshots and records lineage
  from source identity to snapshot to section to requirement/task.
- `R-152`: Intake supports storage modes for committed, pointer-only,
  local-secure-cache, and enterprise-object-store source material without
  leaking restricted content into prompts.
- `R-153`: Structured API sources such as YAML/OpenAPI produce structural
  contract diffs, not only prose diffs.
- `R-154`: Live enterprise connectors such as Confluence, Jira, SharePoint,
  Google Drive, GitHub Enterprise, and similar systems are adapters over the
  same candidate snapshot protocol rather than privileged compile inputs.

Likely code surface:

- `agentspec/cli.py`: `intake` and possibly `source` command groups.
- `agentspec/ingest.py`: keep backward-compatible MVP ingest; factor shared
  snapshot helpers where useful.
- `agentspec/compile.py`: compile only accepted projections; preserve
  DCR-originated material; report source-lineage conflicts.
- `agentspec/intake.py`: import, validate, diff, classify, promote workflow.
- `agentspec/spec_document.py`: schema, validation, and normalization helpers.
- `agentspec/source_registry.py`: optional persistent source identity registry.
- `agentspec/connectors/`: later Confluence/PDF/HTML/YAML/OpenAPI adapters.
- `agentspec/dcr.py`: optional helpers to generate DCRs from intake diff.
- `agentspec/paths.py` / `agentspec/io.py`: storage-mode and path helpers.

Likely artifact surface:

- `docs/source/candidates/**`
- `docs/source/source-registry.yml`
- `docs/source/source-lineage.yml`
- `docs/source/sources.yml`
- `docs/source/sections.yml`
- `docs/change-requests/**`
- `docs/adr/0006-external-spec-intake-protocol.md`
- `reports/traceability/**` or `reports/intake/**`

Likely tests:

- Candidate import leaves accepted compile inputs unchanged.
- Candidate diff detects unchanged, changed, added, removed, and moved
  sections.
- Candidate promotion updates accepted projection and runs compile.
- Rejected candidate leaves accepted baseline unchanged.
- DCR-originated requirements survive promotion compile.
- Pointer-only storage records URI/hash but does not commit body text.
- OpenAPI diff detects endpoint/path/schema/auth changes.

## Disposition

Classification: `needs-adr`.

Rationale:

- The change redefines canonical-source lifecycle semantics.
- It introduces candidate vs accepted state, source lineage, and section
  identity across snapshots.
- It changes how external source-of-truth documents become repo-local
  implementation work.
- It affects security/storage-mode policy for confidential and restricted
  enterprise documents.

Required follow-ups:

1. Draft and accept ADR-0006 for the external spec intake protocol, including
   section identity and promotion semantics.
2. After ADR acceptance, split implementation into small context packs:
   schema/validation, candidate import, diff, promotion, structured API diff,
   and enterprise connectors.
3. Do not implement live Confluence fetching until the file-based candidate
   protocol and promotion gate are verified.

## Acceptance Criteria

- This DCR clearly separates external source, candidate snapshot, accepted
  baseline, and generated repo spec.
- The proposed CLI flow supports agent/automation running import + validation
  + diff while preserving human/policy control over promotion.
- The design covers fixed URL changes, changing URLs for the same source,
  V1/V2 baselines, increasingly detailed docs, PDF/HTML/YAML/OpenAPI sources,
  and future Confluence connectors.
- The impact assessment names affected existing requirements and proposes new
  requirements for implementation planning.
- The disposition requires an ADR before implementation because section
  identity and promotion semantics are architectural.
