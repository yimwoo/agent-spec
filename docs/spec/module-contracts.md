# Module Contracts

Status: draft
Confidence: medium

## Source Sections

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
- `D-13` 13. Domain Model
- `D-13.1` 13. Domain Model > 13.1 SourceDocument
- `D-13.2` 13. Domain Model > 13.2 SourceSection
- `D-13.3` 13. Domain Model > 13.3 SpecShard
- `D-13.4` 13. Domain Model > 13.4 Requirement
- `D-13.5` 13. Domain Model > 13.5 Assumption
- `D-13.6` 13. Domain Model > 13.6 OpenQuestion
- `D-13.7` 13. Domain Model > 13.7 TaskContextPack
- `D-13.8` 13. Domain Model > 13.8 Finding
- `D-13.9` 13. Domain Model > 13.9 ADR
- `D-17` 17. Task Types
- `D-18` 18. Workflow Designs
- `D-18.1` 18. Workflow Designs > 18.1 Greenfield Init Workflow
- `D-18.2` 18. Workflow Designs > 18.2 Design Ingestion Workflow
- `D-18.3` 18. Workflow Designs > 18.3 Spec Compilation Workflow
- `D-18.4` 18. Workflow Designs > 18.4 Task Creation Workflow
- `D-18.5` 18. Workflow Designs > 18.5 Code Agent Execution Workflow
- `D-18.6` 18. Workflow Designs > 18.6 Review Workflow
- `D-18.7` 18. Workflow Designs > 18.7 Automation Workflow

## Source-Backed Notes

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

### D-12.10 12.10 Repo Scanner

Source-backed.

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

### D-12.11 12.11 Traceability Engine

Source-backed.

### 12.11 Traceability Engine

Responsible for mapping:

```text
source sections <-> spec shards <-> requirements <-> tasks <-> code <-> tests <-> ADRs
```
