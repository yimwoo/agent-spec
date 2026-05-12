# Implementation Disciplines

Worker guidance is code-agent-only package material, not a public human skill.
Controllers may attach these disciplines to run packages or child assignments:

- incremental implementation for multi-file features and refactors
- test-driven development for new behavior and bug fixes
- debugging and error recovery for failing tests or unexplained runtime issues
- source-driven development for unfamiliar frameworks, libraries, or APIs
- security and hardening for auth, secrets, PII, payments, and integrations

Every worker package must include the task id, requirement ids, allowed paths,
verification commands, expected evidence, and result reporting requirements.

