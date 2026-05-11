from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import load_data
from .roadmap import ROADMAP_PATH, check_roadmap


LIFECYCLE_STATUS_SCHEMA = "agentspec.lifecycle_status.v0"
PASSING_REVIEW_VERDICTS = frozenset({"ready", "ready-with-warnings"})


def build_lifecycle_projection(
    root: Path,
    *,
    project_counts: dict[str, dict[str, Any]],
    workflows: dict[str, Any],
    handoff: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a read-only lifecycle and write-back readiness projection.

    This intentionally derives state from existing AgentSpec artifacts instead
    of introducing a new lifecycle state store.
    """

    root = root.resolve()
    warnings: list[dict[str, Any]] = []
    warnings.extend(_workflow_warnings(workflows))
    warnings.extend(_completion_warnings(root))
    warnings.extend(_handoff_warnings(handoff, project_counts))
    warnings.extend(_roadmap_warnings(root))
    readiness = "needs_attention" if warnings else "ready"
    return {
        "schema": LIFECYCLE_STATUS_SCHEMA,
        "readiness": readiness,
        "summary": _summary(readiness, warnings),
        "counts": {
            "warnings": len(warnings),
            "blocking": 0,
        },
        "warnings": warnings,
    }


def lifecycle_warning_lines(lifecycle: dict[str, Any]) -> list[str]:
    warnings = lifecycle.get("warnings") if isinstance(lifecycle.get("warnings"), list) else []
    lines: list[str] = []
    for warning in warnings:
        if not isinstance(warning, dict):
            continue
        message = warning.get("message") or warning.get("type") or "Lifecycle warning"
        target = warning.get("context_pack") or warning.get("workflow") or warning.get("path")
        suffix = f" ({target})" if target and str(target) not in str(message) else ""
        lines.append(f"{warning.get('type', 'warning')}: {message}{suffix}")
    return lines


def _workflow_warnings(workflows: dict[str, Any]) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    for orphan in _list(workflows.get("orphans")):
        path = orphan.get("path")
        warnings.append(
            {
                "type": "orphan_workflow",
                "severity": "warning",
                "workflow": path,
                "message": f"Workflow has no referencing task context pack: {path}.",
                "recommendation": orphan.get("backfill_command"),
            }
        )
    for broken in _list(workflows.get("broken_links")):
        warnings.append(
            {
                "type": "broken_workflow_link",
                "severity": "warning",
                "workflow": broken.get("workflow"),
                "context_pack": broken.get("context_pack") or broken.get("task_pack"),
                "message": broken.get("message") or "Workflow/task link is broken.",
            }
        )
    return warnings


def _completion_warnings(root: Path) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    ledger = load_data(root / "agent" / "task-ledger.yml", {}) or {}
    tasks = ledger.get("tasks") if isinstance(ledger, dict) else {}
    if not isinstance(tasks, dict):
        return warnings

    review_contract_started_at = _review_contract_started_at(tasks)
    for context_pack, entry in sorted(tasks.items()):
        if not isinstance(context_pack, str) or not isinstance(entry, dict):
            continue
        if entry.get("status") != "complete":
            continue
        verification = entry.get("verification") if isinstance(entry.get("verification"), dict) else {}
        if verification.get("status") != "passed":
            warnings.append(
                {
                    "type": "missing_verification",
                    "severity": "warning",
                    "context_pack": context_pack,
                    "message": "Completed task lacks passed verification evidence.",
                }
            )
        review = entry.get("code_review") if isinstance(entry.get("code_review"), dict) else {}
        if _review_link_required(entry, review_contract_started_at):
            review_warning = _review_link_warning(root, context_pack, review)
            if review_warning is not None:
                warnings.append(review_warning)
    return warnings


def _review_link_warning(
    root: Path,
    context_pack: str,
    review: dict[str, Any],
) -> dict[str, Any] | None:
    review_id = review.get("id")
    if not review_id:
        return {
            "type": "missing_review",
            "severity": "warning",
            "context_pack": context_pack,
            "message": "Completed task lacks linked code review evidence.",
        }

    path = _review_artifact_path(root, review)
    record = load_data(path)
    if not isinstance(record, dict):
        return {
            "type": "missing_review",
            "severity": "warning",
            "context_pack": context_pack,
            "path": _relative_or_absolute(root, path),
            "message": f"Completed task links code review {review_id}, but review evidence is missing.",
        }
    verdict = record.get("verdict")
    if verdict not in PASSING_REVIEW_VERDICTS:
        return {
            "type": "missing_review",
            "severity": "warning",
            "context_pack": context_pack,
            "path": _relative_or_absolute(root, path),
            "message": f"Completed task links code review {review_id}, but verdict is {verdict!r}.",
        }
    task = record.get("task") if isinstance(record.get("task"), dict) else {}
    if task.get("context_pack") != context_pack:
        return {
            "type": "missing_review",
            "severity": "warning",
            "context_pack": context_pack,
            "path": _relative_or_absolute(root, path),
            "message": f"Completed task links code review {review_id}, but the review targets another task.",
        }
    return None


def _review_artifact_path(root: Path, review: dict[str, Any]) -> Path:
    path = review.get("path")
    if isinstance(path, str) and path.strip():
        candidate = Path(path)
        return candidate if candidate.is_absolute() else root / candidate
    return root / "agent" / "reviews" / f"{review.get('id')}.yml"


def _review_contract_started_at(tasks: dict[Any, Any]) -> str | None:
    reviewed_completion_times = [
        str(entry.get("updated_at"))
        for entry in tasks.values()
        if isinstance(entry, dict)
        and entry.get("status") == "complete"
        and isinstance(entry.get("code_review"), dict)
        and entry["code_review"].get("id")
        and entry.get("updated_at")
    ]
    return min(reviewed_completion_times) if reviewed_completion_times else None


def _review_link_required(entry: dict[str, Any], review_contract_started_at: str | None) -> bool:
    if review_contract_started_at is None:
        return True
    updated_at = entry.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at:
        return True
    return updated_at >= review_contract_started_at


def _handoff_warnings(
    handoff: dict[str, Any] | None,
    project_counts: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(handoff, dict):
        return []
    current = handoff.get("current_state") if isinstance(handoff.get("current_state"), dict) else {}
    mismatches: list[str] = []
    for key in ("requirements", "dcrs", "tasks", "runs"):
        expected = _total(project_counts.get(key))
        actual = _total(current.get(key)) if isinstance(current, dict) else None
        if actual is not None and expected is not None and actual != expected:
            mismatches.append(f"{key}: handoff={actual}, current={expected}")
    if not mismatches:
        return []
    return [
        {
            "type": "stale_handoff",
            "severity": "warning",
            "path": "agent/handoff.yml",
            "message": "Handoff current_state does not match current project status.",
            "details": mismatches,
        }
    ]


def _roadmap_warnings(root: Path) -> list[dict[str, Any]]:
    if not (root / ROADMAP_PATH).exists():
        return []
    result = check_roadmap(root)
    if result.get("current"):
        return []
    return [
        {
            "type": "stale_roadmap",
            "severity": "warning",
            "path": str(ROADMAP_PATH),
            "message": str(result.get("summary") or "Roadmap is stale."),
            "recommendation": "aspec roadmap",
        }
    ]


def _summary(readiness: str, warnings: list[dict[str, Any]]) -> str:
    if readiness == "ready":
        return "Lifecycle projection has no warnings."
    return f"Lifecycle projection has {len(warnings)} warning(s)."


def _list(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _total(value: Any) -> int | None:
    if not isinstance(value, dict):
        return None
    total = value.get("total")
    return total if isinstance(total, int) else None


def _relative_or_absolute(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)
