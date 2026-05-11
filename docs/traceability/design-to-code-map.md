# Design To Code Map

| Requirement | Source Sections | Code Targets | Tests |
|---|---|---|---|
| `R-001` An architect agent, PM agent, developer agent, or reviewer agent must not become the sole source | D-02 | agentspec/compile.py, agentspec/emit.py, agentspec/markdown.py, agentspec/task.py | tests/test_markdown_sectionizer.py |
| `R-002` Convert a Markdown design document into canonical source sections with stable IDs and content ha | D-03 | agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-003` Generate a draft project canvas, spec shards, requirements, assumptions, open questions, and tas | D-03 | agentspec/compile.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-004` Support sparse input and empty repositories through Discovery Mode instead of fabricating certai | D-03 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-005` Support existing repositories through Brownfield Doctor mode | D-03 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-006` Generate AGENTS.md, CLAUDE.md, Claude Code subagents, Codex agents, and reusable role definition | D-03 | agentspec/emit.py, agentspec/init.py | tests/test_cli_workflow.py |
| `R-007` Provide a CLI that can run locally and in CI | D-03 | agentspec/cli.py | tests/test_cli_workflow.py |
| `R-008` Provide a validation model for requirements, task context packs, and traceability files | D-03 | agentspec/compile.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-009` Generate implementation tasks only when the relevant requirements are sufficiently specified | D-03 | agentspec/compile.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-010` Detect design drift in a code diff by comparing changed files against requirements, ADRs, and ta | D-03 | agentspec/compile.py, agentspec/drift.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-011` Provide an AgentSpec MCP server for code agents | D-03 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-012` Provide Claude Code and Codex plugins as thin adapters over the core CLI and MCP server | D-03 | agentspec/cli.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-013` Generate GitHub Agentic Workflows or GitHub Actions for scheduled read-only audits and agent-saf | D-03 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-014` Support repository-wide traceability reports and test gap reports | D-03 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-015` Support large brownfield migrations with safe task partitioning | D-03 | agentspec/doctor.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-016` Support organization-wide policy packs | D-03 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-017` not implement a general-purpose autonomous coding agent | D-03 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-018` not require a hosted service | D-03 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-019` not require enterprise connectors for the first release | D-03 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-020` A user should be able to run the following on a fresh repository: | D-04 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-021` agentspec task create --requirement R-001 | D-04 | agentspec/compile.py, agentspec/emit.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-022` agentspec emit --target claude,codex | D-04 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-023` After that, the repository should contain enough durable context for a code agent to start work  | D-04 | agentspec/doctor.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-024` A tech lead owns a design document and wants multiple developers or code agents to implement it  | D-05 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-025` The snapshot makes code-agent behavior reproducible. A task created today should remain auditabl | D-06 | agentspec/emit.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-026` A spec shard must cite source sections and declare whether its content is source-backed, inferre | D-06 | agentspec/compile.py, agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-027` Assumptions must be explicit. They can be accepted, rejected, superseded, or left unconfirmed. P | D-06 | agentspec/task.py | tests/test_cli_workflow.py |
| `R-028` Not every drift is wrong. Some drift is a valid design evolution. But it must be explicit and us | D-06 | agentspec/drift.py | tests/test_cli_workflow.py |
| `R-029` 6.8 Task Context Pack | D-06.8 | agentspec/task.py | tests/test_cli_workflow.py |
| `R-030` 6.10 Design Drift | D-06.10 | agentspec/drift.py | tests/test_cli_workflow.py |
| `R-031` One writer by default. Multiple reviewers are encouraged; multiple concurrent writers require ex | D-07 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-032` Generator-verifier for quality-critical artifacts. Spec compilation, requirements, drift reviews | D-07 | agentspec/compile.py, agentspec/drift.py | tests/test_cli_workflow.py |
| `R-033` Message bus later, not first. Event-driven agent ecosystems are useful for automation, but V1 sh | D-07 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-034` Brownfield first-class. Existing projects are not broken greenfield projects. Assessment must be | D-07 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-035` Dogfood early. AgentSpec must be able to scaffold, plan, review, and improve its own repository | D-07 | agentspec/compile.py, agentspec/doctor.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-036` Policy is data. Organization-specific rules should be represented as versioned policy packs, not | D-07 | agentspec/compile.py | tests/test_cli_workflow.py |
| `R-037` use agentic design, but it should not become an unconstrained multi-agent swarm | D-08 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-038` The verifier must use explicit criteria. A generic instruction such as "check if this is good" i | D-08 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-039` concurrent writes require locking or branch isolation | D-08 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-040` high-impact changes require ADRs | D-08 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-041` V1 should not start with a full message bus. It should emit GitHub workflows or CI jobs. A real  | D-08 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-042` Agent teams are dangerous when workers edit shared files or depend on one another's findings. Ag | D-08 | agentspec/compile.py, agentspec/emit.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-043` agentspec emit --target claude | D-10 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-044` agentspec emit --target codex | D-10 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-045` It should expose tools such as: | D-10 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-046` It should be a thin adapter over the CLI and MCP server | D-10 | agentspec/cli.py | tests/test_cli_workflow.py |
| `R-047` It should also be a thin adapter over the CLI and MCP server | D-10 | agentspec/cli.py | tests/test_cli_workflow.py |
| `R-048` generate workflow templates for: | D-10 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-049` V1 can emit standard GitHub Actions. V2 can emit GitHub Agentic Workflows where appropriate | D-10 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-050` 10.2 CLI | D-10.2 | agentspec/cli.py | tests/test_cli_workflow.py |
| `R-051` 10.3 MCP Server | D-10.3 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-052` generate implementation tasks | D-11 | agentspec/task.py | tests/test_cli_workflow.py |
| `R-053` generate agent configs | D-11 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-054` create project canvas | D-11 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-055` create assumptions ledger | D-11 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-056` create open questions | D-11 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-057` generate draft spec | D-11 | agentspec/compile.py | tests/test_cli_workflow.py |
| `R-058` compute readiness score | D-11 | agentspec/compile.py | tests/test_cli_workflow.py |
| `R-059` generate discovery, spike, and scaffold tasks only | D-11 | agentspec/task.py | tests/test_cli_workflow.py |
| `R-060` detect language, frameworks, tests, CI, package managers | D-11 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-061` 11.3 Brownfield Doctor Mode | D-11.3 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-062` Responsible for command parsing, configuration loading, output formatting, and local execution o | D-12 | agentspec/cli.py | tests/test_cli_workflow.py |
| `R-063` Responsible for importing design sources: | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-064` Responsible for provenance: | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-065` Responsible for turning source documents into stable sections | D-12 | agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-066` parse heading hierarchy | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-067` compute section content hashes | D-12 | agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-068` detect duplicate headings | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-069` Responsible for generating spec shards from source sections | D-12 | agentspec/compile.py, agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-070` The compiler may use LLM assistance, but the output must mark each paragraph or requirement as: | D-12 | agentspec/compile.py | tests/test_cli_workflow.py |
| `R-071` Responsible for extracting requirements with status, priority, source references, acceptance cri | D-12 | agentspec/compile.py | tests/test_cli_workflow.py |
| `R-072` Responsible for managing assumptions: | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-073` Responsible for managing missing decisions and facts | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-074` Responsible for evaluating whether the project is ready for implementation | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-075` Responsible for reading existing codebases: | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-076` Responsible for mapping: | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-077` Responsible for building task-bounded context: | D-12 | agentspec/task.py | tests/test_cli_workflow.py |
| `R-078` include adjacent sections where needed | D-12 | agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-079` include accepted requirements and assumptions | D-12 | agentspec/compile.py | tests/test_cli_workflow.py |
| `R-080` include open questions and non-goals | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-081` include allowed/forbidden paths | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-082` include relevant code and tests | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-083` Responsible for comparing diffs against requirements, ADRs, allowed paths, tests, and security p | D-12 | agentspec/compile.py, agentspec/drift.py | tests/test_cli_workflow.py |
| `R-084` Responsible for generating: | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-085` Responsible for exposing AgentSpec project context and actions to code agents | D-12 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-086` Responsible for generating scheduled and event-triggered workflows | D-12 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-087` Responsible for applying organization-specific rules: | D-12 | agentspec/compile.py | tests/test_cli_workflow.py |
| `R-088` 12.1 CLI Application | D-12.1 | agentspec/cli.py | tests/test_cli_workflow.py |
| `R-089` 12.4 Sectionizer | D-12.4 | agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-090` 12.12 Context Pack Builder | D-12.12 | agentspec/task.py | tests/test_cli_workflow.py |
| `R-091` 12.13 Drift Checker | D-12.13 | agentspec/drift.py | tests/test_cli_workflow.py |
| `R-092` 12.14 Agent Config Emitters | D-12.14 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-093` 12.15 MCP Server | D-12.15 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-094` 12.16 Automation Emitter | D-12.16 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-095` title: Every implementation task must have a task context pack | D-13 | agentspec/task.py | tests/test_cli_workflow.py |
| `R-096` question: Should AgentSpec store enterprise source snapshots in git, local encrypted cache, or o | D-13 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-097` title: Implement context pack builder | D-13 | agentspec/task.py | tests/test_cli_workflow.py |
| `R-098` Do not implement Claude or Codex emitters | D-13 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-099` context: AgentSpec must support multiple code agents | D-13 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-100` decision: Build vendor-neutral core first; implement plugins as adapters | D-13 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-101` implement-feature.md | D-14 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-102` Many users will not provide a complete design document. They may provide: | D-15 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-103` not generate false certainty from thin input | D-15 | agentspec/compile.py, agentspec/emit.py | tests/test_cli_workflow.py |
| `R-104` It must not generate production implementation tasks until readiness gates pass or the user expl | D-15 | agentspec/compile.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-105` Brownfield Doctor Design | D-16 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-106` The first brownfield pass must not modify production code | D-16 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-107` For weakly documented projects, AgentSpec should create tasks such as: | D-16 | agentspec/compile.py, agentspec/emit.py, agentspec/task.py | tests/test_cli_workflow.py |
| `R-108` create AGENTS.md and CLAUDE.md | D-16 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-109` create traceability placeholders | D-16 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-110` Major refactors require accepted ADRs | D-16 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-111` -> create repo artifact layout | D-18 | agentspec/doctor.py, agentspec/init.py | tests/test_cli_workflow.py |
| `R-112` -> create default config | D-18 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-113` -> create AGENTS.md and CLAUDE.md skeletons | D-18 | agentspec/emit.py | tests/test_cli_workflow.py |
| `R-114` -> create discovery files | D-18 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-115` -> create role definitions | D-18 | agentspec/init.py | tests/test_cli_workflow.py |
| `R-116` -> parse headings | D-18 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-117` -> generate source sections | D-18 | agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-118` -> compute section hashes | D-18 | agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-119` -> include source sections | D-18 | agentspec/markdown.py | tests/test_markdown_sectionizer.py |
| `R-120` -> include accepted assumptions | D-18 | docs/traceability/requirements.yml | tests/test_cli_workflow.py |
| `R-121` Capture every post-implementation design change as a DCR before downstream artifacts change | D-03, D-11.4 | agentspec/init.py, agentspec/dcr.py, agentspec/task.py | tests/test_dcr_schema.py, tests/test_task_originating_dcr.py |
| `R-122` DCR carries one of five classifications | D-11.4, D-18 | agentspec/dcr.py | tests/test_dcr_schema.py |
| `R-123` DCR-derived context packs cite the DCR and require an implementation-eligible state | D-12.12, D-11.4 | agentspec/task.py, agentspec/dcr.py | tests/test_task_originating_dcr.py |
| `R-124` DCR-introduced requirements use status proposed-pending-acceptance | D-12.5, D-18 | agentspec/compile.py, agentspec/dcr.py | tests/test_dcr_schema.py, tests/test_cli_workflow.py |
| `R-125` CLI provides agentspec dcr create / classify / accept / list | D-12.1, D-19 | agentspec/cli.py, agentspec/dcr.py | tests/test_cli_workflow.py |
| `R-126` Drift checker recognizes DCR-derived files and surfaces the DCR ID | D-12.13, D-11.4 | agentspec/drift.py | tests/test_drift.py |
| `R-127` Bounded supervised run executes one context pack with iteration cap and allowed-paths enforcement | D-07, D-12.12, D-12.17, D-23.4 | agentspec/run.py, agentspec/cli.py | tests/test_supervised_run.py |
| `R-128` Supervised run records per-iteration evidence in agent/runs/ JSONL | D-23.6, D-24 | agentspec/run.py, agentspec/io.py | tests/test_supervised_run.py |
| `R-129` Reviewer model produces structured feedback consumable by next iteration | D-07 | agentspec/review.py, agentspec/run.py | tests/test_supervised_run.py |
| `R-130` Supervised run halts and requires human approval for risky changes | D-12.17, D-23.4 | agentspec/run.py, agentspec/policy.py | tests/test_supervised_run.py |
| `R-131` agentspec compile preserves DCR-originated artifacts when regenerating | D-12.5, D-11.4, D-18 | agentspec/compile.py | tests/test_compile_preserves_dcr_material.py |
| `R-132` agentspec compile fails loudly when reconciliation is impossible | D-12.5, D-07 | agentspec/compile.py | tests/test_compile_preserves_dcr_material.py |
| `R-133` agentspec dcr accept flips only the DCR status, not requirement statuses | D-11.4, D-12.1 | agentspec/dcr.py, agentspec/cli.py | tests/test_dcr_cli.py |
| `R-134` agentspec requirement accept R-XXX flips a single proposed-pending-acceptance requirement | D-12.1, D-18 | agentspec/requirement.py, agentspec/cli.py | tests/test_requirement_cli.py |
| `R-135` Autonomous execution profile transforms pause_for_human into blocked findings | D-07, D-12.17, D-23.4 | agentspec/run.py, agentspec/policy.py, agentspec/cli.py, agentspec/init.py | tests/test_supervised_run.py, tests/test_autonomous_mode.py |
| `R-136` Repository-aware code and test target inference | D-12.5, D-12.10, D-12.12 | agentspec/compile.py, agentspec/task.py, agentspec/doctor.py | tests/test_target_inference.py |
| `R-137` Context-pack allowed-path validation distinguishes inferred from confirmed scope | D-12.12, D-23.4 | agentspec/task.py, agentspec/run.py | tests/test_task_originating_dcr.py, tests/test_supervised_run.py |
| `R-138` aspec is installed on PATH via [project.scripts] console entry point | D-12.1, D-19 | pyproject.toml | tests/test_cli_alias.py |
| `R-139` Dogfood notes have a durable artifact location | D-11.4, D-24 | agentspec/init.py, agentspec/paths.py, agentspec/cli.py | tests/test_init_layout.py |
| `R-140` aspec init emits .gitignore guidance for agent/runs/* while preserving .gitkeep | D-23.6 | agentspec/init.py | tests/test_init_layout.py |
| `R-141` Context-pack title truncation respects word boundaries | D-12.12 | agentspec/task.py, agentspec/paths.py | tests/test_task_originating_dcr.py |
| `R-142` Autonomous run supports a research fallback when no executable pack is ready | D-07, D-11.4, D-23.4 | agentspec/run.py, agentspec/policy.py, agentspec/cli.py | tests/test_autonomous_mode.py |
| `R-143` Reviewer classifies pause_for_human severity (minor vs high) and autonomous mode acts on it | D-07, D-12.17 | agentspec/review.py, agentspec/model_review.py, agentspec/run.py | tests/test_autonomous_mode.py, tests/test_model_review.py |
| `R-144` Autonomous-mode complete requires both continuation_reviewer and quality_reviewer signoff | D-07 | agentspec/run.py, agentspec/review.py | tests/test_autonomous_mode.py |
| `R-145` Globstar path matching is shared by policy and drift | D-12.13, D-12.17, D-23.4 | agentspec/paths.py, agentspec/policy.py, agentspec/drift.py | tests/test_glob_semantics.py |
| `R-146` Run completion is atomic and respects the research-mode write surface | D-07, D-23.4, D-23.6 | agentspec/run.py | tests/test_run_completion_atomicity.py |
| `R-147` Candidate source snapshots do not change accepted compile inputs | D-12.3, D-12.5, D-23.6 | agentspec/intake.py, agentspec/cli.py | tests/test_intake_candidate.py |
| `R-148` External sources normalize into a validated SpecDocument schema | D-12.4, D-12.5, D-12.6 | agentspec/spec_document.py, agentspec/intake.py, agentspec/cli.py | tests/test_spec_document.py, tests/test_intake_candidate.py |
| `R-149` Candidate snapshots produce reviewable baseline diffs | D-12.13, D-23.6 | agentspec/intake.py, agentspec/cli.py | tests/test_intake_diff.py |
| `R-150` Candidate promotion requires human approval | D-23.4, D-23.6 | agentspec/intake.py, agentspec/cli.py, agentspec/policy.py | tests/test_intake_promotion.py |
| `R-151` Promotion preserves source snapshot lineage | D-06, D-12.3, D-23.6 | agentspec/intake.py, agentspec/compile.py | tests/test_intake_promotion.py, tests/test_compile_preserves_dcr_material.py |
| `R-152` Intake enforces source storage modes | D-23.1, D-23.2, D-23.3 | agentspec/intake.py, agentspec/spec_document.py, agentspec/policy.py | tests/test_intake_storage.py |
| `R-153` Structured API sources produce contract diffs | D-12.5, D-12.13 | agentspec/spec_document.py, agentspec/intake.py | tests/test_openapi_intake.py |
| `R-154` Enterprise connectors are adapters over candidate snapshots | D-03, D-12.15, D-28.11 | agentspec/connectors/, agentspec/intake.py, agentspec/cli.py | tests/test_enterprise_connectors.py |
| `R-155` AgentSpec stores a source registry for external source identities | D-03, D-12.1, D-12.5, D-23.6 | agentspec/source_registry.py, agentspec/cli.py, docs/source/source-registry.yml, README.md | tests/test_source_registry.py |
| `R-156` Registered source drift checks are read-only by default | D-12.1, D-12.13, D-23.4, D-23.6 | agentspec/source_registry.py, agentspec/cli.py, agentspec/connectors/, agentspec/intake.py | tests/test_source_drift.py |
| `R-157` Changed registered sources produce candidate evidence on request | D-12.3, D-12.13, D-23.6 | agentspec/source_registry.py, agentspec/intake.py, agentspec/cli.py | tests/test_source_drift.py |
| `R-158` Scheduled source drift checks are CI-friendly | D-03, D-12.16, D-23.4, D-28.11 | agentspec/source_registry.py, agentspec/cli.py, README.md | tests/test_source_drift.py, tests/test_source_registry.py |
| `R-159` Run state storage can be redirected | D-23.6 | agentspec/run.py, agentspec/cli.py, agentspec/io.py | tests/test_run_dir.py |
| `R-160` Run subcommands share redirected state consistently | D-23.6 | agentspec/run.py, agentspec/runner.py, agentspec/cli.py | tests/test_run_dir.py, tests/test_runner_package.py |
| `R-161` Default run-state behavior and JSON failures stay stable | D-23.6 | agentspec/run.py, agentspec/cli.py, agentspec/io.py | tests/test_run_dir.py, tests/test_cli_json_errors.py |
| `R-162` Research mode reports remaining target write requirements | D-23.4, D-23.6 | agentspec/run.py, agentspec/cli.py | tests/test_run_dir.py, tests/test_research_mode.py |
| `R-163` Run status records carry recovery context | D-23.6, D-24 | agentspec/status.py | tests/test_status_cli.py |
| `R-164` Plugin source intake routes manual content through core intake | D-03.2, D-10.4, D-10.5, D-20.6, D-21.2, D-22.2, D-26.1, D-26.2, D-26.3 | agentspec/emit.py, agentspec/cli.py, agentspec/intake.py, agentspec-codex-plugin/** | tests/test_cli_workflow.py, tests/test_intake_candidate.py, tests/test_plugin_source_intake.py |
| `R-165` Codex plugin documents init and continue workflows | D-03.2, D-10.5, D-22.2, D-26.1, D-26.2, D-26.3 | agentspec-codex-plugin/** | tests/test_plugin_source_intake.py |
| `R-166` Codex dogfooding uses plugin skill surface | D-03.2, D-10.5, D-22.2, D-26.1, D-26.2, D-26.3 | agentspec/emit.py, agentspec/paths.py, .agents/skills/** | tests/test_plugin_source_intake.py |
| `R-167` Codex plugin uses short aspec skill prefix | D-03.2, D-10.5, D-22.2, D-26.1, D-26.2, D-26.3 | agentspec-codex-plugin/** | tests/test_plugin_source_intake.py |
| `R-168` Codex plugin documents dogfood recovery guidance | D-03.2, D-10.5, D-22.2, D-26.1, D-26.2, D-26.3 | agentspec-codex-plugin/skills/init-project/SKILL.md, agentspec-codex-plugin/skills/manual-source-intake/SKILL.md | tests/test_plugin_source_intake.py |
| `R-169` CLI exposes recovery-oriented next-action aliases | D-10.2, D-23.6, D-24 | agentspec/cli.py | tests/test_status_cli.py |
| `R-170` Pre-commit code-review evidence gate | D-10.2, D-23.6, D-24 | AGENTS.md, agentspec/cli.py, agentspec/review.py, agentspec/run.py, agentspec/task.py | tests/test_code_review_cli.py, tests/test_task_completion.py |
| `R-171` Research mode review evidence contract spike | D-07, D-12.17, D-23.4, D-24 | docs/discovery/spikes/research-mode-review-evidence-contract.md | tests/test_research_mode.py, tests/test_runner_package.py |
| `R-172` Research-mode acceptance evidence contract | D-07, D-12.17, D-23.4, D-24 | agentspec/runner.py, agentspec/run.py, agentspec/review.py | tests/test_runner_package.py, tests/test_research_mode.py |
| `R-173` Codex agent role emission uses developer_instructions | D-10.5, D-22.2, D-26.1, D-26.2, D-26.3 | agentspec/emit.py | tests/test_plugin_source_intake.py |
| `R-174` Doctor reports stale generated agent instruction artifacts | D-03, D-04, D-24 | agentspec/doctor.py | tests/test_cli_workflow.py |
| `R-175` Runner results support structured UI validation evidence artifacts | D-07, D-12.17, D-23.6, D-24 | agentspec/runner.py, agentspec/run.py | tests/test_runner_package.py |
| `R-176` Doctor evaluates repo-local project invariants | D-07, D-12.17, D-24 | agentspec/doctor.py, agentspec/policy.py | tests/test_cli_workflow.py |
| `R-177` Doctor diagnostics are complete and non-fatal for generated agent context and project invariants | D-07, D-12.17, D-24 | agentspec/doctor.py, agentspec/policy.py | tests/test_cli_workflow.py |
| `R-178` AgentSpec exposes an app-build planner/generator/evaluator harness and configurable test-eval reviewer profile | D-07, D-10.5, D-12.14, D-12.17, D-23.6, D-24 | agentspec/config.py, agentspec/emit.py, agentspec/init.py, agentspec/model_review.py, agentspec/paths.py, agentspec/run.py, agentspec/review.py | tests/test_config_profiles.py, tests/test_dual_reviewer_signoff.py, tests/test_init_layout.py, tests/test_model_review.py |
| `R-179` AgentSpec dogfood config uses the test-eval reviewer profile | D-07, D-12.17, D-23.6, D-24 | .agentspec/config.yml | tests/test_config_profiles.py, tests/test_dual_reviewer_signoff.py |
| `R-180` Answered open questions cite accepted decision evidence | D-07, D-23.6, D-24 | docs/discovery/open-questions.yml |  |
| `R-181` Local Codex runtime config is ignored while generated Codex agent roles stay trackable | D-07, D-23.6, D-24 | .gitignore |  |
| `R-182` Task packs include verification support scope and completion writes handoff state | D-03, D-07, D-12.12, D-23.6, D-24 | agentspec/task.py, agentspec/run.py, agentspec/status.py, agentspec/handoff.py, docs/discovery/open-questions.yml | tests/test_task_queue.py, tests/test_task_completion.py, tests/test_task_ledger.py, tests/test_status_cli.py |
| `R-183` AgentSpec exposes a recurring quality GC scan | D-03, D-07, D-23.6, D-24 | agentspec/cli.py, agentspec/quality.py, agentspec/paths.py, agentspec/init.py, agentspec/emit.py, .gitignore | tests/test_quality_gc.py, tests/test_init_layout.py, tests/test_cli_workflow.py |
| `R-184` Task completion can run Quality GC when configured cadence is due | D-03, D-07, D-23.6, D-24 | agentspec/config.py, agentspec/run.py, agentspec/quality.py, .agentspec/config.yml | tests/test_config_profiles.py, tests/test_task_completion.py, tests/test_quality_gc.py |
| `R-185` Next stale answered open questions cite accepted decision evidence | D-07, D-23.6, D-24 | docs/discovery/open-questions.yml |  |
| `R-186` Generated agent context stays current and project invariants are configured | D-07, D-23.6, D-24 | agentspec/emit.py, AGENTS.md, CLAUDE.md, .claude/agents/*.md, .claude/skills/**/SKILL.md, .codex/agents/*.toml, agent/roles/*.md, agent/policies/invariants.yml, reports/quality/latest.yml, reports/quality/latest.md | tests/test_cli_workflow.py |
| `R-187` AgentSpec exposes a read-only project metrics surface | D-07, D-23.6, D-24 | agentspec/cli.py, agentspec/metrics.py, agentspec/status.py | tests/test_metrics_cli.py |
| `R-188` First implementation language question is answered | D-30 | docs/discovery/open-questions.yml |  |
| `R-189` Claude Code plugin package mirrors AgentSpec workflow skills | D-03.2, D-10.4, D-21.2, D-26.1, D-26.2, D-26.3 | agentspec-claude-plugin/** | tests/test_claude_code_plugin.py |
| `R-190` AgentSpec exposes product outcome gates and unified lifecycle skills | D-03.2, D-26.1, D-26.2, D-26.3 | agentspec/outcome.py, agentspec/cli.py, agentspec/status.py, agentspec/quality.py, agentspec/init.py, agentspec/paths.py, agentspec/emit.py, agentspec-codex-plugin/skills/**/SKILL.md, agentspec-claude-plugin/skills/**/SKILL.md | tests/test_outcome_cli.py, tests/test_cli_workflow.py, tests/test_quality_gc.py, tests/test_claude_code_plugin.py |
| `R-191` AgentSpec records multi-session worktree leases | D-03.2, D-26.1, D-26.2, D-26.3 | agentspec/session.py, agentspec/cli.py, agentspec/status.py, agentspec/init.py, agentspec/paths.py | tests/test_session_cli.py, tests/test_cli_workflow.py |
| `R-192` AgentSpec supports progressive maturity profiles | D-03.2, D-26.1, D-26.2, D-26.3 | agentspec/maturity.py, agentspec/cli.py, agentspec/status.py, agentspec/init.py | tests/test_maturity_cli.py, tests/test_cli_workflow.py |
| `R-193` AgentSpec enforces workflow-pack coverage and generated roadmap status | D-03.2, D-06.8, D-06.10, D-12.12, D-12.13 | agentspec/workflow.py, agentspec/roadmap.py, agentspec/drift.py, agentspec/task.py, agentspec/status.py, agentspec/cli.py, agentspec/init.py, agentspec-codex-plugin/skills/**/SKILL.md, agentspec-claude-plugin/skills/**/SKILL.md | tests/test_workflow_contract.py, tests/test_task_queue.py, tests/test_status_cli.py, tests/test_cli_workflow.py, tests/test_claude_code_plugin.py |
| `R-194` AgentSpec exposes lifecycle projection and write-back readiness | lifecycle-engine-hardening-design:D-13, lifecycle-engine-hardening-design:D-16, lifecycle-engine-hardening-design:D-17, lifecycle-engine-hardening-design:D-20.1, lifecycle-engine-hardening-design:D-21 | agentspec/status.py, agentspec/workflow.py, agentspec/drift.py, agentspec/roadmap.py, agentspec/task.py, agentspec/handoff.py, agentspec/writeback.py | tests/test_status_cli.py, tests/test_task_queue.py, tests/test_workflow_contract.py, tests/test_cli_workflow.py |
