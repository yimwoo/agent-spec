# ADR-0001: Core CLI And File Artifacts Before Plugins

Status: accepted

## Context

AgentSpec needs durable, vendor-neutral project memory before tool-specific integrations can be reliable.

## Decision

Build a local CLI and repository artifact model first. Claude, Codex, MCP, and automation integrations are adapters over the same core.

## Consequences

- Generated files remain useful without a hosted runtime.
- Plugins should be thin wrappers over the CLI and shared schemas.
