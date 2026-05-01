# AgentSpec Codex Plugin

This plugin packages Codex skills for AgentSpec workflows:

- project status
- spec compile
- task creation
- drift review
- manual or host-provided source intake

The first plugin source workflow is manual or host-provided source intake: a
user or host connector provides a local export, and the skill routes it through
the core `aspec intake` candidate workflow.

The plugin is a thin adapter. It does not fetch Confluence or Jira directly,
store connector credentials, parse sources, diff candidates, or promote
accepted snapshots.
