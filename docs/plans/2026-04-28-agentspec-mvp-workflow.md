---
intent: Implement the first useful AgentSpec CLI milestone from the supplied product design.
success_criteria:
  - Local CLI supports init, Markdown ingest, compile, readiness, task create, emit, doctor, and drift skeleton workflows.
  - Generated artifacts use source-section references, hashes, requirements, assumptions, open questions, and context packs.
  - Automated tests cover the core sectionizer and end-to-end CLI workflow.
risk_level: medium
auto_approve: true
worktree: host
dirty_worktree: allow
---

## Steps

- [ ] **Step 1: Add failing workflow tests**
action: Create tests for Markdown section IDs/hashes and the first milestone CLI flow.
loop: false
verify: python -m unittest discover -s tests -v
gate: auto

- [ ] **Step 2: Scaffold Python package and CLI**
action: Add project metadata, package modules, command parsing, artifact layout helpers, and durable data IO.
loop: until tests pass
max_iterations: 4
verify: python -m unittest discover -s tests -v
gate: auto

- [ ] **Step 3: Implement ingest and compile**
action: Implement Markdown snapshotting, heading sectionization, deterministic hashes, requirements extraction, readiness scoring, and spec shard generation.
loop: until tests pass
max_iterations: 4
verify: python -m unittest discover -s tests -v
gate: auto

- [ ] **Step 4: Implement task packs, emitters, doctor, and drift skeleton**
action: Add context pack generation, agent instruction emitters, read-only repo scanner, and a CI-ready drift report skeleton.
loop: until tests pass
max_iterations: 4
verify: python -m unittest discover -s tests -v
gate: auto

- [ ] **Step 5: Dogfood with the supplied design doc**
action: Run the CLI against the supplied AgentSpec design document in this repository and inspect generated artifacts.
loop: until successful
max_iterations: 3
verify:
  - type: shell
    command: python -m unittest discover -s tests -v
  - type: shell
    command: python -m agentspec.cli --help
gate: auto
