# Runtime Architecture

Status: draft
Confidence: medium

## Source Sections

- `D-07` 7. Architectural Principles
- `D-09` 9. System Overview
- `D-12` 12. Core Runtime Components
- `D-12.1` 12. Core Runtime Components > 12.1 CLI Application
- `D-12.2` 12. Core Runtime Components > 12.2 Source Ingestor
- `D-12.3` 12. Core Runtime Components > 12.3 Source Snapshotter
- `D-12.4` 12. Core Runtime Components > 12.4 Sectionizer
- `D-12.5` 12. Core Runtime Components > 12.5 Spec Compiler
- `D-12.6` 12. Core Runtime Components > 12.6 Requirement Extractor
- `D-12.7` 12. Core Runtime Components > 12.7 Assumption Manager
- `D-12.8` 12. Core Runtime Components > 12.8 Open Question Manager
- `D-12.9` 12. Core Runtime Components > 12.9 Readiness Analyzer
- `D-12.10` 12. Core Runtime Components > 12.10 Repo Scanner
- `D-12.11` 12. Core Runtime Components > 12.11 Traceability Engine
- `D-12.12` 12. Core Runtime Components > 12.12 Context Pack Builder
- `D-12.13` 12. Core Runtime Components > 12.13 Drift Checker
- `D-12.14` 12. Core Runtime Components > 12.14 Agent Config Emitters
- `D-12.15` 12. Core Runtime Components > 12.15 MCP Server
- `D-12.16` 12. Core Runtime Components > 12.16 Automation Emitter
- `D-12.17` 12. Core Runtime Components > 12.17 Policy Engine

## Source-Backed Notes

### D-07 7. Architectural Principles

Source-backed.

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
10. **Safety by default.** Automation reports and opens PRs; it

...

### D-09 9. System Overview

Source-backed.

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
          | Repo Scanner              |   | Context Pack Builder

...

### D-12 12. Core Runtime Components

Source-backed.

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

Responsible for ext

...

### D-12.1 12.1 CLI Application

Source-backed.

### 12.1 CLI Application

Responsible for command parsing, configuration loading, output formatting, and local execution of core workflows.

### D-12.2 12.2 Source Ingestor

Source-backed.

### 12.2 Source Ingestor

Responsible for importing design sources:

- Markdown
- PDF in later versions
- Confluence snapshots in later versions
- Jira issues in later versions
- GitHub issues and PRs in later versions
- SharePoint and Drive documents in later versions

### D-12.3 12.3 Source Snapshotter

Source-backed.

### 12.3 Source Snapshotter

Responsible for provenance:

- URI
- version
- fetched timestamp
- content hash
- storage mode
- classification
- source ACL metadata where available

### D-12.4 12.4 Sectionizer

Source-backed.

### 12.4 Sectionizer

Responsible for turning source documents into stable sections.

V1 Markdown strategy:

- parse heading hierarchy
- assign deterministic section IDs
- store line ranges
- compute section content hashes
- preserve heading paths
- detect duplicate headings

### D-12.5 12.5 Spec Compiler

Source-backed.

### 12.5 Spec Compiler

Responsible for generating spec shards from source sections.

The compiler may use LLM assistance, but the output must mark each paragraph or requirement as:

- source-backed
- inferred
- user-confirmed
- template-provided

### D-12.6 12.6 Requirement Extractor

Source-backed.

### 12.6 Requirement Extractor

Responsible for extracting requirements with status, priority, source references, acceptance criteria, and test targets.

### D-12.7 12.7 Assumption Manager

Source-backed.

### 12.7 Assumption Manager

Responsible for managing assumptions:

- creation
- acceptance
- rejection
- impact analysis
- gating implementation tasks

### D-12.8 12.8 Open Question Manager

Source-backed.

### 12.8 Open Question Manager

Responsible for managing missing decisions and facts.

### D-12.9 12.9 Readiness Analyzer

Source-backed.

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
