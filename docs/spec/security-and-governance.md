# Security And Governance

Status: draft
Confidence: medium

## Source Sections

- `D-12.17` 12. Core Runtime Components > 12.17 Policy Engine
- `D-23` 23. Security and Governance
- `D-23.1` 23. Security and Governance > 23.1 Source Classification
- `D-23.2` 23. Security and Governance > 23.2 Storage Modes
- `D-23.3` 23. Security and Governance > 23.3 Prompt Injection Defense
- `D-23.4` 23. Security and Governance > 23.4 Automation Permissions
- `D-23.5` 23. Security and Governance > 23.5 Secret Handling
- `D-23.6` 23. Security and Governance > 23.6 Audit

## Source-Backed Notes

### D-12.17 12.17 Policy Engine

Source-backed.

### 12.17 Policy Engine

Responsible for applying organization-specific rules:

- required reviewers
- allowed automation modes
- source classification rules
- secret handling
- permitted MCP servers
- required tests
- required ADRs

---

### D-23 23. Security and Governance

Source-backed.

## 23. Security and Governance

### 23.1 Source Classification

Every source document and section has a classification:

- public
- internal
- confidential
- restricted

Classification affects:

- whether content can be committed
- whether content can be sent to external models
- whether content can appear in task context packs
- whether automation can run on it
- retention and audit behavior

### 23.2 Storage Modes

| Mode | Description | Use Case |
|---|---|---|
| committed | source text is committed to repo | public/internal docs |
| local-secure-cache | encrypted local cache; repo stores hash | confidential docs |
| enterprise-object-store | snapshot stored in internal object store | enterprise systems |
| pointer-only | repo stores URI and hash only | restricted docs |

### 23.3 Prompt Injection Defense

AgentSpec must treat source documents, repository comments, issues, and retrieved enterprise content as untrusted data. Generated task context packs should delimit source content and never turn retrieved text into system-level instructions.

### 23.4 Automation Permissions

Default automation is read-only.

Write-capable jobs require:

- explicit label or manual trigger
- task

...

### D-23.1 23.1 Source Classification

Source-backed.

### 23.1 Source Classification

Every source document and section has a classification:

- public
- internal
- confidential
- restricted

Classification affects:

- whether content can be committed
- whether content can be sent to external models
- whether content can appear in task context packs
- whether automation can run on it
- retention and audit behavior

### D-23.2 23.2 Storage Modes

Source-backed.

### 23.2 Storage Modes

| Mode | Description | Use Case |
|---|---|---|
| committed | source text is committed to repo | public/internal docs |
| local-secure-cache | encrypted local cache; repo stores hash | confidential docs |
| enterprise-object-store | snapshot stored in internal object store | enterprise systems |
| pointer-only | repo stores URI and hash only | restricted docs |

### D-23.3 23.3 Prompt Injection Defense

Source-backed.

### 23.3 Prompt Injection Defense

AgentSpec must treat source documents, repository comments, issues, and retrieved enterprise content as untrusted data. Generated task context packs should delimit source content and never turn retrieved text into system-level instructions.

### D-23.4 23.4 Automation Permissions

Source-backed.

### 23.4 Automation Permissions

Default automation is read-only.

Write-capable jobs require:

- explicit label or manual trigger
- task context pack
- allowed paths
- branch isolation
- no secrets in agent environment
- structured proposed output
- output validation
- human review
- no auto-merge by default

### D-23.5 23.5 Secret Handling

Source-backed.

### 23.5 Secret Handling

Task context packs must exclude secrets. Repo scanning should detect likely secrets and redact them in reports.

### D-23.6 23.6 Audit

Source-backed.

### 23.6 Audit

AgentSpec should record:

- source snapshots
- generated artifact versions
- task creation events
- agent findings
- drift reviews
- assumption promotions
- ADR decisions
- automation runs

V1 can record audit events in JSONL files under `agent/runs/`.

---
