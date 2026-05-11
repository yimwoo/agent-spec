# Rollout Plan

Status: draft
Confidence: medium

## Source Sections

- `D-28` 28. Rollout Plan
- `D-28.1` 28. Rollout Plan > Phase 0: Design and Bootstrap
- `D-28.2` 28. Rollout Plan > Phase 1: Local Artifact Scaffold
- `D-28.3` 28. Rollout Plan > Phase 2: Markdown Design Compiler
- `D-28.4` 28. Rollout Plan > Phase 3: Requirements and Context Packs
- `D-28.5` 28. Rollout Plan > Phase 4: Brownfield Doctor
- `D-28.6` 28. Rollout Plan > Phase 5: Drift Checker
- `D-28.7` 28. Rollout Plan > Phase 6: Agent Config Emitters
- `D-28.8` 28. Rollout Plan > Phase 7: MCP Server
- `D-28.9` 28. Rollout Plan > Phase 8: Plugins
- `D-28.10` 28. Rollout Plan > Phase 9: Automation
- `D-28.11` 28. Rollout Plan > Phase 10: Enterprise Connectors
- `D-29` 29. Recommended Initial Implementation Tasks
- `lifecycle-engine-hardening-design:D-20` Phased Implementation Plan
- `lifecycle-engine-hardening-design:D-20.1` Phased Implementation Plan > Phase 1: Lifecycle Projection Hardening
- `lifecycle-engine-hardening-design:D-20.2` Phased Implementation Plan > Phase 2: Write-Back Module
- `lifecycle-engine-hardening-design:D-20.3` Phased Implementation Plan > Phase 3: Finish Orchestrator
- `lifecycle-engine-hardening-design:D-20.4` Phased Implementation Plan > Phase 4: Native Workflow Creation
- `lifecycle-engine-hardening-design:D-20.5` Phased Implementation Plan > Phase 5: Roadmap Preservation Mode
- `lifecycle-engine-hardening-design:D-20.6` Phased Implementation Plan > Phase 6: Strict Lifecycle Enforcement
- `lifecycle-engine-hardening-design:D-20.7` Phased Implementation Plan > Phase 7: Migration Tools
- `lifecycle-engine-hardening-design:D-20.8` Phased Implementation Plan > Phase 8: Skill Gates
- `agentspec-hotl-integration-without-hotl-names:D-44` Implementation Phases
- `agentspec-hotl-integration-without-hotl-names:D-45` Phase 1: Terminology and File Model
- `agentspec-hotl-integration-without-hotl-names:D-46` Phase 2: Native Planning Command
- `agentspec-hotl-integration-without-hotl-names:D-47` Phase 3: Session Runtime
- `agentspec-hotl-integration-without-hotl-names:D-48` Phase 4: Execute Command
- `agentspec-hotl-integration-without-hotl-names:D-49` Phase 5: Review and Finish
- `agentspec-hotl-integration-without-hotl-names:D-50` Phase 6: Drift and Next Action
- `agentspec-hotl-integration-without-hotl-names:D-51` Phase 7: Legacy Migration

## Source-Backed Notes

### D-28 28. Rollout Plan

Source-backed.

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

### Phase 7: MCP Se

...

### D-28.1 Phase 0: Design and Bootstrap

Source-backed.

### Phase 0: Design and Bootstrap

Deliverables:

- AgentSpec design doc
- initial repo
- minimal `AGENTS.md`
- initial requirements.yml
- first task context pack template

### D-28.2 Phase 1: Local Artifact Scaffold

Source-backed.

### Phase 1: Local Artifact Scaffold

Deliverables:

- `agentspec init`
- artifact layout
- schema validation
- generated AGENTS.md / CLAUDE.md

### D-28.3 Phase 2: Markdown Design Compiler

Source-backed.

### Phase 2: Markdown Design Compiler

Deliverables:

- `agentspec ingest`
- Markdown sectionizer
- source snapshots
- source section IDs and hashes
- basic spec shard generation
- assumptions and open questions

### D-28.4 Phase 3: Requirements and Context Packs

Source-backed.

### Phase 3: Requirements and Context Packs

Deliverables:

- requirements schema
- requirement extractor
- task context pack builder
- readiness analyzer
- discovery mode gates

### D-28.5 Phase 4: Brownfield Doctor

Source-backed.

### Phase 4: Brownfield Doctor

Deliverables:

- repo scanner
- language/framework detection
- test command detection
- design-to-code mapping report
- first safe task generator

### D-28.6 Phase 5: Drift Checker

Source-backed.

### Phase 5: Drift Checker

Deliverables:

- diff parser
- requirement impact analyzer
- spec compliance report
- CI-ready command

### D-28.7 Phase 6: Agent Config Emitters

Source-backed.

### Phase 6: Agent Config Emitters

Deliverables:

- AGENTS.md emitter
- CLAUDE.md emitter
- Claude subagents
- Codex agents
- role files

### D-28.8 Phase 7: MCP Server

Source-backed.

### Phase 7: MCP Server

Deliverables:

- MCP tools
- CLI/MCP shared core
- Claude and Codex MCP config examples

### D-28.9 Phase 8: Plugins

Source-backed.

### Phase 8: Plugins

Deliverables:

- Claude Code plugin
- Codex plugin
- plugin smoke tests
- distribution docs

### D-28.10 Phase 9: Automation

Source-backed.

### Phase 9: Automation

Deliverables:

- GitHub Actions templates
- GitHub Agentic Workflows templates
- nightly and weekly report jobs
- agent-safe issue runner template

### D-28.11 Phase 10: Enterprise Connectors

Source-backed.

### Phase 10: Enterprise Connectors

Deliverables:

- Confluence snapshot provider
- Jira snapshot provider
- GitHub Enterprise provider
- storage mode policy
- source classification support

---
