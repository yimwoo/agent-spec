# Plugin Strategy

Status: draft
Confidence: medium

## Source Sections

- `D-10.3` 10. Product Surface > 10.3 MCP Server
- `D-10.4` 10. Product Surface > 10.4 Claude Code Plugin
- `D-10.5` 10. Product Surface > 10.5 Codex Plugin
- `D-12.15` 12. Core Runtime Components > 12.15 MCP Server
- `D-19.9` 19. CLI Specification > 19.9 `agentspec mcp serve`
- `D-20` 20. MCP Tool Specification
- `D-20.1` 20. MCP Tool Specification > 20.1 `get_project_status`
- `D-20.2` 20. MCP Tool Specification > 20.2 `list_requirements`
- `D-20.3` 20. MCP Tool Specification > 20.3 `get_requirement`
- `D-20.4` 20. MCP Tool Specification > 20.4 `get_source_section`
- `D-20.5` 20. MCP Tool Specification > 20.5 `search_source_sections`
- `D-20.6` 20. MCP Tool Specification > 20.6 `create_task_context_pack`
- `D-20.7` 20. MCP Tool Specification > 20.7 `get_task_context_pack`
- `D-20.8` 20. MCP Tool Specification > 20.8 `check_diff_against_spec`
- `D-20.9` 20. MCP Tool Specification > 20.9 `update_traceability`
- `D-20.10` 20. MCP Tool Specification > 20.10 `record_agent_finding`
- `D-21` 21. Claude Code Integration
- `D-21.1` 21. Claude Code Integration > 21.1 Project-Local Claude Integration
- `D-21.2` 21. Claude Code Integration > 21.2 Claude Plugin
- `D-21.3` 21. Claude Code Integration > 21.3 Claude Role Rules
- `D-22` 22. Codex Integration
- `D-22.1` 22. Codex Integration > 22.1 Project-Local Codex Integration
- `D-22.2` 22. Codex Integration > 22.2 Codex Plugin
- `D-22.3` 22. Codex Integration > 22.3 Codex Role Rules
- `D-26` 26. Plugin Strategy
- `D-26.1` 26. Plugin Strategy > 26.1 Core Before Plugins
- `D-26.2` 26. Plugin Strategy > 26.2 Why Plugins Still Matter
- `D-26.3` 26. Plugin Strategy > 26.3 Recommended Sequence
- `D-28.8` 28. Rollout Plan > Phase 7: MCP Server
- `D-28.9` 28. Rollout Plan > Phase 8: Plugins

## Source-Backed Notes

### D-10.3 10.3 MCP Server

Source-backed.

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

### D-10.4 10.4 Claude Code Plugin

Source-backed.

### 10.4 Claude Code Plugin

The Claude Code plugin provides:

- slash-command-like skills
- specialized subagents
- hooks for pre-write and post-edit checks
- MCP server configuration
- reusable team distribution

It should be a thin adapter over the CLI and MCP server.

### D-10.5 10.5 Codex Plugin

Source-backed.

### 10.5 Codex Plugin

The Codex plugin provides:

- skills for AgentSpec workflows
- bundled MCP configuration
- optional local marketplace entry
- optional custom agents

It should also be a thin adapter over the CLI and MCP server.

### D-12.15 12.15 MCP Server

Source-backed.

### 12.15 MCP Server

Responsible for exposing AgentSpec project context and actions to code agents.

### D-19.9 19.9 `agentspec mcp serve`

Source-backed.

### 19.9 `agentspec mcp serve`

Starts the MCP server.

```bash
agentspec mcp serve --stdio
agentspec mcp serve --http :8765
```

---

### D-20 20. MCP Tool Specification

Source-backed.

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

### D-20.1 20.1 `get_project_status`

Source-backed.

### 20.1 `get_project_status`

Returns readiness, current requirements summary, open questions, active tasks, and traceability health.

### D-20.2 20.2 `list_requirements`

Source-backed.

### 20.2 `list_requirements`

Filters by status, priority, source section, code target, or task.

### D-20.3 20.3 `get_requirement`

Source-backed.

### 20.3 `get_requirement`

Returns requirement details and linked source sections.

### D-20.4 20.4 `get_source_section`

Source-backed.

### 20.4 `get_source_section`

Returns canonical source section text and metadata.

### D-20.5 20.5 `search_source_sections`

Source-backed.

### 20.5 `search_source_sections`

Semantic or keyword search over source sections. V1 can be keyword-only.

### D-20.6 20.6 `create_task_context_pack`

Source-backed.

### 20.6 `create_task_context_pack`

Creates a task pack from one or more requirements.
