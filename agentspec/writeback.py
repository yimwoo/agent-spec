from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import load_data, utc_now_iso
from .roadmap import ROADMAP_PATH, check_roadmap


LIFECYCLE_STATUS_SCHEMA = "agentspec.lifecycle_status.v0"
COMPLETION_PROJECTION_SCHEMA = "agentspec.completion_projection.v0"
WRITEBACK_VERIFICATION_SCHEMA = "agentspec.writeback_verification.v0"
PASSING_REVIEW_VERDICTS = frozenset({"ready", "ready-with-warnings"})


def build_completion_projection(root: Path, task_selector: str | Path) -> dict[str, Any]:
    """Project one task's completion write-back readiness from durable state."""

    root = root.resolve()
    task_path = _resolve_context_pack_selector(root, task_selector)
    context_pack = _relative_or_absolute(root, task_path)
    ledger_entry = _ledger_entry(root, context_pack)
    handoff = load_data(root / "agent" / "handoff.yml", {})
    roadmap = check_roadmap(root)
    findings: list[dict[str, Any]] = []

    if not isinstance(ledger_entry, dict) or ledger_entry.get("status") != "complete":
        findings.append(
            {
                "type": "missing_ledger",
                "severity": "warning",
                "context_pack": context_pack,
                "message": "Task has no complete task-ledger entry.",
                "repair": f"aspec task complete {context_pack} --test-status passed",
            }
        )
    else:
        verification = ledger_entry.get("verification") if isinstance(ledger_entry.get("verification"), dict) else {}
        if verification.get("status") != "passed":
            findings.append(
                {
                    "type": "missing_verification",
                    "severity": "warning",
                    "context_pack": context_pack,
                    "message": "Task ledger does not record passed verification.",
                    "repair": f"aspec task complete {context_pack} --test-status passed",
                }
            )
        review = ledger_entry.get("code_review") if isinstance(ledger_entry.get("code_review"), dict) else {}
        review_warning = _review_link_warning(root, context_pack, review)
        if review_warning is not None:
            findings.append({**review_warning, "repair": f"aspec review code --task {context_pack}"})

    handoff_finding = _selected_handoff_warning(context_pack, ledger_entry, handoff)
    if handoff_finding is not None:
        findings.append(handoff_finding)

    if not roadmap.get("current"):
        findings.append(
            {
                "type": "stale_roadmap",
                "severity": "warning",
                "path": str(ROADMAP_PATH),
                "message": str(roadmap.get("summary") or "Roadmap is missing or stale."),
                "repair": "aspec roadmap",
            }
        )

    return {
        "schema": COMPLETION_PROJECTION_SCHEMA,
        "context_pack": context_pack,
        "task_id": _task_id_from_context_pack(context_pack),
        "status": "ready" if not findings else "needs_attention",
        "ledger": ledger_entry,
        "handoff": _handoff_summary_for_task(handoff, context_pack),
        "roadmap": roadmap,
        "findings": findings,
    }


def update_task_ledger(root: Path, completion: dict[str, Any]) -> dict[str, Any]:
    """Write completion status through the canonical task-ledger helper."""

    from .task import record_task_ledger_status

    context_pack = _required_string(completion, "context_pack")
    verification = completion.get("verification") if isinstance(completion.get("verification"), dict) else {}
    code_review = completion.get("code_review") if isinstance(completion.get("code_review"), dict) else None
    return record_task_ledger_status(
        root.resolve(),
        context_pack=context_pack,
        status=str(completion.get("status") or "complete"),
        run_id=_optional_string(completion.get("run_id")),
        reason=_optional_string(completion.get("completion_reason") or completion.get("reason")),
        test_status=_optional_string(verification.get("status") or completion.get("test_status") or "not_run"),
        updated_at=_optional_string(completion.get("updated_at")) or utc_now_iso(),
        code_review=code_review,
    )


def update_handoff(
    root: Path,
    completion: dict[str, Any],
    project_status: dict[str, Any],
) -> dict[str, Any]:
    """Write project handoff through the canonical handoff helper."""

    from .handoff import write_project_handoff

    return write_project_handoff(
        root.resolve(),
        completed_state=completion,
        project_status=project_status,
    )


def update_roadmap(root: Path) -> Path:
    """Regenerate the canonical roadmap projection."""

    from .roadmap import write_roadmap

    return write_roadmap(root.resolve())


def verify_writeback(root: Path, completion: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Return readiness diagnostics for a selected task completion."""

    selector = completion if isinstance(completion, (str, Path)) else _required_string(completion, "context_pack")
    projection = build_completion_projection(root.resolve(), selector)
    findings = projection.get("findings") if isinstance(projection.get("findings"), list) else []
    return {
        "schema": WRITEBACK_VERIFICATION_SCHEMA,
        "context_pack": projection["context_pack"],
        "ready": not findings,
        "findings": findings,
        "projection": projection,
    }


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


def _ledger_entry(root: Path, context_pack: str) -> dict[str, Any] | None:
    ledger = load_data(root / "agent" / "task-ledger.yml", {}) or {}
    tasks = ledger.get("tasks") if isinstance(ledger, dict) else {}
    if not isinstance(tasks, dict):
        return None
    entry = tasks.get(context_pack)
    return entry if isinstance(entry, dict) else None


def _selected_handoff_warning(
    context_pack: str,
    ledger_entry: dict[str, Any] | None,
    handoff: Any,
) -> dict[str, Any] | None:
    if not isinstance(ledger_entry, dict) or ledger_entry.get("status") != "complete":
        return None
    if not isinstance(handoff, dict) or not handoff:
        return {
            "type": "missing_handoff",
            "severity": "warning",
            "context_pack": context_pack,
            "path": "agent/handoff.yml",
            "message": "Task is complete, but project handoff is missing.",
            "repair": "aspec task complete <task> --test-status passed",
        }
    last = handoff.get("last_completed_task") if isinstance(handoff.get("last_completed_task"), dict) else {}
    if last.get("context_pack") != context_pack:
        return {
            "type": "stale_handoff",
            "severity": "warning",
            "context_pack": context_pack,
            "path": "agent/handoff.yml",
            "message": "Project handoff does not point at the selected completed task.",
            "repair": "aspec task complete <task> --test-status passed",
        }
    if ledger_entry.get("run_id") and last.get("run_id") != ledger_entry.get("run_id"):
        return {
            "type": "stale_handoff",
            "severity": "warning",
            "context_pack": context_pack,
            "path": "agent/handoff.yml",
            "message": "Project handoff run id does not match the task-ledger completion.",
            "repair": "aspec task complete <task> --test-status passed",
        }
    return None


def _handoff_summary_for_task(handoff: Any, context_pack: str) -> dict[str, Any]:
    if not isinstance(handoff, dict) or not handoff:
        return {"present": False, "matches_task": False}
    last = handoff.get("last_completed_task") if isinstance(handoff.get("last_completed_task"), dict) else {}
    return {
        "present": True,
        "matches_task": last.get("context_pack") == context_pack,
        "last_completed_task": last,
    }


def _resolve_context_pack_selector(root: Path, selector: str | Path) -> Path:
    raw = str(selector).strip()
    if not raw:
        raise ValueError("Task selector is required.")
    candidate = Path(raw)
    if candidate.suffix == ".md" or "/" in raw:
        return _resolve_context_pack(root, candidate)
    if raw.startswith("T-"):
        matches = sorted((root / "agent" / "context-packs").glob(f"{raw}-*.md"))
        if not matches:
            raise FileNotFoundError(f"Context pack not found for task id: {raw}")
        if len(matches) > 1:
            rels = ", ".join(str(path.relative_to(root)) for path in matches)
            raise ValueError(f"Task id {raw} is ambiguous: {rels}")
        return matches[0].resolve()
    return _resolve_context_pack(root, candidate)


def _resolve_context_pack(root: Path, context_pack: Path) -> Path:
    path = context_pack if context_pack.is_absolute() else root / context_pack
    if not path.exists():
        raise FileNotFoundError(f"Context pack not found: {context_pack}")
    return path.resolve()


def _task_id_from_context_pack(context_pack: str) -> str | None:
    name = Path(context_pack).name
    return name.split("-", 1)[0] if name.startswith("T-") else None


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"completion must include {key!r}.")
    return value


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


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
