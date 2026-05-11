from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import merged_runtime_config
from .io import load_data, utc_now_iso
from .roadmap import ROADMAP_PATH, check_roadmap


LIFECYCLE_STATUS_SCHEMA = "agentspec.lifecycle_status.v0"
SKILL_GATE_STATUS_SCHEMA = "agentspec.lifecycle_skill_gates.v0"
COMPLETION_PROJECTION_SCHEMA = "agentspec.completion_projection.v0"
WRITEBACK_VERIFICATION_SCHEMA = "agentspec.writeback_verification.v0"
FINISH_PROJECTION_SCHEMA = "agentspec.finish_projection.v0"
FINISH_RESULT_SCHEMA = "agentspec.finish_result.v0"
PASSING_REVIEW_VERDICTS = frozenset({"ready", "ready-with-warnings"})
FINISH_ENFORCEMENTS = frozenset({"warn", "strict"})
SKILL_GATE_IDS = ("design", "plan", "verification", "review", "finish")
STRICT_LIFECYCLE_BLOCKERS = frozenset(
    {
        "orphan_workflow",
        "broken_workflow_link",
        "missing_review",
        "missing_verification",
        "stale_roadmap",
        "skill_gate_missing",
    }
)
STRICT_FINISH_WRITEBACK_BLOCKERS = frozenset({"stale_roadmap"})


class FinishBlockedError(ValueError):
    """Raised when strict finish enforcement blocks task completion."""

    def __init__(self, message: str, projection: dict[str, Any]) -> None:
        super().__init__(message)
        self.projection = projection

    def to_dict(self) -> dict[str, Any]:
        return {"projection": self.projection}


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


def build_finish_projection(
    root: Path,
    task_selector: str | Path | None = None,
    *,
    current: bool = False,
    test_status: str = "not_run",
    review_id: str | None = None,
) -> dict[str, Any]:
    """Build preflight and current write-back diagnostics for a finish request."""

    root = root.resolve()
    context_pack = resolve_finish_selector(root, task_selector, current=current)
    enforcement = _finish_enforcement(root)
    findings: list[dict[str, Any]] = []
    code_review = None

    if test_status != "passed":
        findings.append(
            {
                "type": "missing_verification",
                "severity": "warning",
                "context_pack": context_pack,
                "message": f"Finish verification has not passed; got {test_status!r}.",
                "repair": f"aspec finish {context_pack} --test-status passed --review REVIEW-####",
                "blocks_strict": True,
            }
        )

    if review_id:
        try:
            from .review import validate_completion_review

            code_review = validate_completion_review(root, review_id, context_pack=context_pack)
        except Exception as exc:
            findings.append(
                {
                    "type": "invalid_review",
                    "severity": "warning",
                    "context_pack": context_pack,
                    "review_id": review_id,
                    "message": str(exc),
                    "repair": f"aspec review code --task {context_pack}",
                    "blocks_strict": True,
                }
            )
    else:
        findings.append(
            {
                "type": "missing_review",
                "severity": "warning",
                "context_pack": context_pack,
                "message": "Finish has no linked code review evidence.",
                "repair": f"aspec review code --task {context_pack}",
                "blocks_strict": True,
            }
        )

    current_writeback = verify_writeback(root, context_pack)
    writeback_findings = _finish_writeback_findings(
        current_writeback.get("findings"),
        context_pack=context_pack,
        enforcement=enforcement,
    )
    findings.extend(writeback_findings)
    strict_blockers = [finding for finding in findings if finding.get("blocks_strict") is True]
    return {
        "schema": FINISH_PROJECTION_SCHEMA,
        "context_pack": context_pack,
        "task_id": _task_id_from_context_pack(context_pack),
        "enforcement": enforcement,
        "finishable": not strict_blockers,
        "test_status": test_status,
        "code_review": code_review,
        "findings": findings,
        "strict_blockers": strict_blockers,
        "writeback": current_writeback,
    }


def finish_task(
    root: Path,
    task_selector: str | Path | None = None,
    *,
    current: bool = False,
    dry_run: bool = False,
    run_id: str | None = None,
    reason: str = "Finished by user.",
    test_status: str = "not_run",
    review_id: str | None = None,
) -> dict[str, Any]:
    """Orchestrate task finish through existing completion and write-back APIs."""

    root = root.resolve()
    projection = build_finish_projection(
        root,
        task_selector,
        current=current,
        test_status=test_status,
        review_id=review_id,
    )
    if dry_run:
        return {
            "schema": FINISH_RESULT_SCHEMA,
            "dry_run": True,
            "completed": False,
            "context_pack": projection["context_pack"],
            "enforcement": projection["enforcement"],
            "finishable": projection["finishable"],
            "findings": projection["findings"],
            "projection": projection,
        }

    if projection["enforcement"] == "strict" and projection["strict_blockers"]:
        raise FinishBlockedError(
            "Finish blocked by strict enforcement; resolve findings or switch finish.enforcement to warn.",
            projection,
        )

    from .run import complete_context_pack_run

    state = complete_context_pack_run(
        root,
        str(projection["context_pack"]),
        run_id=run_id,
        reason=reason,
        test_status=test_status,
        review_id=review_id,
    )
    roadmap_path = update_roadmap(root)
    verification = verify_writeback(root, state)
    return {
        "schema": FINISH_RESULT_SCHEMA,
        "dry_run": False,
        "completed": True,
        "context_pack": state["context_pack"],
        "run_id": state["run_id"],
        "enforcement": projection["enforcement"],
        "finishable": projection["finishable"],
        "findings": projection["findings"],
        "state": state,
        "roadmap": str(roadmap_path.relative_to(root)),
        "writeback": verification,
    }


def resolve_finish_selector(
    root: Path,
    task_selector: str | Path | None = None,
    *,
    current: bool = False,
) -> str:
    root = root.resolve()
    if current and task_selector is not None:
        raise ValueError("Select a finish task with either <task-selector> or --current, not both.")
    if current:
        selected = _current_finish_context_pack(root)
        if selected is None:
            raise ValueError("No current task context pack found for finish.")
        return selected
    if task_selector is None:
        raise ValueError("Finish requires <task-selector> or --current.")
    return _relative_or_absolute(root, _resolve_context_pack_selector(root, task_selector))


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
    skill_gates = _build_skill_gate_projection(root, workflows=workflows, handoff=handoff)
    warnings.extend(_list(skill_gates.get("findings")))
    enforcement = _lifecycle_enforcement(root)
    findings = _apply_lifecycle_enforcement(warnings, enforcement=enforcement)
    blocking = [finding for finding in findings if finding.get("severity") == "blocking"]
    readiness = "blocked" if blocking else "needs_attention" if findings else "ready"
    return {
        "schema": LIFECYCLE_STATUS_SCHEMA,
        "enforcement": enforcement,
        "readiness": readiness,
        "summary": _summary(readiness, findings),
        "counts": {
            "warnings": len(findings),
            "blocking": len(blocking),
        },
        "warnings": findings,
        "blocking": blocking,
        "skill_gates": skill_gates,
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
        context_pack = broken.get("context_pack") or broken.get("task_pack")
        warnings.append(
            {
                "type": "broken_workflow_link",
                "severity": "warning",
                "workflow": broken.get("workflow"),
                "context_pack": context_pack,
                "message": broken.get("message") or "Workflow/task link is broken.",
                "repair": f"aspec plan {context_pack}" if context_pack else None,
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
                    "repair": f"aspec finish {context_pack} --test-status passed --review REVIEW-####",
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
            "repair": f"aspec review code --task {context_pack}",
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
            "repair": f"aspec review code --task {context_pack}",
        }
    verdict = record.get("verdict")
    if verdict not in PASSING_REVIEW_VERDICTS:
        return {
            "type": "missing_review",
            "severity": "warning",
            "context_pack": context_pack,
            "path": _relative_or_absolute(root, path),
            "message": f"Completed task links code review {review_id}, but verdict is {verdict!r}.",
            "repair": f"aspec review code --task {context_pack}",
        }
    task = record.get("task") if isinstance(record.get("task"), dict) else {}
    if task.get("context_pack") != context_pack:
        return {
            "type": "missing_review",
            "severity": "warning",
            "context_pack": context_pack,
            "path": _relative_or_absolute(root, path),
            "message": f"Completed task links code review {review_id}, but the review targets another task.",
            "repair": f"aspec review code --task {context_pack}",
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
    for key in ("requirements", "dcrs", "tasks"):
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
            "repair": "aspec roadmap",
        }
    ]


def _build_skill_gate_projection(
    root: Path,
    *,
    workflows: dict[str, Any],
    handoff: dict[str, Any] | None,
) -> dict[str, Any]:
    lifecycle = _lifecycle_config(root)
    raw = lifecycle.get("skill_gates") if isinstance(lifecycle.get("skill_gates"), dict) else {}
    enabled = bool(raw.get("enabled")) if isinstance(raw, dict) else False
    configured_required = _normalize_skill_gate_ids(raw.get("required") if isinstance(raw, dict) else [])
    required = configured_required if enabled else []
    gates = _skill_gate_records(root, workflows=workflows, handoff=handoff, required=required)
    findings = [
        _skill_gate_finding(gate)
        for gate in gates
        if gate.get("required") is True and gate.get("status") == "missing"
    ]
    readiness = "disabled" if not enabled else "needs_attention" if findings else "ready"
    required_gates = [gate for gate in gates if gate.get("required") is True]
    return {
        "schema": SKILL_GATE_STATUS_SCHEMA,
        "enabled": enabled,
        "readiness": readiness,
        "required": required,
        "counts": {
            "gates": len(gates),
            "required": len(required_gates),
            "passed_required": sum(1 for gate in required_gates if gate.get("status") == "passed"),
            "missing_required": sum(1 for gate in required_gates if gate.get("status") == "missing"),
            "not_applicable_required": sum(1 for gate in required_gates if gate.get("status") == "not_applicable"),
        },
        "gates": gates,
        "findings": findings,
    }


def _normalize_skill_gate_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_ids = [value]
    elif isinstance(value, list):
        raw_ids = [item for item in value if isinstance(item, str)]
    else:
        raw_ids = []
    normalized: list[str] = []
    for item in raw_ids:
        gate_id = item.strip().lower().replace("_", "-")
        if gate_id == "workflow":
            gate_id = "plan"
        if gate_id == "writeback":
            gate_id = "finish"
        if gate_id in SKILL_GATE_IDS and gate_id not in normalized:
            normalized.append(gate_id)
    return normalized


def _skill_gate_records(
    root: Path,
    *,
    workflows: dict[str, Any],
    handoff: dict[str, Any] | None,
    required: list[str],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for gate_id in SKILL_GATE_IDS:
        if gate_id == "design":
            record = _design_skill_gate(root)
        elif gate_id == "plan":
            record = _plan_skill_gate(workflows)
        elif gate_id == "verification":
            record = _verification_skill_gate(root)
        elif gate_id == "review":
            record = _review_skill_gate(root)
        else:
            record = _finish_skill_gate(root, handoff)
        record["required"] = gate_id in required
        records.append(record)
    return records


def _design_skill_gate(root: Path) -> dict[str, Any]:
    evidence = _glob_relative(root, "docs/designs/*.md")
    return _skill_gate_record(
        gate_id="design",
        title="Design evidence",
        stage="design",
        evidence=evidence,
        missing_message="Design gate requires a design document under docs/designs/.",
        repair="Create or link a design document under docs/designs/ before implementation.",
    )


def _plan_skill_gate(workflows: dict[str, Any]) -> dict[str, Any]:
    artifacts = _list(workflows.get("artifacts"))
    evidence = [
        str(record.get("path"))
        for record in artifacts
        if isinstance(record.get("path"), str) and record.get("status") == "referenced"
    ]
    missing = not evidence or bool(_list(workflows.get("orphans"))) or bool(_list(workflows.get("broken_links")))
    return _skill_gate_record(
        gate_id="plan",
        title="Planning evidence",
        stage="plan",
        evidence=evidence,
        status="missing" if missing else None,
        missing_message="Planning gate requires a referenced workflow or execution plan.",
        repair="Create an AgentSpec workflow for the task or run aspec task create --from-workflow <path> for an existing plan.",
    )


def _verification_skill_gate(root: Path) -> dict[str, Any]:
    completed = _completed_task_entries(root)
    evidence = [
        context_pack
        for context_pack, entry in completed
        if _dict(entry.get("verification")).get("status") == "passed"
    ]
    status = "not_applicable" if not completed else "missing" if len(evidence) != len(completed) else "passed"
    return _skill_gate_record(
        gate_id="verification",
        title="Verification evidence",
        stage="verification",
        evidence=evidence,
        status=status,
        missing_message="Verification gate requires completed tasks to record passed verification.",
        repair="Run verification and finish the task with --test-status passed.",
    )


def _review_skill_gate(root: Path) -> dict[str, Any]:
    completed = _completed_task_entries(root)
    evidence: list[str] = []
    missing = False
    for context_pack, entry in completed:
        review = _dict(entry.get("code_review"))
        warning = _review_link_warning(root, context_pack, review)
        if warning is not None:
            missing = True
            continue
        review_id = review.get("id")
        if isinstance(review_id, str) and review_id:
            evidence.append(review_id)
    status = "not_applicable" if not completed else "missing" if missing else "passed"
    return _skill_gate_record(
        gate_id="review",
        title="Review evidence",
        stage="review",
        evidence=evidence,
        status=status,
        missing_message="Review gate requires completed tasks to link ready review evidence.",
        repair="Record review evidence with aspec review code --task <task> and link it during finish.",
    )


def _finish_skill_gate(root: Path, handoff: dict[str, Any] | None) -> dict[str, Any]:
    completed = _completed_task_entries(root)
    evidence: list[str] = []
    if isinstance(handoff, dict) and handoff:
        evidence.append("agent/handoff.yml")
    if (root / ROADMAP_PATH).exists() and check_roadmap(root).get("current"):
        evidence.append(str(ROADMAP_PATH))
    status = "not_applicable"
    if completed:
        status = "passed" if len(evidence) == 2 else "missing"
    return _skill_gate_record(
        gate_id="finish",
        title="Finish write-back evidence",
        stage="finish",
        evidence=evidence,
        status=status,
        missing_message="Finish gate requires current handoff and roadmap write-back evidence.",
        repair="Run aspec finish <task> --test-status passed --review REVIEW-####, then aspec roadmap if needed.",
    )


def _skill_gate_record(
    *,
    gate_id: str,
    title: str,
    stage: str,
    evidence: list[str],
    missing_message: str,
    repair: str,
    status: str | None = None,
) -> dict[str, Any]:
    resolved_status = status or ("passed" if evidence else "missing")
    return {
        "id": gate_id,
        "title": title,
        "stage": stage,
        "status": resolved_status,
        "evidence": evidence,
        "message": missing_message if resolved_status == "missing" else None,
        "repair": repair,
    }


def _skill_gate_finding(gate: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "skill_gate_missing",
        "severity": "warning",
        "gate": gate.get("id"),
        "stage": gate.get("stage"),
        "message": gate.get("message") or f"Required lifecycle skill gate is missing: {gate.get('id')}.",
        "repair": gate.get("repair"),
    }


def _glob_relative(root: Path, pattern: str) -> list[str]:
    return [
        _relative_or_absolute(root, path)
        for path in sorted(root.glob(pattern))
        if path.is_file()
    ]


def _completed_task_entries(root: Path) -> list[tuple[str, dict[str, Any]]]:
    ledger = load_data(root / "agent" / "task-ledger.yml", {}) or {}
    tasks = ledger.get("tasks") if isinstance(ledger, dict) else {}
    if not isinstance(tasks, dict):
        return []
    entries: list[tuple[str, dict[str, Any]]] = []
    for context_pack, entry in sorted(tasks.items()):
        if isinstance(context_pack, str) and isinstance(entry, dict) and entry.get("status") == "complete":
            entries.append((context_pack, entry))
    return entries


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


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


def _finish_writeback_findings(
    findings: Any,
    *,
    context_pack: str,
    enforcement: str = "warn",
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for finding in _list(findings):
        copied = dict(finding)
        copied.setdefault("context_pack", context_pack)
        copied["source"] = "writeback"
        copied["blocks_strict"] = (
            enforcement == "strict" and copied.get("type") in STRICT_FINISH_WRITEBACK_BLOCKERS
        )
        if copied.get("type") == "missing_ledger":
            copied["repair"] = f"aspec finish {context_pack} --test-status passed --review REVIEW-####"
        elif copied.get("type") in {"missing_handoff", "stale_handoff"}:
            copied["repair"] = f"aspec finish {context_pack} --test-status passed --review REVIEW-####"
        elif copied.get("type") == "stale_roadmap":
            copied["repair"] = "aspec roadmap"
        results.append(copied)
    return results


def _apply_lifecycle_enforcement(
    findings: list[dict[str, Any]],
    *,
    enforcement: str,
) -> list[dict[str, Any]]:
    if enforcement != "strict":
        return findings
    enforced: list[dict[str, Any]] = []
    for finding in findings:
        copied = dict(finding)
        if copied.get("type") in STRICT_LIFECYCLE_BLOCKERS:
            copied["severity"] = "blocking"
            copied["blocks_strict"] = True
            _ensure_repair_guidance(copied)
        enforced.append(copied)
    return enforced


def _ensure_repair_guidance(finding: dict[str, Any]) -> None:
    if finding.get("repair") or finding.get("recommendation"):
        return
    context_pack = finding.get("context_pack")
    finding_type = finding.get("type")
    if finding_type == "missing_review" and context_pack:
        finding["repair"] = f"aspec review code --task {context_pack}"
    elif finding_type == "missing_verification" and context_pack:
        finding["repair"] = f"aspec finish {context_pack} --test-status passed --review REVIEW-####"
    elif finding_type == "stale_roadmap":
        finding["repair"] = "aspec roadmap"
    elif finding_type == "broken_workflow_link" and context_pack:
        finding["repair"] = f"aspec plan {context_pack}"


def _finish_enforcement(root: Path) -> str:
    config = load_data(root / ".agentspec" / "config.yml", {}) or {}
    if not isinstance(config, dict):
        return "warn"
    finish = config.get("finish") if isinstance(config.get("finish"), dict) else {}
    lifecycle = config.get("lifecycle") if isinstance(config.get("lifecycle"), dict) else {}
    raw = finish.get("enforcement") or lifecycle.get("finish_enforcement") or lifecycle.get("enforcement") or "warn"
    enforcement = str(raw)
    if enforcement == "block":
        enforcement = "strict"
    if enforcement not in FINISH_ENFORCEMENTS:
        allowed = ", ".join(sorted(FINISH_ENFORCEMENTS))
        raise ValueError(f"finish.enforcement must be one of: {allowed}.")
    return enforcement


def _lifecycle_enforcement(root: Path) -> str:
    lifecycle = _lifecycle_config(root)
    raw = lifecycle.get("enforcement") or lifecycle.get("finish_enforcement") or "warn"
    enforcement = str(raw)
    if enforcement == "block":
        enforcement = "strict"
    if enforcement not in FINISH_ENFORCEMENTS:
        allowed = ", ".join(sorted(FINISH_ENFORCEMENTS))
        raise ValueError(f"lifecycle.enforcement must be one of: {allowed}.")
    return enforcement


def _lifecycle_config(root: Path) -> dict[str, Any]:
    config = load_data(root / ".agentspec" / "config.yml", {}) or {}
    if not isinstance(config, dict):
        config = {}
    lifecycle = merged_runtime_config(config).get("lifecycle", {})
    return lifecycle if isinstance(lifecycle, dict) else {}


def _current_finish_context_pack(root: Path) -> str | None:
    active = _active_run_context_packs(root)
    if len(active) == 1:
        return active[0]
    if len(active) > 1:
        raise ValueError("Multiple active runs found; finish requires an explicit task selector.")

    from .task import next_task_context_pack

    next_task = next_task_context_pack(root)
    if isinstance(next_task, dict) and next_task.get("path"):
        return str(next_task["path"])

    handoff = load_data(root / "agent" / "handoff.yml", {}) or {}
    last = handoff.get("last_completed_task") if isinstance(handoff, dict) else {}
    context_pack = last.get("context_pack") if isinstance(last, dict) else None
    return context_pack if isinstance(context_pack, str) and context_pack else None


def _active_run_context_packs(root: Path) -> list[str]:
    run_root = root / "agent" / "runs"
    states: list[tuple[str, str]] = []
    if not run_root.exists():
        return []
    for state_path in run_root.glob("*/state.yml"):
        state = load_data(state_path, {}) or {}
        if not isinstance(state, dict):
            continue
        if state.get("status") not in {"started", "running", "paused"}:
            continue
        context_pack = state.get("context_pack")
        updated_at = state.get("updated_at")
        if isinstance(context_pack, str) and context_pack:
            states.append((str(updated_at or ""), context_pack))
    states.sort(reverse=True)
    return [context_pack for _, context_pack in states]


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
    parts = name.split("-", 2)
    if len(parts) >= 2 and parts[0] == "T" and parts[1].isdigit():
        return f"{parts[0]}-{parts[1]}"
    return None


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
    blocking = [warning for warning in warnings if warning.get("severity") == "blocking"]
    if blocking:
        return f"Lifecycle projection has {len(blocking)} blocking finding(s)."
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
