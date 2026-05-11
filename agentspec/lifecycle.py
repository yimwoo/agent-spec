from __future__ import annotations

from pathlib import Path
from typing import Any


LIFECYCLE_CONTRACT_SCHEMA = "agentspec.lifecycle_contract.v0"


def build_lifecycle_contract(root: Path) -> dict[str, Any]:
    root = root.resolve()
    stages = _lifecycle_stages()
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
                "value": "Mapped as process inspiration for idea refinement, specification, planning, implementation, review, quality, git workflow, CI/CD, documentation, security, performance, browser testing, migration, and launch practices.",
            },
        ],
        "counts": counts,
        "stages": stages,
    }


def format_lifecycle_contract(contract: dict[str, Any]) -> str:
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
            "native_commands": ["aspec task create", "aspec plan"],
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
            "description": "Run or package execution steps while AgentSpec retains task, path, and review governance.",
            "native_commands": [
                "aspec run loop",
                "aspec run step",
                "aspec run package",
                "aspec run result",
                "aspec run exec",
            ],
            "skill_names": ["execute-workflow", "continue-work"],
            "artifacts": ["agent/runs/*", "agent/task-ledger.yml"],
            "next_native_step": "Add aspec workflow execute to drive workflow-stage state directly from W-*.md files.",
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
            "native_commands": ["aspec status --json", "aspec next-action", "aspec continue", "aspec roadmap"],
            "skill_names": ["handoff-recovery", "project-status", "roadmap"],
            "artifacts": ["agent/handoff.yml", "docs/ROADMAP.md"],
            "next_native_step": None,
        },
    ]
