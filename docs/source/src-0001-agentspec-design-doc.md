# AgentSpec Product Design

**Working title:** AgentSpec  
**Subtitle:** Design-to-Agent Workspace Compiler and Control Plane for Code Agents  
**Document status:** Draft v0.1  
**Primary audience:** platform engineers, developer-experience teams, AI tooling teams, engineering leads, and advanced individual developers  
**Last updated:** 2026-04-28

---

## 1. Executive Summary

AgentSpec is a design-source-grounded control plane for code agents.

It converts product requirements, design documents, architecture notes, existing repositories, and enterprise knowledge sources into an agent-ready engineering workspace. That workspace gives code agents such as Claude Code, Codex, GitHub Copilot coding agent, Open SWE, OpenHands, Cursor, and similar tools the durable context, task boundaries, requirements, role definitions, verification gates, and traceability they need to work reliably over long-lived projects.

AgentSpec does not replace coding agents. Coding agents remain the executors. AgentSpec supplies the operating layer around them:

- canonical design source snapshots
- sectioned source documents
- spec shards
- requirement records
- assumption ledgers
- open question ledgers
- design-to-code traceability
- task context packs
- role and reviewer definitions
- CLI commands
- MCP tools
- Claude Code and Codex integration packs
- scheduled automation templates
- drift detection and PR review gates

The core problem is that code agents often fail not because they cannot write code, but because they lack stable, bounded, source-grounded engineering context. They rely too much on chat history, partial summaries, stale project instructions, or incomplete task descriptions. Over time this causes implementation drift, duplicated work, missing tests, architectural inconsistency, and silent divergence from the original design.

AgentSpec makes engineering context explicit, versioned, reviewable, and reusable.

The initial product is local-first and repository-first. It generates files that any coding agent can read, even without a proprietary runtime. The long-term product adds an MCP server, Claude Code and Codex plugins, GitHub Agentic Workflow emitters, enterprise document connectors, and scheduled agent automation.

---

## 2. Core Design Principle

**Design source is canonical. Agent outputs are derived artifacts.**

An architect agent, PM agent, developer agent, or reviewer agent must not become the sole source of truth for downstream work. Each task must carry direct references to the canonical source sections, requirement IDs, accepted assumptions, ADRs, relevant code, and acceptance tests.

The essential execution model is:

```text
Design sources
  -> canonical source sections
  -> spec shards
  -> requirements and assumptions
  -> task context packs
  -> code agent execution
  -> spec compliance review
  -> tests / evals / CI
  -> traceability update
```

AgentSpec exists to prevent this failure mode:

```text
Thin user request
  -> PM summary
  -> architect summary
  -> developer summary
  -> implementation that no longer matches the original intent
```

The correct model is:

```text
Canonical design sections
  -> shared task context pack
  -> multiple role-specific analyses
  -> single bounded implementation
  -> independent spec compliance review
```

Roles are lenses, not truth sources.

---

## 3. Product Goals and Non-Goals

### 3.1 Goals for V1

1. Convert a Markdown design document into canonical source sections with stable IDs and content hashes.
2. Generate a draft project canvas, spec shards, requirements, assumptions, open questions, and task context pack templates.
3. Support sparse input and empty repositories through Discovery Mode instead of fabricating certainty.
4. Support existing repositories through Brownfield Doctor mode.
5. Generate `AGENTS.md`, `CLAUDE.md`, Claude Code subagents, Codex agents, and reusable role definitions.
6. Provide a CLI that can run locally and in CI.
7. Provide a validation model for requirements, task context packs, and traceability files.
8. Generate implementation tasks only when the relevant requirements are sufficiently specified.
9. Detect design drift in a code diff by comparing changed files against requirements, ADRs, and task context packs.
10. Dogfood AgentSpec on its own repository from the first usable milestone.

### 3.2 Goals for V2

1. Add PDF ingestion and high-quality section extraction.
2. Add enterprise source snapshots via MCP-backed connectors, such as Confluence, Jira, SharePoint, GitHub Enterprise, GitLab, Google Drive, or internal documentation systems.
3. Provide an AgentSpec MCP server for code agents.
4. Provide Claude Code and Codex plugins as thin adapters over the core CLI and MCP server.
5. Generate GitHub Agentic Workflows or GitHub Actions for scheduled read-only audits and agent-safe implementation jobs.
6. Support repository-wide traceability reports and test gap reports.
7. Support large brownfield migrations with safe task partitioning.
8. Support organization-wide policy packs.

### 3.3 Goals for V3

1. Add a hosted or self-hosted control plane UI.
2. Add multi-repository program management.
3. Add asynchronous agent execution backends.
4. Add deeper semantic repo mapping through static analysis, language servers, and code graph indexing.
5. Add enterprise governance: retention policies, source classification, approvals, audit exports, and integration with internal compliance workflows.

### 3.4 Non-Goals for V1

1. AgentSpec will not implement a general-purpose autonomous coding agent.
2. AgentSpec will not directly replace Claude Code, Codex, Copilot, Open SWE, OpenHands, SWE-agent, Cursor, or Aider.
3. AgentSpec will not auto-merge code changes.
4. AgentSpec will not assume that model-generated requirements are authoritative.
5. AgentSpec will not require a hosted service.
6. AgentSpec will not require enterprise connectors for the first release.
7. AgentSpec will not attempt perfect parsing of arbitrary PDFs, diagrams, screenshots, or proprietary binary documents in V1.
8. AgentSpec will not modify production code during initial brownfield assessment.

---

## 4. Success Criteria

### 4.1 Product Success Criteria

| Dimension | V1 Target |
|---|---:|
| Markdown design documents sectionized with stable IDs | 95%+ for normal heading-based documents |
| Generated requirements with source section references | 100% of accepted requirements |
| Task context packs with explicit source sections | 100% of implementation tasks |
| Requirements with status and confidence | 100% |
| Drift review reports generated for PR diffs | 100% of configured PRs |
| Brownfield doctor runs without modifying production code | 100% |
| Claude/Codex instruction emitters produce valid files | 100% in fixture tests |
| Dogfood tasks created through AgentSpec | 80%+ after MVP1 |

### 4.2 Quality Success Criteria

| Dimension | V1 Target |
|---|---:|
| Reduction in missing-context implementation tasks during dogfooding | 50% |
| Requirements without source references | 0 accepted requirements |
| Production implementation tasks created from unconfirmed assumptions | 0 |
| PRs missing requirement coverage table | 0 after enforcement enabled |
| Diff reviews incorrectly claiming no spec impact on known-impact fixtures | < 5% |

### 4.3 User Experience Success Criteria

A user should be able to run the following on a fresh repository:

```bash
agentspec init
agentspec ingest docs/source/design.md
agentspec compile
agentspec task create --requirement R-001
agentspec emit --target claude,codex
```

After that, the repository should contain enough durable context for a code agent to start work without relying on hidden chat history.

---

## 5. Target Users and Personas

### 5.1 Individual Developer

An advanced developer using Claude Code, Codex, Cursor, or Copilot wants to start a project from a design document and keep code agent sessions aligned over multiple days or weeks.

Needs:

- lightweight local CLI
- generated `AGENTS.md` and `CLAUDE.md`
- task context packs
- spec drift checks
- low setup cost

### 5.2 Tech Lead / Architect

A tech lead owns a design document and wants multiple developers or code agents to implement it consistently.

Needs:

- design-to-requirement traceability
- ADR generation
- accepted vs inferred assumptions
- task sequencing
- architecture drift reports
- PR spec compliance review

### 5.3 Platform / Developer Experience Team

A platform team wants to standardize how code agents work across an organization.

Needs:

- organization policy packs
- plugin distribution
- MCP integration
- enterprise document connectors
- scheduled audits
- CI integration
- read-only and write-safe automation modes

### 5.4 Enterprise Engineering Organization

An enterprise wants code agents to use internal Confluence, Jira, GitHub Enterprise, SharePoint, or similar sources without losing auditability or exposing sensitive documents.

Needs:

- source snapshot provenance
- document classification
- ACL-aware retrieval
- no secret leakage
- per-repo and org-level governance
- human review gates
- audit logs

---

## 6. Key Concepts

### 6.1 Canonical Design Source

A source document, repository artifact, enterprise document snapshot, issue, ticket, architecture note, or other artifact that is allowed to influence requirements and implementation decisions.

Examples:

- `docs/source/design.md`
- `docs/source/product-requirements.pdf`
- Confluence page snapshot
- Jira epic snapshot
- GitHub issue snapshot
- accepted ADR

### 6.2 Source Snapshot

A captured version of an external or local source document with provenance metadata:

- URI
- title
- source kind
- fetched timestamp
- source version if available
- content hash
- classification
- storage mode
- access policy

The snapshot makes code-agent behavior reproducible. A task created today should remain auditable two weeks later even if the Confluence page has changed.

### 6.3 Source Section

A stable, addressable section of a source document. Source sections are the smallest normal citation unit in AgentSpec.

Example:

```yaml
id: D-05.2
source_id: SRC-0001
title: Module Contracts
heading_path:
  - High-Level Architecture
  - Module Contracts
content_hash: sha256:...
start_line: 128
end_line: 171
```

### 6.4 Spec Shard

A canonical derived document that groups source sections around a specific engineering concern.

Examples:

- `docs/spec/product-charter.md`
- `docs/spec/runtime-architecture.md`
- `docs/spec/module-contracts.md`
- `docs/spec/security-and-governance.md`
- `docs/spec/observability-and-evaluation.md`
- `docs/spec/plugin-strategy.md`
- `docs/spec/mcp-strategy.md`
- `docs/spec/brownfield-strategy.md`

A spec shard must cite source sections and declare whether its content is source-backed, inferred, or user-confirmed.

### 6.5 Requirement

A unit of expected behavior, architecture, quality, security, or process that can be implemented, reviewed, and tested.

Each requirement has:

- ID
- title
- description
- source sections
- priority
- status
- confidence
- acceptance criteria
- code targets
- test targets
- owner or reviewer roles

### 6.6 Assumption

A statement AgentSpec needs in order to proceed but which is not fully supported by source material.

Assumptions must be explicit. They can be accepted, rejected, superseded, or left unconfirmed. Production implementation tasks cannot depend on unconfirmed high-impact assumptions unless the user explicitly overrides the gate.

### 6.7 Open Question

A decision or missing fact that blocks or constrains design, planning, implementation, security review, or evaluation.

### 6.8 Task Context Pack

The bounded context unit given to a code agent for a specific task.

A task context pack contains:

- task ID
- task type
- goal
- source sections
- requirements
- accepted assumptions
- non-goals
- allowed files
- forbidden files
- impacted modules
- existing relevant code
- tests to add or update
- acceptance criteria
- required reviewers
- implementation notes
- risks and open questions

### 6.9 Traceability Matrix

A durable mapping between source sections, requirements, code files, tests, ADRs, and tasks.

### 6.10 Design Drift

Any divergence between implementation and the accepted design, requirements, ADRs, task context pack, or security model.

Not every drift is wrong. Some drift is a valid design evolution. But it must be explicit and usually requires an ADR.

### 6.11 Agent Role

A bounded role definition used by a code agent or subagent.

Roles are not sources of truth. They define analysis perspective, required inputs, forbidden inputs, output schema, and authority boundaries.

### 6.12 Agentic Workflow

A workflow in which one or more LLM agents perform planning, analysis, implementation, review, or automation tasks under explicit constraints.

AgentSpec uses agentic patterns internally, but it does not delegate authority blindly to agents.

---

## 7. Architectural Principles

1. **Source-backed over summary-backed.** Summaries are useful but never authoritative unless they cite source sections.
2. **Explicit uncertainty.** Missing context becomes assumptions and open questions, not fabricated design.
3. **Context pack as work unit.** Code agents execute tasks from bounded context packs, not vague prompts.
4. **One writer by default.** Multiple reviewers are encouraged; multiple concurrent writers require explicit partitioning.
5. **Generator-verifier for quality-critical artifacts.** Spec compilation, requirements, drift reviews, and plugins require independent verification.
6. **Orchestrator-subagent for bounded analysis.** The coordinator delegates short, focused, read-only analysis tasks to specialists.
7. **Shared state through files, not chat history.** Durable repo artifacts are the long-term memory.
8. **Message bus later, not first.** Event-driven agent ecosystems are useful for automation, but V1 should use simpler workflows.
9. **Brownfield first-class.** Existing projects are not broken greenfield projects. Assessment must be read-only by default.
10. **Safety by default.** Automation reports and opens PRs; it does not silently push or merge.
11. **MCP for interoperability.** AgentSpec exposes structured project context through MCP so multiple code agents can consume the same facts.
12. **Plugins as thin adapters.** Claude Code and Codex plugins wrap AgentSpec capabilities; they do not own the core logic.
13. **Dogfood early.** AgentSpec must be able to scaffold, plan, review, and improve its own repository.
14. **Every stage is testable.** Sectioning, requirement extraction, context pack generation, emitters, and drift checks need fixture-based tests.
15. **Policy is data.** Organization-specific rules should be represented as versioned policy packs, not hardcoded prompts.

---

## 8. Relationship to Multi-Agent Coordination Patterns

AgentSpec should use agentic design, but it should not become an unconstrained multi-agent swarm.

The recommended starting architecture is a hybrid:

1. **Orchestrator-subagent** for the interactive CLI/plugin workflow.
2. **Generator-verifier** for quality-critical artifacts.
3. **Shared state** for durable repository artifacts.
4. **Message bus** for scheduled automation in later versions.
5. **Agent teams** only for large, independent brownfield migrations or multi-service work.

### 8.1 Default Pattern: Orchestrator-Subagent

The AgentSpec coordinator owns the high-level workflow:

```text
User request
  -> coordinator
  -> source selector
  -> spec compiler / repo scanner / specialist reviewers
  -> coordinator synthesis
  -> generated artifacts
```

Specialists are bounded and usually read-only:

- spec compiler
- source sectionizer
- requirement extractor
- brownfield mapper
- security reviewer
- plugin emitter reviewer
- drift reviewer
- test/eval reviewer

This pattern is appropriate because most AgentSpec tasks have clear decomposition and bounded outputs.

### 8.2 Generator-Verifier Pattern

Generator-verifier is mandatory for artifacts that can mislead downstream code agents:

- spec shards
- requirements
- assumptions
- context packs
- drift reviews
- plugin-generated agent instructions
- automation workflows

Example:

```text
Spec Compiler generates requirements.yml
  -> Spec Verifier checks source citations, status, confidence, and acceptance criteria
  -> Coordinator either accepts, requests revision, or asks user for clarification
```

The verifier must use explicit criteria. A generic instruction such as "check if this is good" is not acceptable.

### 8.3 Shared State Pattern

AgentSpec uses shared state in the form of repository artifacts:

```text
docs/spec/*.md
docs/traceability/*.yml
docs/adr/*.md
agent/context-packs/*.md
agent/runs/*.jsonl
reports/*.md
```

Agents do not rely on hidden conversation memory. They read and write versioned files with provenance.

This is shared state with constraints:

- all writes are schema-validated
- concurrent writes require locking or branch isolation
- derived artifacts cite source sections
- high-impact changes require ADRs

### 8.4 Message Bus Pattern

Message bus is appropriate for scheduled automation and future multi-agent ecosystems:

```text
repo_event: pull_request_opened
  -> drift_review_requested
  -> security_review_requested
  -> test_gap_review_requested
  -> compliance_summary_requested
  -> pr_comment_proposed
```

V1 should not start with a full message bus. It should emit GitHub workflows or CI jobs. A real event bus can come later when automations become numerous and independently deployable.

### 8.5 Agent Teams Pattern

Agent teams are useful when work can be partitioned for long-running, independent execution:

- migrating multiple services
- mapping a monorepo by package
- upgrading independent modules
- adding tests for separate components

Agent teams are dangerous when workers edit shared files or depend on one another's findings. AgentSpec should require task partitioning, allowed paths, locks, and final integration review before enabling this pattern.

### 8.6 Pattern Selection Matrix

| AgentSpec Scenario | Recommended Pattern |
|---|---|
| Generate initial spec from design doc | Orchestrator-subagent + generator-verifier |
| Validate generated requirements | Generator-verifier |
| Build a task context pack | Orchestrator-subagent |
| Review PR for spec drift | Generator-verifier |
| Store durable project memory | Shared state |
| Nightly audits and event-driven jobs | Message bus or workflow backend |
| Large independent service migration | Agent teams with allowed-path partitions |
| Sparse input discovery | Orchestrator-subagent with human confirmation gate |

---

## 9. System Overview

```text
                         +---------------------------+
                         | Design / Enterprise Docs  |
                         | PRDs, ADRs, Jira, Wiki    |
                         +-------------+-------------+
                                       |
                                       v
                         +---------------------------+
                         | Source Ingestion Layer    |
                         | snapshots, section IDs    |
                         +-------------+-------------+
                                       |
                                       v
                         +---------------------------+
                         | Spec Compilation Layer    |
                         | specs, reqs, assumptions  |
                         +-------------+-------------+
                                       |
                         +-------------+-------------+
                         |                           |
                         v                           v
          +---------------------------+   +---------------------------+
          | Repo Scanner              |   | Context Pack Builder      |
          | code map, tests, deps     |   | task-bounded context      |
          +-------------+-------------+   +-------------+-------------+
                        |                               |
                        v                               v
          +---------------------------+   +---------------------------+
          | Traceability Engine       |   | Agent Config Emitters     |
          | source <-> req <-> code   |   | Claude, Codex, AGENTS.md  |
          +-------------+-------------+   +-------------+-------------+
                        |                               |
                        +---------------+---------------+
                                        |
                                        v
                         +---------------------------+
                         | Verification Layer        |
                         | drift, tests, reviews     |
                         +-------------+-------------+
                                       |
                                       v
                         +---------------------------+
                         | Automation / Plugins / MCP|
                         +---------------------------+
```

---

## 10. Product Surface

### 10.1 Repo Artifacts

Repo artifacts are the most important surface because they are vendor-neutral and durable.

```text
AGENTS.md
CLAUDE.md
.agentspec/
  config.yml
  locks/
  cache/
docs/
  source/
  spec/
  traceability/
  discovery/
  adr/
agent/
  context-packs/
  roles/
  workflows/
  runs/
reports/
  drift/
  doctor/
  traceability/
  eval/
.claude/
  agents/
  skills/
.codex/
  agents/
.agents/
  skills/
.github/
  workflows/
```

### 10.2 CLI

The CLI is the primary V1 interface:

```bash
agentspec init
agentspec ingest <path-or-uri>
agentspec compile
agentspec readiness
agentspec doctor
agentspec repo scan
agentspec trace build
agentspec task create --requirement R-001
agentspec context build --task T-001
agentspec emit --target claude
agentspec emit --target codex
agentspec drift --diff main...HEAD
agentspec mcp serve
```

### 10.3 MCP Server

The MCP server gives code agents structured access to AgentSpec context.

It should expose tools such as:

- `get_project_status`
- `list_requirements`
- `get_requirement`
- `get_source_section`
- `search_source_sections`
- `get_spec_shard`
- `create_task_context_pack`
- `get_task_context_pack`
- `record_agent_finding`
- `check_diff_against_spec`
- `update_traceability`
- `list_open_questions`
- `create_adr`
- `fetch_enterprise_doc_snapshot`

### 10.4 Claude Code Plugin

The Claude Code plugin provides:

- slash-command-like skills
- specialized subagents
- hooks for pre-write and post-edit checks
- MCP server configuration
- reusable team distribution

It should be a thin adapter over the CLI and MCP server.

### 10.5 Codex Plugin

The Codex plugin provides:

- skills for AgentSpec workflows
- bundled MCP configuration
- optional local marketplace entry
- optional custom agents

It should also be a thin adapter over the CLI and MCP server.

### 10.6 GitHub Automation

AgentSpec should generate workflow templates for:

- nightly drift review
- weekly traceability audit
- PR spec compliance review
- agent-safe issue implementation
- test gap analysis
- documentation freshness checks

V1 can emit standard GitHub Actions. V2 can emit GitHub Agentic Workflows where appropriate.

---

## 11. Modes of Operation

### 11.1 Full Design Mode

Input:

- detailed design document
- optional existing repository

Behavior:

- sectionize design
- compile spec shards
- extract requirements
- build traceability
- generate implementation tasks
- generate agent configs

Implementation tasks are allowed when requirements are accepted and readiness score passes the gate.

### 11.2 Sparse Input / Discovery Mode

Input:

- short idea
- thin PRD
- incomplete README
- empty or near-empty repository

Behavior:

- create project canvas
- create assumptions ledger
- create open questions
- select archetype
- generate draft spec
- compute readiness score
- generate discovery, spike, and scaffold tasks only

Production implementation tasks are blocked until relevant assumptions are accepted or readiness reaches the configured threshold.

### 11.3 Brownfield Doctor Mode

Input:

- existing repository
- optional design doc

Behavior:

- scan repo tree
- detect language, frameworks, tests, CI, package managers
- map files to likely components
- compare design requirements to code
- identify unmapped code
- identify unimplemented requirements
- identify missing tests
- recommend first safe tasks

Brownfield doctor is read-only by default.

### 11.4 Dogfood Mode

AgentSpec uses its own workflow to develop itself.

Behavior:

- treats `docs/source/agentspec-design.md` as canonical design source
- requires tasks to have context packs
- updates traceability after implementation
- runs drift checks on PRs
- records design changes as ADRs

---

## 12. Core Runtime Components

### 12.1 CLI Application

Responsible for command parsing, configuration loading, output formatting, and local execution of core workflows.

### 12.2 Source Ingestor

Responsible for importing design sources:

- Markdown
- PDF in later versions
- Confluence snapshots in later versions
- Jira issues in later versions
- GitHub issues and PRs in later versions
- SharePoint and Drive documents in later versions

### 12.3 Source Snapshotter

Responsible for provenance:

- URI
- version
- fetched timestamp
- content hash
- storage mode
- classification
- source ACL metadata where available

### 12.4 Sectionizer

Responsible for turning source documents into stable sections.

V1 Markdown strategy:

- parse heading hierarchy
- assign deterministic section IDs
- store line ranges
- compute section content hashes
- preserve heading paths
- detect duplicate headings

### 12.5 Spec Compiler

Responsible for generating spec shards from source sections.

The compiler may use LLM assistance, but the output must mark each paragraph or requirement as:

- source-backed
- inferred
- user-confirmed
- template-provided

### 12.6 Requirement Extractor

Responsible for extracting requirements with status, priority, source references, acceptance criteria, and test targets.

### 12.7 Assumption Manager

Responsible for managing assumptions:

- creation
- acceptance
- rejection
- impact analysis
- gating implementation tasks

### 12.8 Open Question Manager

Responsible for managing missing decisions and facts.

### 12.9 Readiness Analyzer

Responsible for evaluating whether the project is ready for implementation.

Readiness dimensions:

- problem definition
- target users
- goals
- non-goals
- success criteria
- architecture boundaries
- data model
- integration points
- security model
- test strategy
- rollout plan

### 12.10 Repo Scanner

Responsible for reading existing codebases:

- repo tree
- language detection
- framework detection
- build/test commands
- package managers
- CI files
- test folders
- source folders
- docs
- dependency manifests
- code ownership hints

### 12.11 Traceability Engine

Responsible for mapping:

```text
source sections <-> spec shards <-> requirements <-> tasks <-> code <-> tests <-> ADRs
```

### 12.12 Context Pack Builder

Responsible for building task-bounded context:

- select relevant source sections
- include adjacent sections where needed
- include accepted requirements and assumptions
- include open questions and non-goals
- include allowed/forbidden paths
- include relevant code and tests
- enforce token or size budget

### 12.13 Drift Checker

Responsible for comparing diffs against requirements, ADRs, allowed paths, tests, and security policy.

### 12.14 Agent Config Emitters

Responsible for generating:

- `AGENTS.md`
- `CLAUDE.md`
- Claude subagents
- Claude plugin package
- Codex agents
- Codex plugin package
- generic role files
- workflow prompts

### 12.15 MCP Server

Responsible for exposing AgentSpec project context and actions to code agents.

### 12.16 Automation Emitter

Responsible for generating scheduled and event-triggered workflows.

### 12.17 Policy Engine

Responsible for applying organization-specific rules:

- required reviewers
- allowed automation modes
- source classification rules
- secret handling
- permitted MCP servers
- required tests
- required ADRs

---

## 13. Domain Model

### 13.1 SourceDocument

```yaml
id: SRC-0001
kind: markdown
uri: docs/source/agentspec-design.md
title: AgentSpec Product Design
version: null
content_hash: sha256:...
fetched_at: 2026-04-28T10:00:00Z
classification: internal
storage_mode: committed
```

### 13.2 SourceSection

```yaml
id: D-05.2
source_id: SRC-0001
title: Module Contracts
heading_path:
  - High-Level Architecture
  - Module Contracts
start_line: 120
end_line: 170
content_hash: sha256:...
parent: D-05
children: []
```

### 13.3 SpecShard

```yaml
id: SPEC-RUNTIME-ARCHITECTURE
title: Runtime Architecture
path: docs/spec/runtime-architecture.md
source_sections:
  - D-05
  - D-06
status: draft
confidence: medium
```

### 13.4 Requirement

```yaml
id: R-CTX-001
title: Every implementation task must have a task context pack
source_sections:
  - D-04
  - D-08.3
priority: P0
status: accepted
confidence: high
acceptance:
  - Implementation tasks reference exactly one context pack.
  - Context packs list source sections, requirements, allowed paths, non-goals, and tests.
code_targets:
  - src/agentspec/context/context_pack_builder.py
test_targets:
  - tests/unit/context/test_context_pack_builder.py
```

### 13.5 Assumption

```yaml
id: A-001
statement: The first release is local-first and CLI-first.
source: user_statement
confidence: high
status: accepted
impact:
  - packaging
  - architecture
  - plugin strategy
```

### 13.6 OpenQuestion

```yaml
id: Q-001
question: Should AgentSpec store enterprise source snapshots in git, local encrypted cache, or object storage?
status: open
impact:
  - security
  - enterprise connectors
  - reproducibility
blocking:
  - R-SRC-004
```

### 13.7 TaskContextPack

```yaml
id: T-CTX-001
title: Implement context pack builder
type: implementation
requirements:
  - R-CTX-001
source_sections:
  - D-08.3
accepted_assumptions:
  - A-001
allowed_paths:
  - src/agentspec/context/**
  - tests/unit/context/**
forbidden_paths:
  - src/agentspec/emitters/**
non_goals:
  - Do not implement Claude or Codex emitters.
acceptance:
  - Context pack can be generated from one or more requirements.
  - Missing source sections fail validation.
reviewers:
  - spec-compliance-reviewer
  - test-eval-reviewer
```

### 13.8 Finding

```yaml
id: F-20260428-001
kind: missing_test
severity: high
requirement: R-CTX-001
files:
  - src/agentspec/context/context_pack_builder.py
description: Context pack builder implementation changed but no validation test was added.
status: open
```

### 13.9 ADR

```yaml
id: ADR-0001
title: Core CLI and file artifacts before plugins
status: accepted
source_sections:
  - D-04
  - D-10
context: AgentSpec must support multiple code agents.
decision: Build vendor-neutral core first; implement plugins as adapters.
consequences:
  - CLI and schemas are first-class.
  - Claude and Codex plugins call the same core.
```

---

## 14. Repository Layout Generated by AgentSpec

```text
project/
  AGENTS.md
  CLAUDE.md
  .agentspec/
    config.yml
    cache/
    locks/

  docs/
    source/
      design.md
      sections.yml
      sources.yml
    discovery/
      project-canvas.md
      assumptions.yml
      open-questions.yml
      risks.yml
    spec/
      spec-index.md
      product-charter.md
      architecture.md
      module-contracts.md
      security-and-governance.md
      observability-and-evaluation.md
      rollout-plan.md
    traceability/
      requirements.yml
      design-to-code-map.md
      unmapped-code.md
      design-drift-log.md
    adr/
      0001-initial-architecture.md

  agent/
    roles/
      coordinator.md
      spec-compiler.md
      architect-reviewer.md
      security-reviewer.md
      test-eval-reviewer.md
      brownfield-mapper.md
    context-packs/
      template.md
    workflows/
      implement-feature.md
      review-diff.md
      compile-spec.md
      brownfield-doctor.md
    runs/

  reports/
    doctor/
    drift/
    traceability/
    eval/

  .claude/
    agents/
    skills/

  .codex/
    agents/

  .agents/
    skills/
    plugins/

  .github/
    workflows/
```

---

## 15. Sparse Input and Discovery Mode

### 15.1 Problem

Many users will not provide a complete design document. They may provide:

- one sentence
- a thin README
- a short PRD
- a half-empty repo
- scattered tickets
- outdated documentation

AgentSpec must not generate false certainty from thin input.

### 15.2 Discovery Mode Behavior

When input maturity is low, AgentSpec generates:

- `project-canvas.md`
- `assumptions.yml`
- `open-questions.yml`
- `risks.yml`
- draft specs
- discovery tasks
- spike tasks
- scaffold tasks

It must not generate production implementation tasks until readiness gates pass or the user explicitly accepts key assumptions.

### 15.3 Input Maturity Model

| Level | Input | AgentSpec Mode | Production Implementation? |
|---:|---|---|---|
| L0 | idea only | discovery | no |
| L1 | thin brief | discovery + canvas | no |
| L2 | partial design | draft spec + spike | limited scaffold only |
| L3 | usable design | requirements + tasks | yes, bounded |
| L4 | existing repo, weak docs | brownfield doctor | small safe tasks |
| L5 | design + repo + tests | normal workflow | yes |

### 15.4 Readiness Score

AgentSpec computes a readiness score from 0 to 100.

| Score | Mode |
|---:|---|
| 0-29 | discovery only |
| 30-59 | discovery + spike + scaffold |
| 60-79 | bounded implementation |
| 80-100 | normal implementation workflow |

Readiness dimensions:

- problem definition
- target users
- goals
- non-goals
- success criteria
- architecture boundaries
- data model
- integrations
- security model
- test strategy
- rollout plan

### 15.5 Assumption Promotion

A requirement depending on an unconfirmed high-impact assumption cannot become an accepted implementation requirement.

```text
inferred requirement
  -> user accepts assumption
  -> accepted requirement
  -> implementation task can be created
```

---

## 16. Brownfield Doctor Design

### 16.1 Purpose

Brownfield Doctor helps existing projects adopt AgentSpec without forcing a rewrite.

### 16.2 Read-Only First

The first brownfield pass must not modify production code.

It generates reports:

- repo map
- design coverage
- unmapped requirements
- unmapped code
- test gap report
- architecture drift report
- agent readiness report
- first safe tasks

### 16.3 Repo Scanner Outputs

```yaml
repo:
  languages:
    - python
  package_managers:
    - poetry
  test_frameworks:
    - pytest
  ci:
    - github_actions
  source_roots:
    - src/
  test_roots:
    - tests/
  docs:
    - README.md
    - docs/
```

### 16.4 First Safe Tasks

For weakly documented projects, AgentSpec should create tasks such as:

- document current behavior
- add smoke tests
- identify build and test commands
- map existing modules to tentative components
- create AGENTS.md and CLAUDE.md
- create traceability placeholders
- add missing test fixtures

Major refactors require accepted ADRs.

---

## 17. Task Types

| Task Type | Purpose | Code Writes? |
|---|---|---|
| discovery | clarify unknowns | no |
| spec | write or revise spec artifacts | docs only |
| spike | validate a technical path | experiments only |
| scaffold | create project skeleton | limited |
| implementation | implement accepted requirement | yes |
| review | inspect code, spec, tests, or drift | no |
| migration | partitioned brownfield work | bounded allowed paths |
| automation | configure workflow jobs | workflow paths only |

Each task type has validation rules.

---

## 18. Workflow Designs

### 18.1 Greenfield Init Workflow

```text
User runs agentspec init
  -> create repo artifact layout
  -> create default config
  -> create AGENTS.md and CLAUDE.md skeletons
  -> create discovery files
  -> create role definitions
```

### 18.2 Design Ingestion Workflow

```text
Input design.md
  -> snapshot source
  -> parse headings
  -> generate source sections
  -> compute section hashes
  -> write docs/source/sections.yml
```

### 18.3 Spec Compilation Workflow

```text
source sections
  -> spec compiler
  -> spec shards
  -> requirement extractor
  -> assumptions and open questions
  -> verifier
  -> readiness report
```

### 18.4 Task Creation Workflow

```text
selected requirements
  -> context pack builder
  -> include source sections
  -> include accepted assumptions
  -> include non-goals
  -> include allowed paths
  -> include tests
  -> validate pack
```

### 18.5 Code Agent Execution Workflow

```text
code agent receives task context pack
  -> reads required sections and code
  -> writes plan
  -> implements allowed changes
  -> runs tests
  -> updates traceability
  -> summarizes requirement coverage
```

### 18.6 Review Workflow

```text
diff + context pack + requirements
  -> spec compliance review
  -> security review if impacted
  -> test gap review
  -> drift report
  -> approve / block / require ADR
```

### 18.7 Automation Workflow

```text
schedule or repository event
  -> run read-only agent job
  -> produce structured proposed output
  -> validate output
  -> optional write job applies safe action
```

---

## 19. CLI Specification

### 19.1 `agentspec init`

Creates AgentSpec structure in a repository.

Options:

```bash
agentspec init --mode greenfield
agentspec init --mode brownfield
agentspec init --targets claude,codex
agentspec init --archetype code-agent-tooling
```

### 19.2 `agentspec ingest`

Imports a source document.

```bash
agentspec ingest docs/source/design.md
agentspec ingest docs/source/design.pdf --experimental
agentspec ingest confluence://SPACE/page-id --snapshot
```

### 19.3 `agentspec compile`

Compiles source sections into spec artifacts.

```bash
agentspec compile
agentspec compile --auto-assume
agentspec compile --no-llm
```

### 19.4 `agentspec readiness`

Computes readiness score.

```bash
agentspec readiness
agentspec readiness --json
```

### 19.5 `agentspec doctor`

Runs brownfield assessment.

```bash
agentspec doctor
agentspec doctor --design docs/source/design.md
```

### 19.6 `agentspec task create`

Creates a task context pack.

```bash
agentspec task create --requirement R-CTX-001 --type implementation
agentspec task create --type discovery --title "Clarify plugin strategy"
```

### 19.7 `agentspec emit`

Generates integration artifacts.

```bash
agentspec emit --target agents-md
agentspec emit --target claude
agentspec emit --target codex
agentspec emit --target github-actions
agentspec emit --target github-agentic-workflows
```

### 19.8 `agentspec drift`

Checks design drift.

```bash
agentspec drift --diff main...HEAD
agentspec drift --pr 123
```

### 19.9 `agentspec mcp serve`

Starts the MCP server.

```bash
agentspec mcp serve --stdio
agentspec mcp serve --http :8765
```

---

## 20. MCP Tool Specification

### 20.1 `get_project_status`

Returns readiness, current requirements summary, open questions, active tasks, and traceability health.

### 20.2 `list_requirements`

Filters by status, priority, source section, code target, or task.

### 20.3 `get_requirement`

Returns requirement details and linked source sections.

### 20.4 `get_source_section`

Returns canonical source section text and metadata.

### 20.5 `search_source_sections`

Semantic or keyword search over source sections. V1 can be keyword-only.

### 20.6 `create_task_context_pack`

Creates a task pack from one or more requirements.

### 20.7 `get_task_context_pack`

Returns the task pack in Markdown or JSON.

### 20.8 `check_diff_against_spec`

Runs spec compliance review for a diff.

### 20.9 `update_traceability`

Records implemented requirements, changed files, and tests.

### 20.10 `record_agent_finding`

Records a finding from a reviewer or code agent.

---

## 21. Claude Code Integration

### 21.1 Project-Local Claude Integration

Generated structure:

```text
CLAUDE.md
.claude/
  agents/
    agentspec-coordinator.md
    agentspec-spec-reviewer.md
    agentspec-security-reviewer.md
    agentspec-test-reviewer.md
    agentspec-brownfield-mapper.md
  skills/
    agentspec-compile/
      SKILL.md
    agentspec-create-task/
      SKILL.md
    agentspec-drift-review/
      SKILL.md
```

### 21.2 Claude Plugin

Plugin package:

```text
agentspec-claude-plugin/
  .claude-plugin/
    plugin.json
  skills/
    compile-spec/
      SKILL.md
    create-task/
      SKILL.md
    drift-review/
      SKILL.md
    brownfield-doctor/
      SKILL.md
  agents/
    spec-compliance-reviewer.md
    context-coordinator.md
    security-reviewer.md
  hooks/
    hooks.json
  scripts/
    agentspec-cli-wrapper.sh
  mcp/
    agentspec-mcp.json
```

### 21.3 Claude Role Rules

Claude subagents should be read-only by default unless a task explicitly grants a bounded file scope.

Plugin agents should use output schemas that require:

- source sections read
- requirements covered
- findings
- confidence
- open questions
- recommended next action

---

## 22. Codex Integration

### 22.1 Project-Local Codex Integration

Generated structure:

```text
AGENTS.md
.agents/
  skills/
    agentspec-compile/
      SKILL.md
    agentspec-task/
      SKILL.md
    agentspec-drift/
      SKILL.md
.codex/
  agents/
    spec-reviewer.toml
    security-reviewer.toml
    brownfield-mapper.toml
```

### 22.2 Codex Plugin

Plugin package:

```text
agentspec-codex-plugin/
  .codex-plugin/
    plugin.json
  skills/
    compile-spec/
      SKILL.md
    create-task/
      SKILL.md
    drift-review/
      SKILL.md
  .mcp.json
```

### 22.3 Codex Role Rules

Codex custom agents should be used for bounded analysis and review tasks. Implementation remains under the main coding session unless the task context pack grants partitioned write access.

---

## 23. Security and Governance

### 23.1 Source Classification

Every source document and section has a classification:

- public
- internal
- confidential
- restricted

Classification affects:

- whether content can be committed
- whether content can be sent to external models
- whether content can appear in task context packs
- whether automation can run on it
- retention and audit behavior

### 23.2 Storage Modes

| Mode | Description | Use Case |
|---|---|---|
| committed | source text is committed to repo | public/internal docs |
| local-secure-cache | encrypted local cache; repo stores hash | confidential docs |
| enterprise-object-store | snapshot stored in internal object store | enterprise systems |
| pointer-only | repo stores URI and hash only | restricted docs |

### 23.3 Prompt Injection Defense

AgentSpec must treat source documents, repository comments, issues, and retrieved enterprise content as untrusted data. Generated task context packs should delimit source content and never turn retrieved text into system-level instructions.

### 23.4 Automation Permissions

Default automation is read-only.

Write-capable jobs require:

- explicit label or manual trigger
- task context pack
- allowed paths
- branch isolation
- no secrets in agent environment
- structured proposed output
- output validation
- human review
- no auto-merge by default

### 23.5 Secret Handling

Task context packs must exclude secrets. Repo scanning should detect likely secrets and redact them in reports.

### 23.6 Audit

AgentSpec should record:

- source snapshots
- generated artifact versions
- task creation events
- agent findings
- drift reviews
- assumption promotions
- ADR decisions
- automation runs

V1 can record audit events in JSONL files under `agent/runs/`.

---

## 24. Observability and Evaluation

### 24.1 Runtime Metrics

- number of source documents ingested
- number of source sections generated
- number of requirements extracted
- number of assumptions created
- readiness score
- context packs generated
- drift reviews run
- findings by severity
- traceability coverage
- plugin emitter validation failures

### 24.2 Quality Metrics

- requirements with source references
- accepted requirements depending on unconfirmed assumptions
- tasks missing context packs
- tasks missing tests
- code files without requirement mapping
- requirements without code target
- false positives in drift checker fixture tests
- false negatives in drift checker fixture tests

### 24.3 Dogfood Metrics

- percent of AgentSpec tasks created through AgentSpec
- percent of PRs with drift review
- percent of changes mapped to requirements
- number of ADRs created from drift reviews
- recurring missing-context failures

### 24.4 Golden Fixtures

AgentSpec should maintain fixtures for:

- complete design document
- sparse design document
- empty repository
- small existing repository
- brownfield repository with mismatched docs
- diff that changes module contract
- diff that requires ADR
- diff that changes tests only
- plugin emitter expected output

---

## 25. Drift Checker Design

### 25.1 Inputs

- git diff
- changed file list
- task context pack
- requirements.yml
- ADRs
- design-to-code map
- policy pack
- test results if available

### 25.2 Checks

1. Changed files outside allowed paths.
2. Requirement IDs missing from summary.
3. Production code changed without tests.
4. Contract files changed without ADR.
5. Security-sensitive files changed without security review.
6. Spec files changed without source reference.
7. New behavior added without requirement mapping.
8. Unconfirmed assumptions used in implementation.
9. Traceability not updated.
10. Generated files modified manually when they should be regenerated.

### 25.3 Output

```md
# Spec Compliance Review

## Decision
block / approve-with-comments / approve

## Compared Against
- Task: T-001
- Requirements: R-001, R-002
- Source sections: D-03, D-04
- ADRs: ADR-0001

## Findings
...

## Requirement Coverage
| Requirement | Status | Evidence |
|---|---|---|

## Required Actions
...
```

---

## 26. Plugin Strategy

### 26.1 Core Before Plugins

The core logic belongs in:

- library modules
- CLI
- MCP server
- repo artifact schemas

Plugins should invoke these capabilities, not duplicate them.

### 26.2 Why Plugins Still Matter

Plugins improve usability and distribution:

- slash-command-like workflows
- discoverable skills
- specialized agents
- hooks
- MCP configuration bundling
- team-wide standardization

### 26.3 Recommended Sequence

1. Build CLI and repo artifacts.
2. Add local Claude/Codex emitters.
3. Add MCP server.
4. Add Claude Code plugin.
5. Add Codex plugin.
6. Add org-level plugin marketplace/distribution.

---

## 27. Automation Strategy

### 27.1 Read-Only Jobs

- nightly drift review
- weekly traceability audit
- stale open question review
- test gap review
- documentation freshness check
- dependency risk summary

### 27.2 PR-Only Jobs

- agent-safe issue implementation
- missing test addition
- documentation update
- traceability update

### 27.3 Prohibited by Default

- direct push to main
- auto-merge
- secret access by agent process
- unbounded file edits
- unrestricted network egress

---

## 28. Rollout Plan

### Phase 0: Design and Bootstrap

Deliverables:

- AgentSpec design doc
- initial repo
- minimal `AGENTS.md`
- initial requirements.yml
- first task context pack template

### Phase 1: Local Artifact Scaffold

Deliverables:

- `agentspec init`
- artifact layout
- schema validation
- generated AGENTS.md / CLAUDE.md

### Phase 2: Markdown Design Compiler

Deliverables:

- `agentspec ingest`
- Markdown sectionizer
- source snapshots
- source section IDs and hashes
- basic spec shard generation
- assumptions and open questions

### Phase 3: Requirements and Context Packs

Deliverables:

- requirements schema
- requirement extractor
- task context pack builder
- readiness analyzer
- discovery mode gates

### Phase 4: Brownfield Doctor

Deliverables:

- repo scanner
- language/framework detection
- test command detection
- design-to-code mapping report
- first safe task generator

### Phase 5: Drift Checker

Deliverables:

- diff parser
- requirement impact analyzer
- spec compliance report
- CI-ready command

### Phase 6: Agent Config Emitters

Deliverables:

- AGENTS.md emitter
- CLAUDE.md emitter
- Claude subagents
- Codex agents
- role files

### Phase 7: MCP Server

Deliverables:

- MCP tools
- CLI/MCP shared core
- Claude and Codex MCP config examples

### Phase 8: Plugins

Deliverables:

- Claude Code plugin
- Codex plugin
- plugin smoke tests
- distribution docs

### Phase 9: Automation

Deliverables:

- GitHub Actions templates
- GitHub Agentic Workflows templates
- nightly and weekly report jobs
- agent-safe issue runner template

### Phase 10: Enterprise Connectors

Deliverables:

- Confluence snapshot provider
- Jira snapshot provider
- GitHub Enterprise provider
- storage mode policy
- source classification support

---

## 29. Recommended Initial Implementation Tasks

1. Define core schemas for SourceDocument, SourceSection, Requirement, Assumption, OpenQuestion, TaskContextPack, Finding, and ADR.
2. Implement `agentspec init`.
3. Implement Markdown sectionizer.
4. Implement source snapshot metadata and section hash generation.
5. Implement requirements.yml validation.
6. Implement assumptions.yml and open-questions.yml validation.
7. Implement project canvas generator for sparse input.
8. Implement readiness scorecard.
9. Implement task context pack builder.
10. Implement AGENTS.md and CLAUDE.md emitters.
11. Implement basic brownfield repo scanner.
12. Implement diff parser and drift review skeleton.
13. Add dogfood workflow to AgentSpec itself.

---

## 30. Open Questions

1. What should the final product name be?
2. Should the first implementation language be Python, TypeScript, or a split architecture?
3. Should LLM-based spec compilation be built into the CLI, or delegated to code agents through generated prompts first?
4. What is the minimum useful MCP tool set for V1?
5. Should enterprise source snapshots ever be committed to git by default?
6. What plugin should be built first: Claude Code or Codex?
7. Should AgentSpec support GitHub Agentic Workflows before or after generic GitHub Actions?
8. What is the best default schema format: YAML, JSON, TOML, or Markdown frontmatter?
9. How strict should readiness gates be by default?
10. What is the first public dogfood demo?

---

## 31. Candidate Project Names

### 31.1 Most Direct Names

| Name | Meaning |
|---|---|
| AgentSpec | Specification system for code agents |
| AgentContext | Context layer for code agents |
| CodeAgentOS | Operating system for code-agent work |
| AgentWorkbench | Workspace for agent-driven development |
| AgentControlPlane | Control plane for code agents |
| Design2Agent | Converts design docs into agent-ready projects |
| Spec2CodeAgent | Bridges specs and code agents |
| AgentReady | Makes a repository ready for code agents |
| RepoPilot | Guides agents through repositories |
| SpecPilot | Pilots implementation from specs |

### 31.2 Enterprise-Oriented Names

| Name | Meaning |
|---|---|
| DesignOps AI | Operationalizes design docs for AI development |
| AgentOps Kit | Operational toolkit for code agents |
| CodeAgentOps | DevOps-like operating model for code agents |
| SpecOps | Operations layer for specifications |
| ProjectSpecOps | Spec operations for projects |
| AgentGovern | Governance layer for code agents |
| TraceSpec | Traceability-first spec system |
| SourceBound | Source-grounded agent execution |
| DesignTrace | Design-to-code traceability |
| ContextForge | Forges reusable context for agents |

### 31.3 Short Acronyms

| Acronym | Expansion |
|---|---|
| ASC | Agent Specification Compiler |
| DARC | Design-to-Agent Repository Compiler |
| CAOS | Code Agent Operating System |
| CASP | Code Agent Specification Platform |
| ACME | Agent Context Management Engine |
| ACT | Agent Context Toolkit |
| DAC | Design Agent Compiler |
| ARC | Agent-Ready Compiler |
| TRAC | Traceable Requirements for Agent Coding |
| SAGE | Spec-Aware Generation Engine |

### 31.4 Recommended Shortlist

1. AgentSpec
2. AgentReady
3. Design2Agent
4. ContextForge
5. CodeAgentOS
6. TraceSpec
7. SpecPilot
8. SourceBound

The strongest working name is **AgentSpec** because it is short, easy to remember, and immediately communicates that the project turns specifications into agent-usable structure.

---

## 32. Summary

AgentSpec is a design-source-grounded control plane for code agents.

It turns incomplete ideas, detailed design documents, existing repositories, and enterprise knowledge sources into durable, traceable, agent-ready engineering workspaces. Its core output is not generated application code. Its core output is the structured context and governance layer that makes code-agent execution reliable:

- canonical source sections
- spec shards
- requirements
- assumptions
- open questions
- task context packs
- agent roles
- traceability
- drift reviews
- plugins
- MCP tools
- safe automation

The project should use agentic design internally, but in a bounded way. Start with orchestrator-subagent and generator-verifier patterns. Use repository artifacts as shared state. Add message-bus-like automation later. Reserve persistent agent teams for large, safely partitioned brownfield work.

The recommended first milestone is not a plugin and not an autonomous runner. The recommended first milestone is a vendor-neutral local CLI that creates an agent-ready repository structure, ingests a Markdown design document, creates source sections, validates requirements and assumptions, and generates task context packs.

Once that foundation works, Claude Code and Codex plugins become thin adapters over a stable core rather than fragile one-off prompt packs.
