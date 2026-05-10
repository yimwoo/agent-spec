from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from typing import Any

from .dcr import list_dcrs
from .handoff import load_project_handoff
from .io import load_data
from .maturity import build_maturity_status
from .outcome import build_outcome_status
from .session import build_session_status
from .task import list_task_context_packs, next_task_context_pack


PROJECT_STATUS_SCHEMA = "agentspec.project_status.v0"
ACTIVE_RUN_STATUSES = {"started", "running"}
ATTENTION_RUN_STATUSES = {"paused", "halted"}


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

    active_runs = [run for run in runs if run.get("status") in ACTIVE_RUN_STATUSES]
    attention_runs = [run for run in runs if run.get("status") in ATTENTION_RUN_STATUSES]
    recent_runs = sorted(runs, key=lambda run: str(run.get("updated_at", "")), reverse=True)[:recent_limit]

    payload = {
        "schema": PROJECT_STATUS_SCHEMA,
        "root": str(root),
        "overall": _overall_status(next_task=next_task, active_runs=active_runs, attention_runs=attention_runs),
        "recommendation": _recommendation(next_task=next_task, active_runs=active_runs, attention_runs=attention_runs),
        "readiness": {
            "score": readiness.get("score"),
            "mode": readiness.get("mode"),
            "summary": readiness.get("summary"),
        },
        "outcomes": outcomes,
        "maturity": maturity,
        "requirements": {
            "total": len(requirements),
            "by_status": _counts(record.get("status") for record in requirements),
            "by_priority": _counts(record.get("priority") for record in requirements),
        },
        "dcrs": {
            "total": len(dcrs),
            "by_status": _counts(record.get("status") for record in dcrs),
            "by_classification": _counts(record.get("classification") for record in dcrs),
        },
        "tasks": {
            "total": len(tasks),
            "by_status": _counts(record.get("status") for record in tasks),
            "by_type": _counts(record.get("type") for record in tasks),
            "ready": [record for record in tasks if record.get("status") == "ready"],
            "next": next_task,
        },
        "runs": {
            "total": len(runs),
            "by_status": _counts(run.get("status") for run in runs),
            "by_mode": _counts(run.get("mode") for run in runs),
            "active": active_runs,
            "attention": attention_runs,
            "recent": recent_runs,
        },
        "sessions": sessions,
    }
    handoff = load_project_handoff(root)
    if handoff is not None:
        payload["handoff"] = handoff
    return payload


def load_run_records(root: Path) -> list[dict[str, Any]]:
    """Return normalized run records with recovery context."""

    return _load_runs(root.resolve())


def format_project_status(status: dict[str, Any]) -> str:
    readiness = status.get("readiness", {})
    requirements = status.get("requirements", {})
    dcrs = status.get("dcrs", {})
    tasks = status.get("tasks", {})
    runs = status.get("runs", {})
    sessions = status.get("sessions", {})
    maturity = status.get("maturity", {})
    outcomes = status.get("outcomes", {})

    lines = [
        "AgentSpec Status",
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
        f"Next: {_next_text(tasks.get('next'))}",
        f"Recommendation: {status.get('recommendation')}",
    ]

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
    policy_flags = reviewer.get("policy_flags") if reviewer else []
    if not isinstance(policy_flags, list):
        policy_flags = []

    return {
        "last_review_reason": reviewer.get("reason") if reviewer else None,
        "policy_flags": [str(flag) for flag in policy_flags],
        "test_status": _test_status_from_event(executor) or _test_status_from_state(data),
        "last_event_ref": reviewer.get("_event_ref") if reviewer else None,
        "recovery_command": _recovery_command(str(record.get("run_id") or run_dir.name), str(record.get("status", "unknown"))),
    }


def _last_event(events: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    for event in reversed(events):
        if event.get("kind") == kind:
            return event
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
) -> str:
    if attention_runs:
        return "attention_needed"
    if active_runs:
        return "running"
    if next_task:
        return "ready"
    return "idle"


def _recommendation(
    *,
    next_task: dict[str, Any] | None,
    active_runs: list[dict[str, Any]],
    attention_runs: list[dict[str, Any]],
) -> str:
    if attention_runs:
        run_id = attention_runs[0].get("run_id")
        return f"Inspect attention-needed run with `aspec run inspect {run_id}`."
    if active_runs:
        run_id = active_runs[0].get("run_id")
        return f"Continue active run with `aspec run prompt {run_id}` or `aspec run loop --run-id {run_id}`."
    if next_task:
        return f"Start next ready task with `aspec run loop {next_task.get('path')}`."
    return "No ready task context pack found; create or classify the next DCR/task, or run autonomous research mode."


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
