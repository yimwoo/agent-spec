from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import load_data, write_data


HANDOFF_SCHEMA = "agentspec.project_handoff.v0"
HANDOFF_PATH = Path("agent/handoff.yml")


def load_project_handoff(root: Path) -> dict[str, Any] | None:
    data = load_data(root / HANDOFF_PATH)
    if not isinstance(data, dict):
        return None
    payload = dict(data)
    payload["path"] = str(HANDOFF_PATH)
    return payload


def write_project_handoff(
    root: Path,
    *,
    completed_state: dict[str, Any],
    project_status: dict[str, Any],
) -> dict[str, Any]:
    payload = build_project_handoff(root, completed_state=completed_state, project_status=project_status)
    write_data(root / HANDOFF_PATH, payload)
    return payload


def build_project_handoff(
    root: Path,
    *,
    completed_state: dict[str, Any],
    project_status: dict[str, Any],
) -> dict[str, Any]:
    updated_at = str(completed_state.get("updated_at") or "")
    payload = {
        "schema": HANDOFF_SCHEMA,
        "updated_at": updated_at,
        "root": ".",
        "last_completed_task": _last_completed_task(completed_state),
        "current_state": _current_state(project_status),
        "next_action": _next_action(project_status),
        "commands": {
            "status": "aspec status --json",
            "next_action": "aspec continue",
            "task_next": "aspec task next",
        },
        "artifacts": {
            "task_ledger": "agent/task-ledger.yml",
            "handoff": str(HANDOFF_PATH),
        },
    }
    code_review = completed_state.get("code_review")
    if isinstance(code_review, dict):
        payload["artifacts"]["last_code_review"] = code_review.get("path") or f"agent/reviews/{code_review.get('id')}.yml"
    return payload


def _last_completed_task(completed_state: dict[str, Any]) -> dict[str, Any]:
    context_pack = str(completed_state.get("context_pack") or "")
    task = {
        "id": _task_id(context_pack),
        "context_pack": context_pack,
        "title": completed_state.get("context_pack_title"),
        "run_id": completed_state.get("run_id"),
        "reason": completed_state.get("completion_reason"),
        "updated_at": completed_state.get("updated_at"),
        "verification": completed_state.get("verification", {}),
    }
    code_review = completed_state.get("code_review")
    if isinstance(code_review, dict):
        task["code_review"] = {
            key: code_review.get(key)
            for key in ("id", "verdict", "reviewer", "range", "path")
            if code_review.get(key) is not None
        }
    return task


def _current_state(project_status: dict[str, Any]) -> dict[str, Any]:
    return {
        "overall": project_status.get("overall"),
        "recommendation": project_status.get("recommendation"),
        "readiness": project_status.get("readiness", {}),
        "requirements": _counts(project_status.get("requirements")),
        "dcrs": _counts(project_status.get("dcrs")),
        "tasks": _counts(project_status.get("tasks")),
        "runs": _counts(project_status.get("runs")),
    }


def _next_action(project_status: dict[str, Any]) -> dict[str, Any]:
    runs = project_status.get("runs") if isinstance(project_status.get("runs"), dict) else {}
    attention = runs.get("attention") if isinstance(runs, dict) else []
    active = runs.get("active") if isinstance(runs, dict) else []
    tasks = project_status.get("tasks") if isinstance(project_status.get("tasks"), dict) else {}
    next_task = tasks.get("next") if isinstance(tasks, dict) else None

    if isinstance(attention, list) and attention:
        run_id = attention[0].get("run_id")
        return {
            "kind": "inspect_attention_run",
            "run_id": run_id,
            "command": f"aspec run inspect {run_id}",
        }
    if isinstance(active, list) and active:
        run_id = active[0].get("run_id")
        return {
            "kind": "continue_active_run",
            "run_id": run_id,
            "command": f"aspec run prompt {run_id}",
        }
    if isinstance(next_task, dict):
        path = next_task.get("path")
        return {
            "kind": "start_task",
            "task_id": next_task.get("id"),
            "context_pack": path,
            "command": f"aspec run loop {path}",
        }
    return {
        "kind": "idle",
        "command": "aspec status --json",
    }


def _counts(section: Any) -> dict[str, Any]:
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


def _task_id(context_pack: str) -> str | None:
    match = re.search(r"(T-\d{3,})", Path(context_pack).name)
    return match.group(1) if match else None
