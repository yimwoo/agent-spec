# ADR-0006: External Spec Intake and Snapshot Promotion Protocol

Status: accepted
Date: 2026-05-01
Related: `DCR-0026-external-spec-intake-and-candidate-snapshots.md`,
`ADR-0002-design-change-protocol.md`, `R-007`, `R-010`, `R-025`,
`R-034`, `R-035`, `R-096`, `R-121`, `R-122`, `R-123`, `R-131`,
`R-132`
Supersedes: none

## Context

AgentSpec currently supports local Markdown/text ingestion through
`aspec ingest`, then derives repo-local spec artifacts through
`aspec compile`. That MVP works when the design source is a file the user
intentionally places in the repository, but it is too coarse for external
sources of truth that change over time.

Common user workflows include:

- A stable Confluence page whose body and remote version keep changing.
- A design that starts as a PDF, later becomes HTML, and eventually moves
  to a docs site.
- Separate V1 and V2 URLs that both describe valid product baselines.
- API contract YAML or OpenAPI files that should be diffed structurally,
  not only as prose.
- A repo-local spec that records what has been implemented, while the
  external source keeps getting refined ahead of implementation.

ADR-0002 already says post-snapshot design changes must not silently mutate
downstream artifacts. DCR-0026 extends that principle to external design
sources: fetching or parsing a new external document must not automatically
change the accepted repo spec, requirements, plans, ADRs, or context packs.

## Decision

AgentSpec will add an **External Spec Intake** protocol with a
candidate-first state model.

### 1. External sources are evidence, not accepted spec

External sources such as Confluence, PDF, HTML, YAML, OpenAPI, Google Docs, or
fixed URLs are treated as evidence. They become implementation authority only
after a candidate snapshot is reviewed and promoted into the repo-local
accepted baseline.

The accepted baseline is the set of snapshots that `aspec compile` is allowed
to use. Candidate snapshots are visible for review and diff, but they do not
feed compile.

### 2. Source identity is separate from locator

AgentSpec will distinguish:

- `source_key`: stable logical identity, such as `payments-design`.
- `remote_uri`: locator used for one fetch, such as
  `confluence://SPACE/page-id`, `https://example.test/spec.html`, or
  `/tmp/export.pdf`.
- `snapshot_id`: immutable capture id, such as `SRC-0002`.
- `remote_version`: optional external version, such as a Confluence version
  number, ETag, commit SHA, or OpenAPI version string.

This allows one logical source to move between URLs without becoming a new
product concept, and allows different URLs to represent different baselines
when the user wants that.

### 3. Intake normalizes into `SpecDocument`

Every intake adapter produces a structured intermediate document before diff
or promotion:

```yaml
schema: agentspec.spec_document.v0
source_key: payments-design
snapshot_id: SRC-0002
kind: markdown
title: Payments API V2 Design
remote_uri: /tmp/payments-design.md
remote_version: null
content_hash: sha256:...
normalized_hash: sha256:...
fetched_at: "2026-05-01T00:00:00Z"
classification: internal
storage_mode: committed
sections:
  - local_id: D-01
    stable_key: payments-api-v2/overview
    heading_path: ["Overview"]
    content_hash: sha256:...
    body_ref: source.md#L1-L40
requirements: []
api_contracts: []
open_questions: []
```

Adapters may support different levels of extraction, but all must emit the
same top-level shape:

- Markdown and HTML produce sections and candidate requirements.
- PDF produces sections with extraction confidence and page references.
- YAML/OpenAPI produces both sections and structured API contract entries.
- Confluence produces the same shape after fetching the page body and remote
  version through a connector.

### 4. Candidate snapshots live outside accepted compile inputs

Candidate snapshots are stored outside `docs/source/sections.yml`:

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

Candidate import must not modify:

- `docs/source/sources.yml`
- `docs/source/sections.yml`
- `docs/spec/**`
- `docs/traceability/requirements.yml`
- `agent/context-packs/**`
- `docs/adr/**`

Existing `sources.yml` records without an explicit state are treated as
`accepted` for backwards compatibility.

### 5. Validation precedes diff and promotion

Intake validation is required before diff or promotion. Validation checks:

- required metadata fields
- section ids, stable keys, line/page/body references, and content hashes
- storage-mode compliance
- classification compliance
- OpenAPI/YAML structural validity when applicable
- prompt-injection boundaries for retrieved source content

Validation failure writes a validation report and returns a structured CLI
error. It does not update accepted compile inputs.

### 6. Diff is candidate-to-baseline, not file-to-file only

AgentSpec will diff a candidate snapshot against the accepted baseline for the
same `source_key`, unless the user supplies another baseline.

The diff result includes at least:

- source metadata changes
- section additions, removals, moves, renames, and body hash changes
- candidate requirement additions, removals, strengthening, weakening, and
  supersession
- API contract changes for structured sources: endpoint, method, path,
  request schema, response schema, auth scope, enum value, and version changes
- intake recommendation: `doc-only`, `clarification`, `implement-now`,
  `defer`, `spike`, `needs-adr`, `reject`, or `needs-review`

The first implementation may use deterministic structural/hash diff and a
conservative classifier. If the classifier is unsure, it must return
`needs-review` rather than inventing a decision.

### 7. Intake recommendations do not change the DCR enum

The intake recommendation enum is intentionally wider than the DCR
classification enum from ADR-0002. It does not amend ADR-0002.

Mapping rules:

| Intake recommendation | DCR effect |
|---|---|
| `implement-now` | Recommend a DCR classified `implement-now`; operator still runs the DCR command explicitly. |
| `defer` | Recommend a DCR classified `defer`; operator still runs the DCR command explicitly. |
| `spike` | Recommend a DCR classified `spike`; operator still runs the DCR command explicitly. |
| `needs-adr` | Recommend a DCR classified `needs-adr` plus ADR follow-up; operator still runs the DCR/ADR commands explicitly. |
| `reject` | Record rejected intake evidence; no DCR is required unless the operator wants an audit DCR. |
| `doc-only` | Intake-only outcome; update accepted source/spec projection after human promotion, no DCR. |
| `clarification` | Intake-only outcome; update accepted source/spec projection after human promotion, no DCR unless implementation scope changes. |
| `needs-review` | Non-terminal pending state; never written as a DCR classification. |

`aspec intake` may write an intake report with recommended DCR fields, but it
must not call `aspec dcr classify`, `aspec dcr accept`, or
`aspec requirement accept` as part of promotion. A future DCR may add a
first-class DCR draft state; ADR-0006 does not.

### 8. Promotion is human-gated

Automation may run import, validation, and diff. Promotion requires human
approval. Policy-based auto-promotion is out of scope for ADR-0006 and would
need a follow-up DCR or ADR.

Promotion has two phases:

1. **Projection update:** mark the candidate accepted and update the accepted
   `docs/source/` projection. This phase must be atomic at the filesystem
   boundary by writing replacement manifests to temporary files and renaming
   them into place, or by using an equivalent journal/rollback strategy.
2. **Post-promotion work:** optionally run compile, write reports, and produce
   recommended follow-up DCR/ADR/task commands. This phase is not part of the
   projection-update atomic boundary.

Projection update does these things:

1. Marks the candidate snapshot as accepted.
2. Preserves previous accepted snapshots and hashes for audit.
3. Updates the accepted `docs/source/` projection.
4. Records lineage so the previous accepted baseline remains addressable.

Post-promotion work does these things:

1. If `--compile` is set, runs `aspec compile` after the accepted projection
   update; otherwise returns the exact compile command for the operator.
2. Preserves DCR-originated artifacts per R-131 and R-132 during compile.
3. Writes recommended follow-up DCR/ADR/task commands required by the intake
   recommendation. It does not auto-classify or auto-accept those artifacts.

Promotion decisions:

- `doc-only`: update accepted source/spec notes, no implementation pack.
- `clarification`: update accepted source/spec and optionally strengthen
  existing requirements after review.
- `implement-now`: recommend DCR-governed requirements and context-pack work.
- `needs-adr`: recommend a DCR plus ADR follow-up; no implementation pack
  until accepted.
- `spike`: recommend a research/spike DCR or context pack.
- `defer`: keep the diff as backlog evidence, no accepted baseline change
  unless explicitly requested.
- `reject`: keep the candidate for audit, leave accepted baseline unchanged.

### 9. Section identity is source-scoped and snapshot-qualified

Current `D-*` IDs are local to one source snapshot. They are not globally
unique once multiple accepted `source_key` values exist.

MVP rule:

- Bare `D-*` citations remain valid only while a project has exactly one
  accepted source.
- Once a project has more than one accepted source, generated artifacts must
  cite accepted sections as `source_key:D-*`.
- Historical snapshots remain addressable as `snapshot_id:D-*`.

Examples:

```text
payments-design:D-03
auth-design:D-03
SRC-0001:D-03
```

Accepted `D-*` references in requirements and context packs continue to point
at accepted baseline sections only in the single-source compatibility path.
Multi-source projects must use source-scoped citations to avoid collisions.

Promotion maps candidate sections to accepted sections by stable identity:

- exact stable key match
- otherwise heading-path lineage and content similarity
- otherwise new concept

Removed or replaced concepts are marked as superseded in lineage metadata
rather than erased. This keeps old tasks auditable even when the live external
source changes.

### 10. Source classification and storage modes are part of intake

Each snapshot declares a classification:

- `public`
- `internal`
- `confidential`
- `restricted`

Each snapshot also declares a storage mode:

- `committed`: source text may be committed to git.
- `pointer-only`: repo stores URI, metadata, and hashes only.
- `local-secure-cache`: body is stored outside normal git history.
- `enterprise-object-store`: body is stored in a configured internal store.

Connectors must not bypass storage policy. Restricted content may be diffed or
summarized only through policy-approved paths, and task context packs must
continue to delimit retrieved source content as untrusted evidence.

### 11. Existing ingest remains a compatibility shortcut

`aspec ingest` remains a backward-compatible MVP shortcut through the first
External Spec Intake implementation cycle. It must keep the current
Markdown/text behavior unless a later accepted DCR changes that contract.

A future version may reimplement `aspec ingest` internally using intake import
and promotion, but only if the external CLI behavior remains compatible for
existing single-source Markdown users.

### 12. Connectors are adapters over intake

Live Confluence, Jira, SharePoint, Google Drive, GitHub Enterprise, and other
connectors are not privileged compile inputs. They fetch content and metadata,
then hand the result to the same candidate snapshot protocol.

This keeps the first implementation file-based and testable:

1. Markdown candidate import.
2. HTML candidate import.
3. Candidate diff.
4. Human-gated promotion.
5. YAML/OpenAPI structured diff.
6. PDF extraction.
7. Live Confluence connector.

## CLI Contract

The initial command group should be:

```bash
aspec intake import <path-or-uri> \
  --kind markdown|html|pdf|yaml|openapi|confluence \
  --source-key <key> \
  --classification public|internal|confidential|restricted \
  --storage-mode committed|pointer-only|local-secure-cache|enterprise-object-store \
  --as-candidate \
  --json

aspec intake validate <snapshot-id> --json

aspec intake diff <snapshot-id> --baseline accepted --json

aspec intake classify <snapshot-id> \
  --recommendation doc-only|clarification|implement-now|defer|spike|needs-adr|reject \
  --json

aspec intake promote <snapshot-id> \
  --decision accepted \
  --compile \
  --json
```

`--decision` accepts `accepted` only in this ADR. Candidate rejection is
handled by `aspec intake classify --recommendation reject`, which leaves the
candidate un-promoted. A future DCR may extend `--decision` to include
`superseded` for explicit supersession of an earlier accepted snapshot.

Future registry commands may add:

```bash
aspec source add <source-key> <uri>
aspec source list
aspec source status <source-key>
```

## New Open Questions

- **Q-027:** Should `source_key` be globally unique across a repo, or scoped by
  product/version?
- **Q-028:** What exact similarity threshold should map a candidate section to
  an existing accepted `D-*` section?
- **Q-029:** What future policy surface would be required before any
  `doc-only` auto-promotion could be considered?
- **Q-030:** Where should `local-secure-cache` live, and how does it behave in
  CI?
- **Q-031:** Resolved by §11 — `aspec ingest` remains a backward-compatible
  Markdown/text shortcut through the first External Spec Intake cycle. Listed
  here so the numbering gap is auditable.
- **Q-032:** When a project already has multiple accepted source keys, should
  the CLI reject bare `D-*` references outright or only warn and normalize
  them to source-scoped references?
- **Q-033:** What recovery journal should repair a failed post-promotion
  compile after the accepted projection update has already succeeded?

## Consequences

### Positive

- External design sources can change without silently changing repo-local
  implementation authority.
- Code agents can cite exactly which snapshot and section they used.
- Confluence and other enterprise connectors share one auditable protocol
  instead of each adding bespoke compile behavior.
- Fixed URL, moved URL, V1/V2, increasingly detailed docs, and structured API
  contracts all fit one state model.
- Candidate import and diff can run in automation while promotion remains
  controlled.

### Negative / Costs

- Source state becomes more complex: accepted, candidate, rejected,
  superseded, and possibly archived.
- Section identity needs lineage metadata beyond current `D-*` ids.
- Compile must be stricter about accepted inputs and reconciliation.
- Storage modes add policy surface before enterprise connectors ship.
- Users now have one more review gate before implementation work can start.

### Neutral

- The existing `aspec ingest` Markdown MVP can remain as a compatibility
  shortcut while the intake lane matures.
- DCR/ADR governance remains unchanged: intake feeds DCRs, it does not bypass
  them.
- Drift review gains a new source-diff input, but code-diff drift remains the
  existing behavior.

## Implementation Guidance

Do not implement live Confluence fetching first. Start with file-based inputs
so the lifecycle is testable without credentials or network.

Recommended context-pack sequence:

1. `SpecDocument` schema and validation helpers.
2. Candidate snapshot import for Markdown.
3. Candidate diff report against accepted baseline.
4. Human-gated promotion into accepted `docs/source/` projection.
5. Compile integration and DCR-originated preservation tests.
6. HTML import.
7. YAML/OpenAPI import and structural diff.
8. Storage-mode enforcement for pointer-only.
9. PDF import.
10. Confluence connector.

Each implementation pack must cite DCR-0026 and the new requirement IDs
introduced from it. Promotion and acceptance commands must remain human-gated
unless a later ADR explicitly defines an auto-promotion policy.

## Status of this ADR

Accepted on 2026-05-01 by yimwu, drafted by Claude pilot agent during the
DCR-0026 intake. DCR-0026 is now implementation-eligible per its required
follow-up #1.
