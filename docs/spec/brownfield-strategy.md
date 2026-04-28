# Brownfield Strategy

Status: draft
Confidence: medium

## Source Sections

- `D-11.3` 11. Modes of Operation > 11.3 Brownfield Doctor Mode
- `D-12.10` 12. Core Runtime Components > 12.10 Repo Scanner
- `D-16` 16. Brownfield Doctor Design
- `D-16.1` 16. Brownfield Doctor Design > 16.1 Purpose
- `D-16.2` 16. Brownfield Doctor Design > 16.2 Read-Only First
- `D-16.3` 16. Brownfield Doctor Design > 16.3 Repo Scanner Outputs
- `D-16.4` 16. Brownfield Doctor Design > 16.4 First Safe Tasks
- `D-19.5` 19. CLI Specification > 19.5 `agentspec doctor`
- `D-28.5` 28. Rollout Plan > Phase 4: Brownfield Doctor

## Source-Backed Notes

### D-11.3 11.3 Brownfield Doctor Mode

Source-backed.

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

### D-16 16. Brownfield Doctor Design

Source-backed.

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

### D-16.1 16.1 Purpose

Source-backed.

### 16.1 Purpose

Brownfield Doctor helps existing projects adopt AgentSpec without forcing a rewrite.

### D-16.2 16.2 Read-Only First

Source-backed.

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

### D-16.3 16.3 Repo Scanner Outputs

Source-backed.

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

### D-16.4 16.4 First Safe Tasks

Source-backed.

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

### D-19.5 19.5 `agentspec doctor`

Source-backed.

### 19.5 `agentspec doctor`

Runs brownfield assessment.

```bash
agentspec doctor
agentspec doctor --design docs/source/design.md
```

### D-28.5 Phase 4: Brownfield Doctor

Source-backed.

### Phase 4: Brownfield Doctor

Deliverables:

- repo scanner
- language/framework detection
- test command detection
- design-to-code mapping report
- first safe task generator
