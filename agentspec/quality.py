from __future__ import annotations

from pathlib import Path
from typing import Any

from .doctor import AGENT_CONTEXT_RECOVERY_COMMAND, run_doctor
from .io import ensure_writable_dir, load_data, utc_now_iso, write_data, write_text
from .status import build_project_status


QUALITY_GC_SCHEMA = "agentspec.quality_gc_report.v0"
DEFAULT_TASK_INTERVAL = 3


def run_quality_gc(
    root: Path,
    *,
    report_dir: Path | None = None,
    task_interval: int = DEFAULT_TASK_INTERVAL,
) -> dict[str, Any]:
    """Run a read-only quality garbage-collection scan.

    The scan reuses existing status and doctor diagnostics, then writes a
    compact quality report that can be reviewed or committed as the latest
    project quality grade.
    """

    root = root.resolve()
    if task_interval < 1:
        raise ValueError("task_interval must be >= 1.")

    destination = _quality_destination(root, report_dir)
    ensure_writable_dir(destination, label="Quality report destination")
    previous = load_data(destination / "latest.yml", {})

    status = build_project_status(root)
    doctor = run_doctor(root, report_dir=report_dir)
    findings = _findings(status, doctor)
    completed_tasks = int(status.get("tasks", {}).get("by_status", {}).get("complete", 0))
    cadence = _cadence(
        previous,
        completed_tasks=completed_tasks,
        task_interval=task_interval,
    )
    report = {
        "schema": QUALITY_GC_SCHEMA,
        "generated_at": utc_now_iso(),
        "grade": _grade(findings),
        "summary": _summary(findings),
        "findings": findings,
        "project_status": _project_status_summary(status),
        "doctor": _doctor_summary(doctor),
        "handoff": _handoff_summary(status.get("handoff")),
        "cadence": cadence,
        "reports": {
            "structured": str(_relative_to_root(root, destination / "latest.yml")),
            "markdown": str(_relative_to_root(root, destination / "latest.md")),
        },
    }
    write_data(destination / "latest.yml", report)
    write_text(destination / "latest.md", _markdown_report(report))
    return report


def quality_gc_cadence_status(
    root: Path,
    *,
    report_dir: Path | None = None,
    task_interval: int = DEFAULT_TASK_INTERVAL,
) -> dict[str, Any]:
    """Return the task-completion cadence state without writing reports."""

    root = root.resolve()
    if task_interval < 1:
        raise ValueError("task_interval must be >= 1.")

    destination = _quality_destination(root, report_dir)
    previous = load_data(destination / "latest.yml", {})
    status = build_project_status(root)
    completed_tasks = int(status.get("tasks", {}).get("by_status", {}).get("complete", 0))
    return _cadence(
        previous,
        completed_tasks=completed_tasks,
        task_interval=task_interval,
    )


def _quality_destination(root: Path, report_dir: Path | None) -> Path:
    if report_dir is None:
        return root / "reports" / "quality"
    base = report_dir if report_dir.is_absolute() else root / report_dir
    return base / "quality"


def _findings(status: dict[str, Any], doctor: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    agent_context = doctor.get("agent_context", {})
    for warning in agent_context.get("warnings", []) if isinstance(agent_context, dict) else []:
        findings.append(
            {
                "id": f"QG-AGENT-CONTEXT-{len(findings) + 1:03d}",
                "category": "agent_context_freshness",
                "severity": "warning",
                "title": "Generated agent context is stale or missing.",
                "message": warning.get("message", "Generated agent context needs refresh."),
                "path": warning.get("path"),
                "recovery_command": warning.get("recovery_command", AGENT_CONTEXT_RECOVERY_COMMAND),
            }
        )

    invariants = doctor.get("project_invariants", {})
    if isinstance(invariants, dict) and invariants.get("status") == "not_configured":
        findings.append(
            {
                "id": "QG-INVARIANTS-001",
                "category": "golden_principles",
                "severity": "info",
                "title": "Project golden principles are not configured.",
                "message": "No agent/policies/invariants.yml file is configured for mechanical project rules.",
                "path": invariants.get("path", "agent/policies/invariants.yml"),
                "recovery_command": "Create agent/policies/invariants.yml with project-specific required_path or forbidden_path rules.",
            }
        )
    elif isinstance(invariants, dict):
        for result in invariants.get("results", []):
            if not isinstance(result, dict) or result.get("status") not in {"failed", "invalid"}:
                continue
            findings.append(
                {
                    "id": f"QG-INVARIANTS-{len(findings) + 1:03d}",
                    "category": "golden_principles",
                    "severity": str(result.get("severity", "warning")),
                    "title": "Project invariant needs attention.",
                    "message": result.get("message", "Project invariant did not pass."),
                    "path": result.get("path") or result.get("pattern"),
                    "invariant_id": result.get("id"),
                }
            )

    open_questions = _open_question_count(status)
    if open_questions:
        findings.append(
            {
                "id": "QG-OPEN-QUESTIONS-001",
                "category": "open_questions",
                "severity": "info",
                "title": "Open questions remain.",
                "message": f"{open_questions} open question(s) remain in discovery state.",
                "path": "docs/discovery/open-questions.yml",
                "count": open_questions,
            }
        )

    if status.get("handoff") is None:
        findings.append(
            {
                "id": "QG-HANDOFF-001",
                "category": "handoff",
                "severity": "info",
                "title": "No committed handoff is present.",
                "message": "agent/handoff.yml is missing; complete a task to write continuation state.",
                "path": "agent/handoff.yml",
            }
        )

    outcomes = status.get("outcomes")
    if isinstance(outcomes, dict) and outcomes.get("readiness") != "ready":
        blockers = outcomes.get("blockers") if isinstance(outcomes.get("blockers"), list) else []
        findings.append(
            {
                "id": "QG-OUTCOMES-001",
                "category": "product_outcomes",
                "severity": "warning",
                "title": "Product outcome readiness is not green.",
                "message": outcomes.get("summary", "Product outcomes are not ready."),
                "path": outcomes.get("path", "agent/outcomes.yml"),
                "readiness": outcomes.get("readiness"),
                "blocker_count": len(blockers),
                "recovery_command": "aspec outcome",
            }
        )

    return findings


def _open_question_count(status: dict[str, Any]) -> int:
    root = Path(str(status.get("root", ".")))
    questions = load_data(root / "docs" / "discovery" / "open-questions.yml", [])
    if not isinstance(questions, list):
        return 0
    return sum(1 for question in questions if isinstance(question, dict) and question.get("status", "open") == "open")


def _grade(findings: list[dict[str, Any]]) -> str:
    severities = {finding.get("severity") for finding in findings}
    if "error" in severities:
        return "C"
    if "warning" in severities:
        return "B"
    return "A"


def _summary(findings: list[dict[str, Any]]) -> str:
    warnings = sum(1 for finding in findings if finding.get("severity") == "warning")
    errors = sum(1 for finding in findings if finding.get("severity") == "error")
    infos = sum(1 for finding in findings if finding.get("severity") == "info")
    return f"{errors} error(s), {warnings} warning(s), {infos} info finding(s)."


def _project_status_summary(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall": status.get("overall"),
        "readiness": status.get("readiness", {}),
        "requirements": _count_summary(status.get("requirements")),
        "dcrs": _count_summary(status.get("dcrs")),
        "tasks": _count_summary(status.get("tasks")),
        "runs": _count_summary(status.get("runs")),
        "outcomes": _outcome_summary(status.get("outcomes")),
        "next_task": status.get("tasks", {}).get("next") if isinstance(status.get("tasks"), dict) else None,
    }


def _doctor_summary(doctor: dict[str, Any]) -> dict[str, Any]:
    agent_context = doctor.get("agent_context", {}) if isinstance(doctor.get("agent_context"), dict) else {}
    invariants = doctor.get("project_invariants", {}) if isinstance(doctor.get("project_invariants"), dict) else {}
    return {
        "agent_context_status": agent_context.get("status"),
        "agent_context_warning_count": len(agent_context.get("warnings", [])),
        "agent_context_recovery_command": agent_context.get("recovery_command", AGENT_CONTEXT_RECOVERY_COMMAND),
        "project_invariants_status": invariants.get("status"),
        "project_invariants_path": invariants.get("path"),
    }


def _outcome_summary(outcomes: Any) -> dict[str, Any]:
    if not isinstance(outcomes, dict):
        return {}
    counts = outcomes.get("counts") if isinstance(outcomes.get("counts"), dict) else {}
    return {
        "readiness": outcomes.get("readiness"),
        "score": outcomes.get("score"),
        "counts": counts,
    }


def _handoff_summary(handoff: Any) -> dict[str, Any]:
    if not isinstance(handoff, dict):
        return {"present": False, "path": "agent/handoff.yml"}
    last_task = handoff.get("last_completed_task") if isinstance(handoff.get("last_completed_task"), dict) else {}
    next_action = handoff.get("next_action") if isinstance(handoff.get("next_action"), dict) else {}
    return {
        "present": True,
        "path": handoff.get("path", "agent/handoff.yml"),
        "updated_at": handoff.get("updated_at"),
        "last_completed_task": last_task.get("id"),
        "next_action": next_action.get("kind"),
        "next_command": next_action.get("command"),
    }


def _cadence(previous: Any, *, completed_tasks: int, task_interval: int) -> dict[str, Any]:
    previous_completed = None
    if isinstance(previous, dict):
        previous_cadence = previous.get("cadence")
        if isinstance(previous_cadence, dict) and isinstance(previous_cadence.get("completed_tasks"), int):
            previous_completed = previous_cadence["completed_tasks"]
    completed_since = None if previous_completed is None else max(0, completed_tasks - previous_completed)
    return {
        "task_interval": task_interval,
        "completed_tasks": completed_tasks,
        "completed_tasks_at_last_quality": previous_completed,
        "completed_tasks_since_last_quality": completed_since,
        "was_due": previous_completed is None or (completed_since is not None and completed_since >= task_interval),
        "next_recommended_completed_tasks": completed_tasks + task_interval,
    }


def _count_summary(section: Any) -> dict[str, Any]:
    if not isinstance(section, dict):
        return {"total": 0}
    return {
        key: value
        for key, value in {
            "total": section.get("total", 0),
            "by_status": section.get("by_status"),
            "by_type": section.get("by_type"),
            "by_mode": section.get("by_mode"),
        }.items()
        if value is not None
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Quality GC Report",
        "",
        f"- Grade: {report.get('grade')}",
        f"- Generated: {report.get('generated_at')}",
        f"- Summary: {report.get('summary')}",
        "",
        "## Cadence",
        "",
    ]
    cadence = report.get("cadence", {})
    lines.extend(
        [
            f"- Completed tasks: {cadence.get('completed_tasks')}",
            f"- Task interval: {cadence.get('task_interval')}",
            f"- Was due: {cadence.get('was_due')}",
            f"- Next recommended completed-task count: {cadence.get('next_recommended_completed_tasks')}",
            "",
            "## Findings",
            "",
        ]
    )
    findings = report.get("findings", [])
    if findings:
        for finding in findings:
            path = f" `{finding.get('path')}`" if finding.get("path") else ""
            command = f" Recovery: `{finding.get('recovery_command')}`" if finding.get("recovery_command") else ""
            title = str(finding.get("title", finding.get("id"))).rstrip(".")
            lines.append(
                f"- [{finding.get('severity', 'info')}] {title}:{path} "
                f"{finding.get('message', '-')}{command}"
            )
    else:
        lines.append("- No quality GC findings.")
    lines.extend(["", "## Handoff", ""])
    handoff = report.get("handoff", {})
    lines.extend(
        [
            f"- Present: {handoff.get('present')}",
            f"- Last completed task: {handoff.get('last_completed_task', '-')}",
            f"- Next action: {handoff.get('next_action', '-')}",
            f"- Next command: `{handoff.get('next_command', '-')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def _relative_to_root(root: Path, path: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path
