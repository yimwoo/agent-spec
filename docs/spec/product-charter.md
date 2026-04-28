# Product Charter

Status: draft
Confidence: medium

## Source Sections

- `D-01` 1. Executive Summary
- `D-03` 3. Product Goals and Non-Goals
- `D-03.1` 3. Product Goals and Non-Goals > 3.1 Goals for V1
- `D-03.2` 3. Product Goals and Non-Goals > 3.2 Goals for V2
- `D-03.3` 3. Product Goals and Non-Goals > 3.3 Goals for V3
- `D-03.4` 3. Product Goals and Non-Goals > 3.4 Non-Goals for V1
- `D-04` 4. Success Criteria
- `D-04.1` 4. Success Criteria > 4.1 Product Success Criteria
- `D-04.2` 4. Success Criteria > 4.2 Quality Success Criteria
- `D-04.3` 4. Success Criteria > 4.3 User Experience Success Criteria
- `D-05` 5. Target Users and Personas
- `D-05.1` 5. Target Users and Personas > 5.1 Individual Developer
- `D-05.2` 5. Target Users and Personas > 5.2 Tech Lead / Architect
- `D-05.3` 5. Target Users and Personas > 5.3 Platform / Developer Experience Team
- `D-05.4` 5. Target Users and Personas > 5.4 Enterprise Engineering Organization

## Source-Backed Notes

### D-01 1. Executive Summary

Source-backed.

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

The core problem is that code agents often fail not because they cannot write code, but because they lack stable, bounded, source-groun

...

### D-03 3. Product Goals and Non-Goals

Source-backed.

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
2. Add enterprise source snapshots via MCP-backed connectors, such as Confluence, Jira, SharePoint, GitHub Enterprise, GitLab

...

### D-03.1 3.1 Goals for V1

Source-backed.

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

### D-03.2 3.2 Goals for V2

Source-backed.

### 3.2 Goals for V2

1. Add PDF ingestion and high-quality section extraction.
2. Add enterprise source snapshots via MCP-backed connectors, such as Confluence, Jira, SharePoint, GitHub Enterprise, GitLab, Google Drive, or internal documentation systems.
3. Provide an AgentSpec MCP server for code agents.
4. Provide Claude Code and Codex plugins as thin adapters over the core CLI and MCP server.
5. Generate GitHub Agentic Workflows or GitHub Actions for scheduled read-only audits and agent-safe implementation jobs.
6. Support repository-wide traceability reports and test gap reports.
7. Support large brownfield migrations with safe task partitioning.
8. Support organization-wide policy packs.

### D-03.3 3.3 Goals for V3

Source-backed.

### 3.3 Goals for V3

1. Add a hosted or self-hosted control plane UI.
2. Add multi-repository program management.
3. Add asynchronous agent execution backends.
4. Add deeper semantic repo mapping through static analysis, language servers, and code graph indexing.
5. Add enterprise governance: retention policies, source classification, approvals, audit exports, and integration with internal compliance workflows.

### D-03.4 3.4 Non-Goals for V1

Source-backed.

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

### D-04 4. Success Criteria

Source-backed.

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

...

### D-04.1 4.1 Product Success Criteria

Source-backed.

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

### D-04.2 4.2 Quality Success Criteria

Source-backed.

### 4.2 Quality Success Criteria

| Dimension | V1 Target |
|---|---:|
| Reduction in missing-context implementation tasks during dogfooding | 50% |
| Requirements without source references | 0 accepted requirements |
| Production implementation tasks created from unconfirmed assumptions | 0 |
| PRs missing requirement coverage table | 0 after enforcement enabled |
| Diff reviews incorrectly claiming no spec impact on known-impact fixtures | < 5% |

### D-04.3 4.3 User Experience Success Criteria

Source-backed.

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

### D-05 5. Target Users and Personas

Source-backed.

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

An enterprise wants code agents to use internal Confluence, Jira, GitHub Enterprise, SharePoint, or similar sources without losing auditability o

...

### D-05.1 5.1 Individual Developer

Source-backed.

### 5.1 Individual Developer

An advanced developer using Claude Code, Codex, Cursor, or Copilot wants to start a project from a design document and keep code agent sessions aligned over multiple days or weeks.

Needs:

- lightweight local CLI
- generated `AGENTS.md` and `CLAUDE.md`
- task context packs
- spec drift checks
- low setup cost
