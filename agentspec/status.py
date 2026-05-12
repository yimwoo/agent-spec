from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from .config import load_project_config, merged_runtime_config
from .dcr import list_dcrs
from .errors import ERROR_SCHEMA
from .handoff import load_project_handoff
from .io import load_data
from .maturity import build_maturity_status
from .model_review import build_agent_profile_diagnostics
from .outcome import build_outcome_status
from .paths import path_matches_pattern
from .run import RESEARCH_ALLOWED_PATHS
from .session import build_session_preflight, build_session_status
from .task import list_task_context_packs, next_task_context_pack
from .workflow import build_workflow_contract_status, workflow_warning_lines
from .writeback import build_lifecycle_projection, lifecycle_warning_lines


PROJECT_STATUS_SCHEMA = "agentspec.project_status.v0"
LIFECYCLE_SUMMARY_SCHEMA = "agentspec.lifecycle_summary.v0"
IMPLEMENTATION_READINESS_GATE = 60
ACTIVE_RUN_STATUSES = {"started", "running"}
ATTENTION_RUN_STATUSES = {"paused", "halted"}
LIFECYCLE_BREADCRUMB = [
    "draft_source",
    "ingest_source",
    "compile_requirements",
    "create_task_context_pack",
    "run_task",
    "verify_and_review",
    "complete_task",
    "outcome_readiness",
]


def build_project_status(root: Path, *, recent_limit: int = 5) -> dict[str, Any]:
    root = root.resolve()
    recent_limit = max(0, recent_limit)
    requirements = _list_or_empty(load_data(root / "docs" / "traceability" / "requirements.yml", []))
    readiness = _dict_or_empty(load_data(root / "docs" / "discovery" / "readiness.yml", {}))
    dcrs = list_dcrs(root)
    tasks = list_task_context_packs(root)
    runs = _load_runs(root)
    next_task = next_task_context_pack(root)
    outcomes = build_outcome_status(root)
    maturity = build_maturity_status(root)
    sessions = build_session_status(root)
    workflows = build_workflow_contract_status(root)
    agent_profiles = _agent_profile_status(root)

    active_runs, stale_active_runs = _classify_active_runs(runs, tasks)
    attention_runs, stale_attention_runs = _classify_attention_runs(root, runs, tasks)
    recent_runs = sorted(runs, key=lambda run: str(run.get("updated_at", "")), reverse=True)[:recent_limit]
    requirements_counts = {
        "total": len(requirements),
        "by_status": _counts(record.get("status") for record in requirements),
        "by_priority": _counts(record.get("priority") for record in requirements),
        "accepted_examples": _requirement_examples(requirements, status="accepted"),
    }
    dcr_counts = {
        "total": len(dcrs),
        "by_status": _counts(record.get("status") for record in dcrs),
        "by_classification": _counts(record.get("classification") for record in dcrs),
    }
    task_counts = {
        "total": len(tasks),
        "by_status": _counts(record.get("status") for record in tasks),
        "by_type": _counts(record.get("type") for record in tasks),
        "ready": [record for record in tasks if record.get("status") == "ready"],
        "next": next_task,
    }
    run_counts = {
        "total": len(runs),
        "by_status": _counts(run.get("status") for run in runs),
        "by_mode": _counts(run.get("mode") for run in runs),
        "active": active_runs,
        "stale_active": stale_active_runs,
        "attention": attention_runs,
        "stale_attention": stale_attention_runs,
        "recent": recent_runs,
    }
    handoff = load_project_handoff(root)
    lifecycle = build_lifecycle_projection(
        root,
        project_counts={
            "requirements": requirements_counts,
            "dcrs": dcr_counts,
            "tasks": task_counts,
            "runs": run_counts,
        },
        workflows=workflows,
        handoff=handoff,
    )

    payload = {
        "schema": PROJECT_STATUS_SCHEMA,
        "root": str(root),
        "overall": _overall_status(
            next_task=next_task,
            active_runs=active_runs,
            attention_runs=attention_runs,
            lifecycle=lifecycle,
        ),
        "recommendation": _recommendation(
            next_task=next_task,
            active_runs=active_runs,
            attention_runs=attention_runs,
            workflows=workflows,
            lifecycle=lifecycle,
        ),
        "readiness": {
            "score": readiness.get("score"),
            "mode": readiness.get("mode"),
            "summary": readiness.get("summary"),
        },
        "outcomes": outcomes,
        "maturity": maturity,
        "requirements": requirements_counts,
        "dcrs": dcr_counts,
        "tasks": task_counts,
        "runs": run_counts,
        "sessions": sessions,
        "agent_profiles": agent_profiles,
        "workflows": workflows,
        "lifecycle": lifecycle,
    }
    if handoff is not None:
        payload["handoff"] = handoff
    payload["lifecycle_summary"] = build_lifecycle_summary(payload)
    return payload


def build_lifecycle_summary(status: dict[str, Any]) -> dict[str, Any]:
    """Return a stable, human-oriented next-action projection for status JSON."""

    readiness = _dict_or_empty(status.get("readiness"))
    requirements = _dict_or_empty(status.get("requirements"))
    tasks = _dict_or_empty(status.get("tasks"))
    runs = _dict_or_empty(status.get("runs"))
    workflows = _dict_or_empty(status.get("workflows"))
    lifecycle = _dict_or_empty(status.get("lifecycle"))
    outcomes = _dict_or_empty(status.get("outcomes"))
    next_task = tasks.get("next") if isinstance(tasks.get("next"), dict) else None
    attention_runs = _list_or_empty(runs.get("attention"))
    active_runs = _list_or_empty(runs.get("active"))
    workflow_warnings = workflow_warning_lines(workflows)

    stage = "idle_no_ready_task"
    main_point = "No implementation task is ready to run."
    artifact: dict[str, Any] | None = None
    blocked_by: list[dict[str, Any]] = []
    action = {
        "label": "Inspect AgentSpec status and create or classify the next task.",
        "human_decision_required": True,
        "reason": "AgentSpec needs a ready context pack before a code agent can safely start implementation.",
        "commands": ["aspec status --json", "aspec task next"],
    }

    if attention_runs:
        run = attention_runs[0]
        run_id = str(run.get("run_id") or "unknown")
        stage = "attention_run"
        main_point = f"Run {run_id} needs attention before new work can continue."
        artifact = _run_artifact(run)
        blocked_by = _run_blockers(run)
        action = {
            "label": "Inspect the attention-needed run.",
            "human_decision_required": True,
            "reason": "A paused or halted run may require remediation or a human decision before AgentSpec starts another task.",
            "commands": [f"aspec run inspect {run_id}", "aspec status --json"],
        }
    elif active_runs:
        run = active_runs[0]
        run_id = str(run.get("run_id") or "unknown")
        stage = "active_run"
        main_point = f"Run {run_id} is active."
        artifact = _run_artifact(run)
        action = {
            "label": "Continue the active run.",
            "human_decision_required": False,
            "reason": "AgentSpec already has an in-progress run; continuing it preserves the current task boundary.",
            "commands": [f"aspec run prompt {run_id}", f"aspec run loop --run-id {run_id}", "aspec status --json"],
        }
    elif next_task:
        stage = "task_ready"
        task_id = str(next_task.get("id") or "unknown")
        path = str(next_task.get("path") or "")
        session_preflight = build_session_preflight(
            Path(str(status.get("root") or ".")),
            context_pack=path,
            task_id=task_id,
            task_type=str(next_task.get("type") or "implementation"),
        )
        main_point = f"Task {task_id} is ready to run."
        artifact = {
            "type": "task",
            "id": task_id,
            "title": next_task.get("title"),
            "path": path or None,
            "session_preflight": session_preflight,
        }
        if session_preflight.get("status") == "missing":
            stage = "task_ready_session_needed"
            main_point = f"Task {task_id} is ready, but a branch/worktree session should be claimed before execution."
            command = str(session_preflight.get("recommended_command") or f"aspec session start --task {task_id}")
            action = {
                "label": "Claim a branch/worktree session for the ready task.",
                "human_decision_required": False,
                "reason": str(session_preflight.get("message") or "Implementation execution should have an active session lease."),
                "commands": [command, f"aspec run loop {path}" if path else "aspec task next", "aspec status --json"],
                "options": [
                    {
                        "label": "Claim an implementation session",
                        "when": "Before the code agent mutates files for the ready task.",
                        "commands": [command],
                    },
                    {
                        "label": "Run after the session is active",
                        "when": "After the branch/worktree lease exists and matches the task.",
                        "commands": [f"aspec run loop {path}" if path else "aspec task next"],
                    },
                ],
            }
            blocked_by = [
                {
                    "kind": "missing_session_lease",
                    "message": str(session_preflight.get("message") or ""),
                    "context_pack": path or None,
                    "task_id": task_id,
                }
            ]
        else:
            action = {
                "label": "Start the next ready task.",
                "human_decision_required": False,
                "reason": "A ready task context pack defines the scope, allowed paths, and verification expectations.",
                "commands": [f"aspec run loop {path}" if path else "aspec task next", "aspec status --json"],
            }
    elif lifecycle.get("readiness") in {"blocked", "needs_attention"}:
        stage = "lifecycle_attention"
        findings = _lifecycle_findings(lifecycle)
        first = findings[0] if findings else {}
        message = first.get("message") or first.get("type") or "Lifecycle drift needs attention."
        main_point = f"Lifecycle attention is needed: {message}"
        blocked_by = _finding_blockers(findings)
        recommendation = first.get("recommendation")
        commands = [str(recommendation)] if recommendation else ["aspec status --json"]
        if "aspec status --json" not in commands:
            commands.append("aspec status --json")
        action = {
            "label": "Resolve lifecycle warning.",
            "human_decision_required": True,
            "reason": message,
            "commands": commands,
        }
    elif workflow_warnings:
        stage = "workflow_backfill_needed"
        main_point = "A workflow exists without a ready task context pack."
        command = _first_workflow_backfill_command(workflows)
        commands = [command] if command else ["aspec task create --from-workflow <workflow>"]
        commands.append("aspec status --json")
        blocked_by = [{"kind": "workflow_without_task_pack", "message": workflow_warnings[0]}]
        action = {
            "label": "Backfill the workflow into an AgentSpec task pack.",
            "human_decision_required": False,
            "reason": "Workflow files are executable only after AgentSpec links them to a context pack.",
            "commands": commands,
        }
    else:
        stage, main_point, blocked_by, action = _no_ready_task_summary(
            readiness=readiness,
            requirements=requirements,
            tasks=tasks,
            dcrs=_dict_or_empty(status.get("dcrs")),
            outcomes=outcomes,
        )

    return {
        "schema": LIFECYCLE_SUMMARY_SCHEMA,
        "main_point": main_point,
        "current_stage": stage,
        "breadcrumb": list(LIFECYCLE_BREADCRUMB),
        "current_artifact": artifact,
        "readiness": _readiness_summary(readiness),
        "outcomes": {
            "readiness": outcomes.get("readiness"),
            "score": outcomes.get("score"),
            "summary": outcomes.get("summary"),
        },
        "recommended_next_action": _with_agent_display(action),
        "blocked_by": blocked_by,
        "terms": _lifecycle_terms(),
    }


def load_run_records(root: Path) -> list[dict[str, Any]]:
    """Return normalized run records with recovery context."""

    return _load_runs(root.resolve())


def format_project_status(status: dict[str, Any]) -> str:
    summary = status.get("lifecycle_summary")
    readiness = status.get("readiness", {})
    requirements = status.get("requirements", {})
    dcrs = status.get("dcrs", {})
    tasks = status.get("tasks", {})
    runs = status.get("runs", {})
    sessions = status.get("sessions", {})
    workflows = status.get("workflows", {})
    agent_profiles = status.get("agent_profiles", {})
    maturity = status.get("maturity", {})
    outcomes = status.get("outcomes", {})
    lifecycle = status.get("lifecycle", {})

    lines = ["AgentSpec Status"]
    if isinstance(summary, dict):
        lines.extend(_summary_lines(summary))

    lines.extend([
        f"Root: {status.get('root')}",
        f"Overall: {status.get('overall')}",
        f"Readiness: {_readiness_text(readiness)}",
        f"Product Outcomes: {_outcomes_text(outcomes)}",
        f"Maturity: {_maturity_text(maturity)}",
        f"Requirements: {_count_text(requirements)}",
        f"DCRs: {_count_text(dcrs)}",
        f"Tasks: {_count_text(tasks)}",
        f"Runs: {_count_text(runs)}",
        f"Sessions: {_count_text(sessions)}",
        f"Agent Profiles: {_agent_profiles_text(agent_profiles)}",
        f"Workflow Pack Warnings: {_workflow_text(workflows)}",
        f"Lifecycle: {_lifecycle_text(lifecycle)}",
        f"Next: {_next_text(tasks.get('next'))}",
        f"Recommendation: {status.get('recommendation')}",
    ])

    handoff = status.get("handoff")
    if isinstance(handoff, dict):
        next_action = handoff.get("next_action") if isinstance(handoff.get("next_action"), dict) else {}
        lines.append(
            f"Handoff: {handoff.get('path', 'agent/handoff.yml')} "
            f"({next_action.get('kind', 'unknown')}) -> {next_action.get('command', '-')}"
        )

    attention = runs.get("attention") if isinstance(runs, dict) else []
    if attention:
        lines.extend(["", "Attention Runs:"])
        lines.extend(f"- {_run_text(run)}" for run in attention)

    active = runs.get("active") if isinstance(runs, dict) else []
    if active:
        lines.extend(["", "Active Runs:"])
        lines.extend(f"- {_run_text(run)}" for run in active)

    active_sessions = sessions.get("active") if isinstance(sessions, dict) else []
    if active_sessions:
        lines.extend(["", "Active Sessions:"])
        lines.extend(f"- {_session_text(session)}" for session in active_sessions)

    lifecycle_warnings = lifecycle_warning_lines(lifecycle) if isinstance(lifecycle, dict) else []
    if lifecycle_warnings:
        lines.extend(["", "Lifecycle Warnings:"])
        lines.extend(f"- {warning}" for warning in lifecycle_warnings)

    workflow_warnings = workflow_warning_lines(workflows) if isinstance(workflows, dict) else []
    if workflow_warnings:
        lines.extend(["", "Workflow Warnings:"])
        lines.extend(f"- {warning}" for warning in workflow_warnings)

    recent = runs.get("recent") if isinstance(runs, dict) else []
    if recent:
        lines.extend(["", "Recent Runs:"])
        lines.extend(f"- {_run_text(run)}" for run in recent)

    return "\n".join(lines)


def _load_runs(root: Path) -> list[dict[str, Any]]:
    runs_dir = root / "agent" / "runs"
    if not runs_dir.is_dir():
        return []

    records: list[dict[str, Any]] = []
    for run_dir in sorted(path for path in runs_dir.iterdir() if path.is_dir()):
        state = _load_optional_dict(run_dir / "state.yml")
        summary = _load_optional_dict(run_dir / "summary.yml")
        source = "state" if state else "summary" if summary else None
        data = state or summary
        if not data:
            continue
        events = _load_run_events(root, run_dir)

        record = {
            "run_id": data.get("run_id") or run_dir.name,
            "status": data.get("status", "unknown"),
            "mode": data.get("mode", "supervised"),
            "context_pack": data.get("context_pack"),
            "context_pack_title": data.get("context_pack_title"),
            "iteration": data.get("iteration"),
            "max_iterations": data.get("max_iterations"),
            "last_decision": data.get("last_decision"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "terminal": bool(data.get("terminal")) or data.get("status") in {"complete", "halted", "aborted"},
            "source": source,
        }
        record.update(_recovery_context(run_dir, record, data, events))
        if summary:
            record["summary_path"] = _relative_or_absolute(root, run_dir / "summary.yml")
            record["blocked_findings"] = summary.get("blocked_findings", [])
        if state:
            record["state_path"] = _relative_or_absolute(root, run_dir / "state.yml")
        records.append(record)

    return sorted(records, key=lambda run: str(run.get("updated_at", "")), reverse=True)


def _classify_active_runs(
    runs: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    active: list[dict[str, Any]] = []
    stale_active: list[dict[str, Any]] = []
    completed_by_pack = _completed_task_by_context_pack(tasks)

    for run in runs:
        if run.get("status") not in ACTIVE_RUN_STATUSES:
            continue
        stale = _superseded_by_completed_task_details(run, completed_by_pack)
        if stale:
            run["stale_active"] = stale
            stale_active.append(run)
        else:
            active.append(run)
    return active, stale_active


def _classify_attention_runs(
    root: Path,
    runs: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attention: list[dict[str, Any]] = []
    stale_attention: list[dict[str, Any]] = []
    completed_by_pack = _completed_task_by_context_pack(tasks)
    completed_scopes = _completed_task_allowed_scopes(root, tasks)

    for run in runs:
        if run.get("status") not in ATTENTION_RUN_STATUSES:
            continue
        stale = _superseded_by_completed_task_details(run, completed_by_pack)
        if stale is None:
            stale = _stale_research_attention_details(run, completed_scopes)
        if stale:
            run["stale_attention"] = stale
            stale_attention.append(run)
        else:
            attention.append(run)
    return attention, stale_attention


def _completed_task_by_context_pack(tasks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    for task in tasks:
        if task.get("status") != "complete":
            continue
        context_pack = task.get("path")
        if isinstance(context_pack, str) and context_pack:
            completed[context_pack] = task
    return completed


def _superseded_by_completed_task_details(
    run: dict[str, Any],
    completed_by_pack: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    context_pack = run.get("context_pack")
    if not isinstance(context_pack, str):
        return None
    completed = completed_by_pack.get(context_pack)
    if not completed:
        return None
    return {
        "reason": "Run is superseded by completed task ledger state.",
        "covered_by_task": completed.get("id"),
        "context_pack": context_pack,
    }


def _completed_task_allowed_scopes(
    root: Path,
    tasks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scopes: list[dict[str, Any]] = []
    for task in tasks:
        if task.get("status") != "complete":
            continue
        context_pack = task.get("path")
        if not isinstance(context_pack, str) or not context_pack:
            continue
        allowed_paths = _context_pack_allowed_paths(root, context_pack)
        if not allowed_paths:
            continue
        scopes.append(
            {
                "task_id": task.get("id"),
                "title": task.get("title"),
                "context_pack": context_pack,
                "allowed_paths": allowed_paths,
            }
        )
    return scopes


def _stale_research_attention_details(
    run: dict[str, Any],
    completed_scopes: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if run.get("mode") != "research":
        return None
    if "forbidden_path" not in _string_list(run.get("policy_flags")):
        return None
    touched_paths = _string_list(run.get("touched_paths"))
    if not touched_paths:
        return None
    implementation_paths = [
        path
        for path in touched_paths
        if not _path_allowed_by_patterns(path, RESEARCH_ALLOWED_PATHS)
    ]
    if not implementation_paths:
        return None
    for scope in completed_scopes:
        allowed_paths = _string_list(scope.get("allowed_paths"))
        if all(_path_allowed_by_patterns(path, allowed_paths) for path in implementation_paths):
            return {
                "reason": "Research-mode forbidden paths are covered by a completed task context pack.",
                "covered_by_task": scope.get("task_id"),
                "context_pack": scope.get("context_pack"),
                "covered_paths": implementation_paths,
            }
    return None


def _context_pack_allowed_paths(root: Path, context_pack: str) -> list[str]:
    path = root / context_pack
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return _markdown_list_after_heading(text, "Allowed Paths")


def _markdown_list_after_heading(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    items: list[str] = []
    in_section = False
    heading_re = re.compile(rf"^##\s+{re.escape(heading)}\s*$", flags=re.IGNORECASE)
    for line in lines:
        if heading_re.match(line.strip()):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            match = re.match(r"^\s*-\s+`?([^`]+?)`?\s*$", line)
            if match:
                items.append(match.group(1).strip())
    return items


def _path_allowed_by_patterns(path: str, patterns: list[str]) -> bool:
    return any(path_matches_pattern(path, pattern) for pattern in patterns)


def _agent_profile_status(root: Path) -> dict[str, Any]:
    try:
        config = merged_runtime_config(load_project_config(root))
    except ValueError as exc:
        return {
            "schema": "agentspec.agent_profile_diagnostics.v0",
            "status": "invalid_config",
            "bindings": {},
            "profiles": {},
            "warnings": [{"profile": None, "message": str(exc)}],
        }
    return build_agent_profile_diagnostics(config)


def _load_optional_dict(path: Path) -> dict[str, Any]:
    try:
        data = load_data(path, {})
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _load_run_events(root: Path, run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "events.jsonl"
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            payload["_event_ref"] = f"{_relative_or_absolute(root, path)}:{line_number}"
            events.append(payload)
    return events


def _recovery_context(
    run_dir: Path,
    record: dict[str, Any],
    data: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    reviewer = _last_event(events, "reviewer_verdict")
    executor = _last_event(events, "executor_output")
    last_error = _latest_structured_error(events)
    policy_flags = reviewer.get("policy_flags") if reviewer else []
    if not isinstance(policy_flags, list):
        policy_flags = []

    return {
        "last_review_reason": reviewer.get("reason") if reviewer else None,
        "policy_flags": [str(flag) for flag in policy_flags],
        "touched_paths": _string_list(executor.get("touched_paths") if executor else []),
        "reported_touched_paths": _string_list(executor.get("reported_touched_paths") if executor else []),
        "test_status": _test_status_from_event(executor) or _test_status_from_state(data),
        "last_event_ref": reviewer.get("_event_ref") if reviewer else None,
        "last_error": last_error,
        "recovery_command": _recovery_command(str(record.get("run_id") or run_dir.name), str(record.get("status", "unknown"))),
    }


def _last_event(events: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("kind") == kind:
            return event
    return None


def _latest_structured_error(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        error = event.get("error")
        if not isinstance(error, dict) or error.get("schema") != ERROR_SCHEMA:
            continue
        payload = {
            key: error.get(key)
            for key in (
                "code",
                "layer",
                "message",
                "retryable",
                "severity",
                "operation",
                "details",
            )
            if key in error
        }
        recovery_command = error.get("recovery_command") or event.get("recovery_command")
        if recovery_command is not None:
            payload["recovery_command"] = recovery_command
        event_ref = event.get("_event_ref")
        if event_ref is not None:
            payload["event_ref"] = event_ref
        return payload
    return None


def _test_status_from_event(event: dict[str, Any] | None) -> str | None:
    if not event:
        return None
    summary = event.get("test_summary")
    if isinstance(summary, dict) and isinstance(summary.get("status"), str):
        return summary["status"]
    return None


def _test_status_from_state(data: dict[str, Any]) -> str | None:
    verification = data.get("verification")
    if isinstance(verification, dict) and isinstance(verification.get("status"), str):
        return verification["status"]
    return None


def _recovery_command(run_id: str, status: str) -> str:
    if status in ACTIVE_RUN_STATUSES:
        return f"aspec run prompt {run_id}"
    return f"aspec run inspect {run_id}"


def _list_or_empty(value: Any) -> list[dict[str, Any]]:
    return [record for record in value if isinstance(record, dict)] if isinstance(value, list) else []


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _counts(values: Any) -> dict[str, int]:
    counter = Counter(str(value) for value in values if value is not None)
    return {key: counter[key] for key in sorted(counter)}


def _overall_status(
    *,
    next_task: dict[str, Any] | None,
    active_runs: list[dict[str, Any]],
    attention_runs: list[dict[str, Any]],
    lifecycle: dict[str, Any] | None = None,
) -> str:
    if attention_runs:
        return "attention_needed"
    if active_runs:
        return "running"
    if next_task:
        return "ready"
    if isinstance(lifecycle, dict) and lifecycle.get("readiness") == "needs_attention":
        return "attention_needed"
    return "idle"


def _recommendation(
    *,
    next_task: dict[str, Any] | None,
    active_runs: list[dict[str, Any]],
    attention_runs: list[dict[str, Any]],
    workflows: dict[str, Any] | None = None,
    lifecycle: dict[str, Any] | None = None,
) -> str:
    if attention_runs:
        run_id = attention_runs[0].get("run_id")
        return f"Inspect attention-needed run with `aspec run inspect {run_id}`."
    if active_runs:
        run_id = active_runs[0].get("run_id")
        return f"Continue active run with `aspec run prompt {run_id}` or `aspec run loop --run-id {run_id}`."
    if next_task:
        return f"Start next ready task with `aspec run loop {next_task.get('path')}`."
    lifecycle_recommendation = _lifecycle_recommendation(lifecycle)
    if lifecycle_recommendation:
        return lifecycle_recommendation
    warnings = workflow_warning_lines(workflows or {})
    if warnings:
        first = workflows.get("orphans", [{}])[0] if isinstance(workflows, dict) and isinstance(workflows.get("orphans"), list) else {}
        command = first.get("backfill_command") if isinstance(first, dict) else None
        return f"Backfill in-flight workflow with `{command}`." if command else warnings[0]
    return "No ready task context pack found; create or classify the next DCR/task, or run autonomous research mode."


def _lifecycle_recommendation(lifecycle: dict[str, Any] | None) -> str | None:
    if not isinstance(lifecycle, dict):
        return None
    warnings = lifecycle.get("warnings") if isinstance(lifecycle.get("warnings"), list) else []
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        recommendation = warning.get("recommendation")
        if recommendation:
            return f"Resolve lifecycle warning with `{recommendation}`."
    if warnings:
        first = warnings[0]
        return f"Resolve lifecycle warning: {first.get('message') or first.get('type')}."
    return None


def _summary_lines(summary: dict[str, Any]) -> list[str]:
    action = _dict_or_empty(summary.get("recommended_next_action"))
    readiness = _dict_or_empty(summary.get("readiness"))
    commands = _string_list(action.get("commands"))
    options = _list_or_empty(action.get("options"))
    lines = [
        f"Main point: {summary.get('main_point', '-')}",
        f"Lifecycle state: current={summary.get('current_stage', 'unknown')}; next={action.get('label', '-')}",
        f"Recommended next action: {action.get('label', '-')}",
        f"Human decision needed: {'yes' if action.get('human_decision_required') else 'no'}",
        f"Mode: {readiness.get('mode', 'unknown')}",
        _implementation_gate_text(readiness),
    ]
    explanation = readiness.get("explanation")
    if explanation:
        lines.append(f"Readiness meaning: {explanation}")
    if commands:
        lines.append("Terminal next commands:")
        lines.extend(f"- {command}" for command in commands)
    if options:
        lines.append("Next options:")
        for index, option in enumerate(options, start=1):
            label = option.get("label") or f"Option {index}"
            when = option.get("when")
            lines.append(f"{index}. {label}")
            if when:
                lines.append(f"   Use when: {when}")
            option_commands = _string_list(option.get("commands"))
            lines.extend(f"   - {command}" for command in option_commands)
    lines.append("")
    return lines


def _implementation_gate_text(readiness: dict[str, Any]) -> str:
    score = readiness.get("score")
    gate = readiness.get("implementation_gate", IMPLEMENTATION_READINESS_GATE)
    if not isinstance(score, int):
        return f"Implementation gate: readiness is unknown; compile accepted source before creating implementation tasks."
    relation = "meets" if score >= gate else "is below"
    consequence = (
        "implementation tasks are allowed when a ready task pack exists"
        if score >= gate
        else "production implementation tasks are blocked"
    )
    return f"Implementation gate: readiness {score}/100 {relation} {gate}/100; {consequence}."


def _readiness_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    score = readiness.get("score")
    mode = readiness.get("mode") or "unknown"
    allowed = isinstance(score, int) and score >= IMPLEMENTATION_READINESS_GATE
    if not isinstance(score, int):
        explanation = "Readiness has not been compiled yet, so AgentSpec cannot safely recommend implementation work."
    elif allowed:
        explanation = (
            f"Readiness {score}/100 meets the {IMPLEMENTATION_READINESS_GATE}/100 implementation gate; "
            "AgentSpec may recommend implementation tasks when a ready context pack exists."
        )
    else:
        explanation = (
            f"Readiness {score}/100 is below the {IMPLEMENTATION_READINESS_GATE}/100 implementation gate; "
            "AgentSpec should stay in discovery, spike, or scaffold work until blockers are resolved."
        )
    return {
        "score": score,
        "mode": mode,
        "summary": readiness.get("summary"),
        "implementation_gate": IMPLEMENTATION_READINESS_GATE,
        "implementation_allowed": allowed,
        "explanation": explanation,
    }


def _no_ready_task_summary(
    *,
    readiness: dict[str, Any],
    requirements: dict[str, Any],
    tasks: dict[str, Any],
    dcrs: dict[str, Any],
    outcomes: dict[str, Any],
) -> tuple[str, str, list[dict[str, Any]], dict[str, Any]]:
    score = readiness.get("score")
    accepted_requirements = _status_count(requirements, "accepted")
    accepted_examples = _list_or_empty(requirements.get("accepted_examples"))
    example_requirement = accepted_examples[0] if accepted_examples else {}
    requirement_id = str(example_requirement.get("id") or "R-001")
    requirement_title = str(example_requirement.get("title") or "next accepted requirement")
    total_tasks = int(tasks.get("total", 0) or 0)
    classified_dcrs = _status_count(dcrs, "classified")
    accepted_dcrs = _status_count(dcrs, "accepted")
    outcome_counts = outcomes.get("counts") if isinstance(outcomes.get("counts"), dict) else {}
    outcomes_ready = (
        outcomes.get("readiness") == "ready"
        and int(outcome_counts.get("required_gates", 0) or 0) > 0
        and int(outcome_counts.get("ready_required_gates", 0) or 0)
        == int(outcome_counts.get("required_gates", 0) or 0)
        and int(outcome_counts.get("blocked_required_gates", 0) or 0) == 0
    )
    action_label = "Prepare the next AgentSpec task context pack."

    if accepted_requirements == 0:
        stage = "source_or_requirements_needed"
        main_point = "No implementation task is ready because AgentSpec has no accepted requirements yet."
        reason = "Accepted requirements must exist before AgentSpec can create a scoped implementation task."
        commands = ["aspec status", "aspec status --json", "aspec ingest docs/source/design.md", "aspec compile"]
        options = [
            {
                "label": "Import design/source material",
                "when": "You already have a design, spec, issue, or Markdown note that should become AgentSpec source.",
                "commands": ["aspec ingest docs/source/design.md", "aspec compile", "aspec status"],
            },
            {
                "label": "Inspect current state",
                "when": "You need to see why no requirements are accepted yet.",
                "commands": ["aspec status", "aspec status --json"],
            },
        ]
    elif isinstance(score, int) and score < IMPLEMENTATION_READINESS_GATE:
        stage = "implementation_readiness_blocked"
        main_point = (
            f"No implementation task is ready because readiness {score}/100 is below "
            f"the {IMPLEMENTATION_READINESS_GATE}/100 implementation gate."
        )
        reason = "Resolve readiness blockers with discovery, spike, or scaffold work before creating production implementation tasks."
        commands = [
            "aspec status",
            'aspec task create --type spike --title "Resolve readiness blockers"',
            "aspec task next",
        ]
        options = [
            {
                "label": "Create a spike task",
                "when": "The next step is investigation or design cleanup before production implementation is safe.",
                "commands": [
                    'aspec task create --type spike --title "Resolve readiness blockers"',
                    "aspec task next",
                ],
            },
            {
                "label": "Recompile source after updating design inputs",
                "when": "The readiness score is stale or source material was just revised.",
                "commands": ["aspec compile", "aspec status"],
            },
        ]
    elif total_tasks == 0:
        stage = "task_context_needed"
        main_point = "No implementation task is ready because accepted requirements have not been converted into task context packs."
        reason = "A code agent needs a task context pack before it can safely edit files."
        commands = [
            f'aspec task create --requirement {requirement_id} --type implementation --title "Implement {requirement_title}"',
            "aspec task next",
        ]
        options = [
            {
                "label": f"Create an implementation task for {requirement_id}",
                "when": "You want a code agent to start from an accepted requirement.",
                "commands": commands,
            },
            {
                "label": "Review accepted requirements before tasking",
                "when": "You are not sure which requirement should be implemented next.",
                "commands": ["aspec status --json"],
            },
        ]
    else:
        stage = "idle_no_ready_task"
        main_point = "No implementation task is ready; all known task context packs are complete, halted, or otherwise not executable."
        followup_title = "Define the next AgentSpec improvement"
        if outcomes_ready:
            action_label = "Choose new AgentSpec scope."
            reason = (
                "All configured product outcomes and required gates are ready; "
                "no existing requirement or gate currently identifies remaining implementation scope."
            )
            commands = [
                "aspec outcome",
                f'aspec dcr create --title "{followup_title}" --classification implement-now',
                "aspec run loop --mode autonomous --json",
            ]
            options = [
                {
                    "label": "Capture a new change request",
                    "when": "The next work is a new idea, bug, or product change that is not yet represented by a requirement.",
                    "commands": [
                        f'aspec dcr create --title "{followup_title}" --classification implement-now',
                        "aspec status",
                    ],
                },
                {
                    "label": "Inspect ready outcomes before choosing",
                    "when": "You want to confirm there is no uncovered outcome gate before tasking more work.",
                    "commands": ["aspec outcome", "aspec task list"],
                },
                {
                    "label": "Run research mode",
                    "when": "There is no known implementation scope and you want AgentSpec to propose the next discovery artifact.",
                    "commands": ["aspec run loop --mode autonomous --json"],
                },
            ]
        else:
            reason = "Create or classify the next DCR/task, or choose autonomous research mode if there is no known implementation scope."
            commands = [
                f'aspec task create --requirement {requirement_id} --type implementation --title "Follow up on {requirement_title}"',
                "aspec task next",
                f'aspec dcr create --title "{followup_title}" --classification implement-now',
            ]
            options = [
                {
                    "label": f"Create a follow-up task for {requirement_id}",
                    "when": "Existing accepted scope still needs another implementation slice.",
                    "commands": [
                        f'aspec task create --requirement {requirement_id} --type implementation --title "Follow up on {requirement_title}"',
                        "aspec task next",
                    ],
                },
                {
                    "label": "Capture a new change request",
                    "when": "The next work is a new idea, bug, or product change that is not yet represented by a requirement.",
                    "commands": [
                        f'aspec dcr create --title "{followup_title}" --classification implement-now',
                        "aspec status",
                    ],
                },
                {
                    "label": "Inspect the project before choosing",
                    "when": "You want to decide manually from current DCRs, requirements, runs, and outcomes.",
                    "commands": ["aspec status", "aspec outcome", "aspec task list"],
                },
            ]

    blocked_by = [
        {
            "kind": "no_ready_task",
            "message": main_point,
            "accepted_requirements": accepted_requirements,
            "tasks_total": total_tasks,
            "dcrs_ready_for_tasking": classified_dcrs + accepted_dcrs,
        }
    ]
    action = {
        "label": action_label,
        "human_decision_required": True,
        "reason": reason,
        "commands": commands,
        "options": options,
    }
    return stage, main_point, blocked_by, action


def agent_display_for_next_action(action: dict[str, Any]) -> dict[str, Any]:
    """Return command-free next-action text for code-agent user replies."""

    options = []
    for index, option in enumerate(_list_or_empty(action.get("options")), start=1):
        options.append(
            {
                "label": str(option.get("label") or f"Option {index}"),
                "when": str(option.get("when") or "").strip() or None,
            }
        )
    return {
        "label": str(action.get("label") or "Choose the next AgentSpec action."),
        "reason": str(action.get("reason") or "").strip() or None,
        "requires_human_reply": bool(action.get("human_decision_required")),
        "show_terminal_commands": False,
        "guidance": (
            "For Codex or Claude Code responses, present this as plain-language next action "
            "guidance and keep raw terminal commands internal unless the user asks for them."
        ),
        "options": options,
    }


def _with_agent_display(action: dict[str, Any]) -> dict[str, Any]:
    updated = dict(action)
    updated["agent_display"] = agent_display_for_next_action(updated)
    return updated


def _requirement_examples(
    requirements: list[dict[str, Any]],
    *,
    status: str,
    limit: int = 3,
) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for requirement in reversed(requirements):
        if str(requirement.get("status") or "") != status:
            continue
        requirement_id = requirement.get("id")
        if not requirement_id:
            continue
        examples.append(
            {
                "id": str(requirement_id),
                "title": _shell_title(str(requirement.get("title") or requirement_id)),
            }
        )
        if len(examples) >= limit:
            break
    return examples


def _shell_title(value: str) -> str:
    cleaned = " ".join(value.replace('"', "'").split())
    return cleaned[:80] if len(cleaned) > 80 else cleaned


def _status_count(section: dict[str, Any], key: str) -> int:
    by_status = section.get("by_status")
    if not isinstance(by_status, dict):
        return 0
    value = by_status.get(key, 0)
    return int(value) if isinstance(value, int) else 0


def _run_artifact(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "run",
        "id": run.get("run_id"),
        "title": run.get("context_pack_title"),
        "path": run.get("context_pack"),
        "status": run.get("status"),
    }


def _run_blockers(run: dict[str, Any]) -> list[dict[str, Any]]:
    flags = _string_list(run.get("policy_flags"))
    blockers = [{"kind": "policy_flag", "message": flag} for flag in flags]
    reason = run.get("last_review_reason")
    if reason:
        blockers.append({"kind": "reviewer_reason", "message": str(reason)})
    return blockers


def _lifecycle_findings(lifecycle: dict[str, Any]) -> list[dict[str, Any]]:
    blocking = _list_or_empty(lifecycle.get("blocking"))
    warnings = _list_or_empty(lifecycle.get("warnings"))
    return blocking or warnings


def _finding_blockers(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for finding in findings[:5]:
        blockers.append(
            {
                "kind": str(finding.get("type") or "lifecycle_warning"),
                "message": str(finding.get("message") or finding.get("type") or "Lifecycle warning."),
                "path": finding.get("path"),
                "recommendation": finding.get("recommendation"),
            }
        )
    return blockers


def _first_workflow_backfill_command(workflows: dict[str, Any]) -> str | None:
    orphans = workflows.get("orphans")
    if not isinstance(orphans, list):
        return None
    for orphan in orphans:
        if isinstance(orphan, dict) and orphan.get("backfill_command"):
            return str(orphan["backfill_command"])
    return None


def _lifecycle_terms() -> dict[str, str]:
    return {
        "SRC-*": "AgentSpec source snapshot IDs for ingested design or source documents.",
        "R-*": "Requirement IDs compiled from accepted source material and DCRs.",
        "T-*": "Task context pack IDs that bound code-agent work, allowed paths, and verification.",
        "O-*": "Product outcome IDs for user-visible workflows that need proof before readiness claims.",
        "G-*": "Outcome gate IDs for required evidence checks under a product outcome.",
    }


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _readiness_text(readiness: Any) -> str:
    if not isinstance(readiness, dict) or readiness.get("score") is None:
        return "unknown"
    mode = readiness.get("mode") or "unknown"
    return f"{readiness.get('score')}/100 ({mode})"


def _count_text(section: Any) -> str:
    if not isinstance(section, dict):
        return "unknown"
    total = section.get("total", 0)
    by_status = section.get("by_status")
    if not isinstance(by_status, dict) or not by_status:
        return f"{total} total"
    status_text = ", ".join(f"{key}={value}" for key, value in by_status.items())
    return f"{total} total ({status_text})"


def _outcomes_text(outcomes: Any) -> str:
    if not isinstance(outcomes, dict):
        return "unknown"
    score = outcomes.get("score")
    score_text = f"{score}/100" if isinstance(score, int) else "n/a"
    return f"{outcomes.get('readiness', 'unknown')} ({score_text})"


def _maturity_text(maturity: Any) -> str:
    if not isinstance(maturity, dict):
        return "unknown"
    score = maturity.get("score")
    score_text = f"{score}/100" if isinstance(score, int) else "n/a"
    return (
        f"{maturity.get('level', 'unknown')} "
        f"{maturity.get('readiness', 'unknown')} "
        f"({score_text}, enforcement={maturity.get('enforcement', 'unknown')})"
    )


def _workflow_text(workflows: Any) -> str:
    if not isinstance(workflows, dict):
        return "unknown"
    return f"{workflows.get('orphan_count', 0)} orphan(s) / {workflows.get('total', 0)} artifact(s)"


def _agent_profiles_text(agent_profiles: Any) -> str:
    if not isinstance(agent_profiles, dict):
        return "unknown"
    profiles = agent_profiles.get("profiles")
    profile_count = len(profiles) if isinstance(profiles, dict) else 0
    warnings = agent_profiles.get("warnings")
    warning_count = len(warnings) if isinstance(warnings, list) else 0
    return f"{agent_profiles.get('status', 'unknown')} ({profile_count} profile(s), {warning_count} warning(s))"


def _lifecycle_text(lifecycle: Any) -> str:
    if not isinstance(lifecycle, dict):
        return "unknown"
    counts = lifecycle.get("counts") if isinstance(lifecycle.get("counts"), dict) else {}
    return f"{lifecycle.get('readiness', 'unknown')} ({counts.get('warnings', 0)} warning(s))"


def _next_text(next_task: Any) -> str:
    if not isinstance(next_task, dict):
        return "none"
    return f"{next_task.get('id')} {next_task.get('path')} ({next_task.get('type')})"


def _run_text(run: dict[str, Any]) -> str:
    bits = [
        str(run.get("run_id")),
        str(run.get("status")),
        str(run.get("mode")),
    ]
    context_pack = run.get("context_pack")
    if context_pack:
        bits.append(str(context_pack))
    iteration = run.get("iteration")
    max_iterations = run.get("max_iterations")
    if iteration is not None and max_iterations is not None:
        bits.append(f"iter {iteration}/{max_iterations}")
    updated_at = run.get("updated_at")
    if updated_at:
        bits.append(f"updated {updated_at}")
    return " | ".join(bits)


def _session_text(session: dict[str, Any]) -> str:
    bits = [
        str(session.get("session_id")),
        str(session.get("status")),
        str(session.get("mode")),
    ]
    context_pack = session.get("context_pack")
    if context_pack:
        bits.append(str(context_pack))
    branch = session.get("branch")
    if branch:
        bits.append(f"branch {branch}")
    worktree = session.get("worktree")
    if worktree:
        bits.append(f"worktree {worktree}")
    updated_at = session.get("updated_at")
    if updated_at:
        bits.append(f"updated {updated_at}")
    return " | ".join(bits)


def _relative_or_absolute(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
