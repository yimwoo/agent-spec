from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import load_data


OUTCOMES_SCHEMA = "agentspec.outcomes.v0"
OUTCOME_STATUS_SCHEMA = "agentspec.outcome_status.v0"
READY_GATE_STATUSES = {"passed", "ready"}
BLOCKING_GATE_STATUSES = {"blocked", "failed", "missing"}


def build_outcome_status(root: Path) -> dict[str, Any]:
    """Build a read-only product outcome readiness summary.

    Task readiness answers whether AgentSpec has executable work. Outcome
    readiness answers whether critical product workflows have the proof needed
    to claim production-quality behavior.
    """

    root = root.resolve()
    path = root / "agent" / "outcomes.yml"
    data = load_data(path, None)
    configured = isinstance(data, dict)
    outcomes = _list_or_empty(data.get("outcomes") if isinstance(data, dict) else [])
    normalized = [_normalize_outcome(outcome) for outcome in outcomes]
    total_required_gates = sum(outcome["gate_counts"]["required"] for outcome in normalized)
    ready_required_gates = sum(outcome["gate_counts"]["ready_required"] for outcome in normalized)
    blocked_required_gates = sum(outcome["gate_counts"]["blocked_required"] for outcome in normalized)
    ready_outcomes = [outcome for outcome in normalized if outcome["status"] == "ready"]
    blocked_outcomes = [outcome for outcome in normalized if outcome["status"] == "blocked"]
    next_actions = _next_actions(normalized, configured=configured)

    score = None
    if total_required_gates:
        score = round((ready_required_gates / total_required_gates) * 100)

    readiness = _readiness(
        configured=configured,
        outcomes=normalized,
        blocked_outcomes=blocked_outcomes,
        total_required_gates=total_required_gates,
        ready_required_gates=ready_required_gates,
    )
    return {
        "schema": OUTCOME_STATUS_SCHEMA,
        "path": "agent/outcomes.yml",
        "configured": configured,
        "readiness": readiness,
        "score": score,
        "summary": _summary(
            readiness=readiness,
            outcomes=normalized,
            ready_outcomes=ready_outcomes,
            blocked_outcomes=blocked_outcomes,
            total_required_gates=total_required_gates,
            ready_required_gates=ready_required_gates,
        ),
        "counts": {
            "outcomes": len(normalized),
            "ready_outcomes": len(ready_outcomes),
            "blocked_outcomes": len(blocked_outcomes),
            "required_gates": total_required_gates,
            "ready_required_gates": ready_required_gates,
            "blocked_required_gates": blocked_required_gates,
        },
        "outcomes": normalized,
        "blockers": _blockers(normalized),
        "next_actions": next_actions,
    }


def format_outcome_status(status: dict[str, Any]) -> str:
    lines = [
        "AgentSpec Product Outcomes",
        f"Path: {status.get('path', 'agent/outcomes.yml')}",
        f"Readiness: {status.get('readiness', 'unknown')}",
        f"Score: {_score_text(status.get('score'))}",
        f"Summary: {status.get('summary', '-')}",
    ]

    outcomes = status.get("outcomes") if isinstance(status.get("outcomes"), list) else []
    if outcomes:
        lines.extend(["", "Outcomes:"])
        for outcome in outcomes:
            counts = outcome.get("gate_counts", {}) if isinstance(outcome.get("gate_counts"), dict) else {}
            lines.append(
                "- "
                f"{outcome.get('id')} {outcome.get('title')} "
                f"[{outcome.get('status')}] "
                f"required gates {counts.get('ready_required', 0)}/{counts.get('required', 0)}"
            )
    else:
        lines.extend(["", "Outcomes:", "- none defined"])

    blockers = status.get("blockers") if isinstance(status.get("blockers"), list) else []
    if blockers:
        lines.extend(["", "Blockers:"])
        for blocker in blockers:
            location = "/".join(
                part
                for part in [str(blocker.get("outcome_id", "")), str(blocker.get("gate_id", ""))]
                if part
            )
            title = blocker.get("title") or blocker.get("message") or "Blocked outcome gate"
            lines.append(f"- {location}: {title}")

    next_actions = status.get("next_actions") if isinstance(status.get("next_actions"), list) else []
    if next_actions:
        lines.extend(["", "Next Actions:"])
        for action in next_actions:
            lines.append(f"- {action}")

    return "\n".join(lines)


def _normalize_outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    gates = [_normalize_gate(gate) for gate in _list_or_empty(outcome.get("gates"))]
    required = [gate for gate in gates if gate["required"]]
    ready_required = [gate for gate in required if gate["status"] in READY_GATE_STATUSES]
    blocked_required = [gate for gate in required if gate["status"] in BLOCKING_GATE_STATUSES]
    blockers = _string_list(outcome.get("blockers"))
    status = _outcome_status(
        explicit_status=str(outcome.get("status", "")).strip(),
        required_gates=required,
        ready_required_gates=ready_required,
        blocked_required_gates=blocked_required,
        blockers=blockers,
    )
    return {
        "id": str(outcome.get("id") or "OUTCOME"),
        "title": str(outcome.get("title") or outcome.get("name") or "Untitled outcome"),
        "description": outcome.get("description"),
        "priority": str(outcome.get("priority") or "P0"),
        "status": status,
        "gates": gates,
        "gate_counts": {
            "total": len(gates),
            "required": len(required),
            "ready_required": len(ready_required),
            "blocked_required": len(blocked_required),
        },
        "blockers": blockers,
        "next_actions": _string_list(outcome.get("next_actions")),
    }


def _normalize_gate(gate: dict[str, Any]) -> dict[str, Any]:
    status = str(gate.get("status") or "missing").strip().lower()
    evidence = _evidence(gate.get("evidence"))
    return {
        "id": str(gate.get("id") or "GATE"),
        "title": str(gate.get("title") or gate.get("name") or "Untitled gate"),
        "status": status,
        "required": bool(gate.get("required", True)),
        "evidence": evidence,
        "next_action": gate.get("next_action"),
    }


def _outcome_status(
    *,
    explicit_status: str,
    required_gates: list[dict[str, Any]],
    ready_required_gates: list[dict[str, Any]],
    blocked_required_gates: list[dict[str, Any]],
    blockers: list[str],
) -> str:
    explicit = explicit_status.lower()
    if explicit in {"blocked", "failed"} or blockers or blocked_required_gates:
        return "blocked"
    if required_gates and len(required_gates) == len(ready_required_gates):
        return "ready"
    if explicit in {"ready", "passed"} and not required_gates:
        return "ready"
    if explicit in {"in_progress", "running"}:
        return "in_progress"
    return "not_ready"


def _readiness(
    *,
    configured: bool,
    outcomes: list[dict[str, Any]],
    blocked_outcomes: list[dict[str, Any]],
    total_required_gates: int,
    ready_required_gates: int,
) -> str:
    if not configured:
        return "missing"
    if not outcomes:
        return "not_configured"
    if blocked_outcomes:
        return "blocked"
    if total_required_gates and total_required_gates == ready_required_gates:
        return "ready"
    return "not_ready"


def _summary(
    *,
    readiness: str,
    outcomes: list[dict[str, Any]],
    ready_outcomes: list[dict[str, Any]],
    blocked_outcomes: list[dict[str, Any]],
    total_required_gates: int,
    ready_required_gates: int,
) -> str:
    if readiness == "missing":
        return "agent/outcomes.yml is missing; product outcome readiness is not tracked."
    if not outcomes:
        return "No product outcomes are defined yet."
    return (
        f"{len(ready_outcomes)}/{len(outcomes)} outcome(s) ready; "
        f"{ready_required_gates}/{total_required_gates} required gate(s) ready; "
        f"{len(blocked_outcomes)} outcome(s) blocked."
    )


def _blockers(outcomes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for outcome in outcomes:
        for blocker in outcome.get("blockers", []):
            blockers.append(
                {
                    "outcome_id": outcome["id"],
                    "title": blocker,
                    "message": blocker,
                }
            )
        for gate in outcome.get("gates", []):
            if not gate.get("required") or gate.get("status") not in BLOCKING_GATE_STATUSES:
                continue
            blockers.append(
                {
                    "outcome_id": outcome["id"],
                    "gate_id": gate["id"],
                    "title": gate["title"],
                    "status": gate["status"],
                    "next_action": gate.get("next_action"),
                }
            )
    return blockers


def _next_actions(outcomes: list[dict[str, Any]], *, configured: bool) -> list[str]:
    if not configured:
        return ["Create agent/outcomes.yml with P0 product workflows and required proof gates."]
    if not outcomes:
        return ["Define at least one P0 product workflow in agent/outcomes.yml."]
    actions: list[str] = []
    for outcome in outcomes:
        actions.extend(outcome.get("next_actions", []))
        for gate in outcome.get("gates", []):
            action = gate.get("next_action")
            if gate.get("required") and gate.get("status") not in READY_GATE_STATUSES and action:
                actions.append(str(action))
    return _dedupe(actions)


def _evidence(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item.strip()]


def _list_or_empty(value: Any) -> list[dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _score_text(score: Any) -> str:
    if isinstance(score, int):
        return f"{score}/100"
    return "n/a"
