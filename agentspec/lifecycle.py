"""AgentSpec lifecycle operating-contract projections and formatting."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .config import load_project_config, merged_runtime_config
from .guidance import POST_ARTIFACT_GUIDANCE_SCHEMA


LIFECYCLE_CONTRACT_SCHEMA = "agentspec.lifecycle_contract.v0"
EXECUTION_STRATEGY_SCHEMA = "agentspec.execution_strategy.v0"


def build_execution_strategy(
    root: Path,
    *,
    provider: str | None = None,
    capabilities: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Select provider-native execution or the portable AgentSpec fallback.

    Args:
        root: AgentSpec project root.
        provider: Optional explicit host provider override.
        capabilities: Optional provider capability availability overrides.

    Returns:
        A structured strategy with the selected path, unavailable host
        capabilities, governance boundaries, and stable fallback contract.
    """

    root = root.resolve()
    resolved_provider = _execution_provider(root, provider)
    native_candidate = _native_execution_candidate(
        resolved_provider,
        capabilities=capabilities or {},
    )
    fallback = {
        "id": "agentspec-runner-fallback",
        "mode": "agentspec_generic_fallback",
        "provider": "generic",
        "mechanism": "runner_package_result",
        "availability": "available",
        "role": "portable fallback when the host-native workflow is unavailable",
        "commands": ["aspec run package", "aspec run result"],
        "compatibility_commands": ["aspec run loop", "aspec run exec"],
    }
    unavailable: list[dict[str, str]] = []
    if native_candidate["availability"] == "unavailable":
        unavailable.append(
            {
                "id": str(native_candidate["capability"]),
                "provider": resolved_provider,
                "reason": str(native_candidate["unavailable_reason"]),
            }
        )
        selected = dict(fallback)
    else:
        selected = {
            key: value
            for key, value in native_candidate.items()
            if key != "unavailable_reason"
        }

    return {
        "schema": EXECUTION_STRATEGY_SCHEMA,
        "preferred_mode": "provider_native",
        "selected": selected,
        "native_candidate": native_candidate,
        "unavailable_capabilities": unavailable,
        "fallback": fallback,
        "governance": {
            "before_execution": [
                "task context pack",
                "workflow plan",
                "active owner/patcher session lease",
                "allowed-path scope",
            ],
            "during_execution": [
                "scope expansion requires an explicit decision",
                "provider-native work must preserve AgentSpec policy boundaries",
            ],
            "before_completion": [
                "verification evidence",
                "code-review verdict",
                "finish write-back",
            ],
        },
    }


def build_lifecycle_contract(root: Path) -> dict[str, Any]:
    """Build the native lifecycle stages and adapter ownership contract."""

    root = root.resolve()
    stages = _lifecycle_stages()
    execution = build_execution_strategy(root)
    counts = {
        "stages": len(stages),
        "available": sum(1 for stage in stages if stage["status"] == "available"),
        "partial": sum(1 for stage in stages if stage["status"] == "partial"),
        "planned": sum(1 for stage in stages if stage["status"] == "planned"),
    }
    return {
        "schema": LIFECYCLE_CONTRACT_SCHEMA,
        "root": str(root),
        "summary": "AgentSpec owns the repo-local operating contract for human-plus-agent software delivery.",
        "post_artifact_guidance": {
            "schema": POST_ARTIFACT_GUIDANCE_SCHEMA,
            "command": "aspec guidance <artifact> --json",
            "human_command": "aspec guidance <artifact>",
            "agent_display": {
                "show_terminal_commands": False,
                "guidance": "Use this projection after creating or updating an artifact to show state-aware next choices without raw commands.",
            },
        },
        "execution": execution,
        "adapter_boundary": {
            "agent_spec_owns": [
                "canonical source snapshots",
                "requirements and DCR governance",
                "task context packs",
                "workflow artifacts",
                "session and branch leases",
                "allowed paths",
                "run packages and results",
                "verification evidence",
                "review evidence",
                "finish write-back",
                "roadmap and handoff",
            ],
            "adapters_provide": [
                "host-specific model invocation",
                "subagent process spawning",
                "browser or desktop automation runtime",
                "remote forge operations such as PR creation",
            ],
        },
        "source_inspirations": [
            {
                "name": "AgentSpec source snapshots",
                "value": "Accepted AgentSpec design and lifecycle-hardening source sections.",
            },
            {
                "name": "addyosmani/agent-skills",
                "value": (
                    "Mapped as process inspiration for idea refinement, specification, planning, "
                    "implementation, review, quality, git workflow, CI/CD, documentation, security, "
                    "performance, browser testing, migration, and launch practices."
                ),
            },
        ],
        "counts": counts,
        "stages": stages,
    }


def format_lifecycle_contract(contract: dict[str, Any]) -> str:
    """Format a lifecycle operating contract for terminal output."""

    lines = [
        "AgentSpec Lifecycle Operating Contract",
        str(contract.get("summary") or ""),
        "",
        "Stages:",
    ]
    for index, stage in enumerate(contract.get("stages", []), start=1):
        if not isinstance(stage, dict):
            continue
        commands = ", ".join(stage.get("native_commands") or ["-"])
        skills = ", ".join(stage.get("skill_names") or ["-"])
        lines.append(f"{index}. {stage['title']} [{stage['status']}]")
        lines.append(f"   Commands: {commands}")
        lines.append(f"   Skills: {skills}")
        if stage.get("next_native_step"):
            lines.append(f"   Next: {stage['next_native_step']}")
    return "\n".join(lines)


def _lifecycle_stages() -> list[dict[str, Any]]:
    return [
        {
            "id": "brainstorm",
            "title": "Brainstorm And Frame",
            "status": "partial",
            "description": "Turn ambiguous intent into a DCR candidate, design brief, or discovery task.",
            "native_commands": ["aspec dcr create", "aspec dogfood record"],
            "skill_names": ["brainstorm"],
            "artifacts": ["docs/change-requests/DCR-*.md", "reports/dogfood/*.md"],
            "next_native_step": "Add a dedicated aspec brainstorm command when idea capture needs structured output.",
        },
        {
            "id": "design",
            "title": "Design And Source Intake",
            "status": "partial",
            "description": "Promote source-backed design material into canonical AgentSpec context.",
            "native_commands": [
                "aspec ingest",
                "aspec intake import",
                "aspec intake diff",
                "aspec intake promote",
                "aspec compile",
                "aspec guidance <artifact> --json",
            ],
            "skill_names": ["design-work", "manual-source-intake", "compile-spec"],
            "artifacts": ["docs/source/**", "docs/spec/**", "docs/traceability/requirements.yml"],
            "next_native_step": "Add aspec design as a higher-level orchestration command over intake and compile.",
        },
        {
            "id": "plan",
            "title": "Plan Workflow",
            "status": "available",
            "description": "Create bounded task packs and native workflow artifacts from accepted requirements.",
            "native_commands": ["aspec task create", "aspec plan", "aspec guidance <artifact> --json"],
            "skill_names": ["create-task", "plan-workflow"],
            "artifacts": ["agent/context-packs/T-*.md", "agent/workflows/W-*.md"],
            "next_native_step": None,
        },
        {
            "id": "branch_start",
            "title": "Start Branch Or Session",
            "status": "partial",
            "description": "Record branch, worktree, owner, task, and allowed-path lease metadata.",
            "native_commands": ["aspec session start"],
            "skill_names": ["start-branch"],
            "artifacts": ["agent/sessions/active/*.yml"],
            "next_native_step": "Add aspec branch start to optionally create the git branch/worktree and session lease together.",
        },
        {
            "id": "execute",
            "title": "Execute Workflow",
            "status": "partial",
            "description": (
                "Prefer the host's native Codex or Claude workflow while AgentSpec retains task, path, "
                "verification, review, and finish governance; use the runner contract as fallback."
            ),
            "native_commands": [
                "aspec run package",
                "aspec run result",
                "aspec run loop",
                "aspec run exec",
            ],
            "skill_names": ["execute-workflow", "continue-work"],
            "artifacts": ["agent/runs/*", "agent/task-ledger.yml"],
            "preferred_execution": "provider_native",
            "fallback_execution": "agentspec_generic_fallback",
            "next_native_step": "Add provider hook adapters that enforce AgentSpec decisions inside host-native execution.",
        },
        {
            "id": "delegate",
            "title": "Delegate Work",
            "status": "planned",
            "description": "Split independent workflow steps into child execution packages or sessions with disjoint write scopes.",
            "native_commands": [],
            "skill_names": ["delegate-work"],
            "artifacts": ["agent/sessions/active/*.yml", "agent/runs/*"],
            "next_native_step": "Add aspec run delegate with child session leases, ownership, fan-out/fan-in, and result aggregation.",
        },
        {
            "id": "verify",
            "title": "Verify Work",
            "status": "partial",
            "description": "Run declared checks and inspect outcome, status, roadmap, and task-specific evidence.",
            "native_commands": ["aspec outcome", "aspec status", "aspec roadmap --check"],
            "skill_names": ["verify-work"],
            "artifacts": ["agent/context-packs/T-*.md", "reports/**"],
            "next_native_step": "Add aspec verify to store structured verification evidence without completing the task.",
        },
        {
            "id": "review",
            "title": "Review And Decide",
            "status": "available",
            "description": "Record task-level review verdicts before completion or branch finish.",
            "native_commands": ["aspec review code"],
            "skill_names": ["review-code"],
            "artifacts": ["agent/reviews/REVIEW-*.yml"],
            "next_native_step": None,
        },
        {
            "id": "branch_finish",
            "title": "Finish Branch",
            "status": "partial",
            "description": "Combine finish write-back with branch/session disposition.",
            "native_commands": ["aspec finish", "aspec task complete", "aspec session finish"],
            "skill_names": ["finish-branch", "finish-work"],
            "artifacts": ["agent/handoff.yml", "agent/task-ledger.yml", "docs/ROADMAP.md", "agent/sessions/archived/*.yml"],
            "next_native_step": "Add aspec branch finish to run clean-checkout verification and record merge, PR, keep, or discard disposition.",
        },
        {
            "id": "handoff_recovery",
            "title": "Handoff And Recovery",
            "status": "available",
            "description": "Resume from durable state and dispatch the next safe action.",
            "native_commands": [
                "aspec status --json",
                "aspec guidance <artifact> --json",
                "aspec next-action",
                "aspec continue",
                "aspec roadmap",
            ],
            "skill_names": ["handoff-recovery", "project-status", "roadmap"],
            "artifacts": ["agent/handoff.yml", "docs/ROADMAP.md"],
            "next_native_step": None,
        },
    ]


def _execution_provider(root: Path, provider: str | None) -> str:
    explicit = provider or os.environ.get("AGENTSPEC_EXECUTION_PROVIDER")
    if explicit:
        return _normalize_provider(explicit)

    config = merged_runtime_config(load_project_config(root))
    execution = config.get("execution")
    if isinstance(execution, dict) and execution.get("provider"):
        return _normalize_provider(str(execution["provider"]))
    profiles = config.get("agent_profiles")
    main_executor = profiles.get("main_executor") if isinstance(profiles, dict) else None
    adapter = main_executor.get("adapter") if isinstance(main_executor, dict) else None
    return _normalize_provider(str(adapter or "current-host"))


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower().replace("_", "-")
    aliases = {
        "anthropic": "claude",
        "claude-code": "claude",
        "openai": "codex",
        "host-default": "current-host",
        "current_host": "current-host",
        "runner": "generic",
    }
    return aliases.get(normalized, normalized or "current-host")


def _native_execution_candidate(
    provider: str,
    *,
    capabilities: dict[str, bool],
) -> dict[str, Any]:
    definitions: dict[str, dict[str, Any]] = {
        "codex": {
            "id": "codex-native-execution",
            "capability": "codex_goal_or_workflow",
            "mechanism": "goal_or_workflow",
            "environment": "AGENTSPEC_CODEX_NATIVE_EXECUTION",
        },
        "claude": {
            "id": "claude-native-execution",
            "capability": "claude_loop_or_dynamic_workflow",
            "mechanism": "loop_or_dynamic_workflow",
            "environment": "AGENTSPEC_CLAUDE_NATIVE_EXECUTION",
        },
        "current-host": {
            "id": "current-host-native-execution",
            "capability": "current_host_native_workflow",
            "mechanism": "host_managed_workflow",
            "environment": None,
        },
    }
    definition = definitions.get(provider)
    if definition is None:
        return {
            "id": f"{provider or 'unknown'}-native-execution",
            "mode": "provider_native",
            "provider": provider,
            "capability": "provider_native_execution",
            "mechanism": "unknown",
            "availability": "unavailable",
            "unavailable_reason": "No provider-native AgentSpec adapter is registered for this host.",
        }

    capability = str(definition["capability"])
    availability = _capability_availability(
        capability,
        provider=provider,
        environment=definition.get("environment"),
        capabilities=capabilities,
    )
    return {
        "id": str(definition["id"]),
        "mode": "provider_native",
        "provider": provider,
        "capability": capability,
        "mechanism": str(definition["mechanism"]),
        "availability": availability,
        "unavailable_reason": (
            f"The selected {provider} host does not expose {capability}."
            if availability == "unavailable"
            else None
        ),
    }


def _capability_availability(
    capability: str,
    *,
    provider: str,
    environment: Any,
    capabilities: dict[str, bool],
) -> str:
    if capability in capabilities:
        return "available" if capabilities[capability] else "unavailable"
    if isinstance(environment, str):
        parsed = _environment_boolean(environment)
        if parsed is not None:
            return "available" if parsed else "unavailable"
    return "unverified" if provider == "current-host" else "available"


def _environment_boolean(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return None
