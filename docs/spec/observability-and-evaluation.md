# Observability And Evaluation

Status: draft
Confidence: medium

## Source Sections

- `D-04.2` 4. Success Criteria > 4.2 Quality Success Criteria
- `D-24` 24. Observability and Evaluation
- `D-24.1` 24. Observability and Evaluation > 24.1 Runtime Metrics
- `D-24.2` 24. Observability and Evaluation > 24.2 Quality Metrics
- `D-24.3` 24. Observability and Evaluation > 24.3 Dogfood Metrics
- `D-24.4` 24. Observability and Evaluation > 24.4 Golden Fixtures

## Source-Backed Notes

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

### D-24 24. Observability and Evaluation

Source-backed.

## 24. Observability and Evaluation

### 24.1 Runtime Metrics

- number of source documents ingested
- number of source sections generated
- number of requirements extracted
- number of assumptions created
- readiness score
- context packs generated
- drift reviews run
- findings by severity
- traceability coverage
- plugin emitter validation failures

### 24.2 Quality Metrics

- requirements with source references
- accepted requirements depending on unconfirmed assumptions
- tasks missing context packs
- tasks missing tests
- code files without requirement mapping
- requirements without code target
- false positives in drift checker fixture tests
- false negatives in drift checker fixture tests

### 24.3 Dogfood Metrics

- percent of AgentSpec tasks created through AgentSpec
- percent of PRs with drift review
- percent of changes mapped to requirements
- number of ADRs created from drift reviews
- recurring missing-context failures

### 24.4 Golden Fixtures

AgentSpec should maintain fixtures for:

- complete design document
- sparse design document
- empty repository
- small existing repository
- brownfield repository with mismatched docs
- diff that changes module contract
- di

...

### D-24.1 24.1 Runtime Metrics

Source-backed.

### 24.1 Runtime Metrics

- number of source documents ingested
- number of source sections generated
- number of requirements extracted
- number of assumptions created
- readiness score
- context packs generated
- drift reviews run
- findings by severity
- traceability coverage
- plugin emitter validation failures

### D-24.2 24.2 Quality Metrics

Source-backed.

### 24.2 Quality Metrics

- requirements with source references
- accepted requirements depending on unconfirmed assumptions
- tasks missing context packs
- tasks missing tests
- code files without requirement mapping
- requirements without code target
- false positives in drift checker fixture tests
- false negatives in drift checker fixture tests

### D-24.3 24.3 Dogfood Metrics

Source-backed.

### 24.3 Dogfood Metrics

- percent of AgentSpec tasks created through AgentSpec
- percent of PRs with drift review
- percent of changes mapped to requirements
- number of ADRs created from drift reviews
- recurring missing-context failures

### D-24.4 24.4 Golden Fixtures

Source-backed.

### 24.4 Golden Fixtures

AgentSpec should maintain fixtures for:

- complete design document
- sparse design document
- empty repository
- small existing repository
- brownfield repository with mismatched docs
- diff that changes module contract
- diff that requires ADR
- diff that changes tests only
- plugin emitter expected output

---
