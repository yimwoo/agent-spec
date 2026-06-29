"""Product-outcome readiness projections and human-readable formatting."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import load_data, utc_now_iso, write_data


OUTCOMES_SCHEMA = "agentspec.outcomes.v0"
OUTCOME_STATUS_SCHEMA = "agentspec.outcome_status.v0"
OUTCOME_OBSERVATION_SCHEMA = "agentspec.outcome_observation.v0"
OUTCOME_VERDICT_SCHEMA = "agentspec.outcome_verdict.v0"
OUTCOME_VERDICTS_SCHEMA = "agentspec.outcome_verdicts.v0"
OUTCOME_OBSERVATIONS_PATH = Path("agent/outcome-evidence/observations")
OUTCOME_VERDICTS_PATH = Path("agent/outcome-evidence/verdicts/latest.yml")
OUTCOME_CHECK_KINDS = frozenset(
    {"command", "browser_ui", "slo", "api_compatibility", "deployment", "release"}
)
READY_GATE_STATUSES = {"passed", "ready"}
BLOCKING_GATE_STATUSES = {"blocked", "failed", "malformed", "missing", "stale", "untrusted"}
DEFAULT_MAX_AGE_SECONDS = 86_400
UNTRUSTED_SOURCE_TYPES = frozenset({"model", "model_self_report", "self_report", "task_completion"})


def build_outcome_status(
    root: Path,
    *,
    evaluated_at: str | None = None,
) -> dict[str, Any]:
    """Build a read-only product outcome readiness summary.

    Task readiness answers whether AgentSpec has executable work. Outcome
    readiness answers whether critical product workflows have the proof needed
    to claim production-quality behavior.
    """

    root = root.resolve()
    evaluation_time = _parse_timestamp(evaluated_at or utc_now_iso())
    if evaluation_time is None:
        raise ValueError("evaluated_at must be an ISO 8601 timestamp with a timezone.")
    evaluation_iso = _timestamp_text(evaluation_time)
    path = root / "agent" / "outcomes.yml"
    data = load_data(path, None)
    configured = isinstance(data, dict)
    outcomes = _list_or_empty(data.get("outcomes") if isinstance(data, dict) else [])
    observations, observation_issues = _load_outcome_observations(root)
    normalized = [
        _normalize_outcome(
            outcome,
            observations=observations,
            evaluated_at=evaluation_time,
        )
        for outcome in outcomes
    ]
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
        "evaluated_at": evaluation_iso,
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
        "observation_issues": observation_issues,
        "evidence_contract": {
            "definitions": "agent/outcomes.yml",
            "observations": OUTCOME_OBSERVATIONS_PATH.as_posix(),
            "verdicts": OUTCOME_VERDICTS_PATH.as_posix(),
            "policy_authority": "agentspec.outcome",
            "adapter_role": "observation_only",
        },
        "blockers": _blockers(normalized),
        "next_actions": next_actions,
        "agent_next_actions": _agent_next_actions(next_actions),
    }


def record_outcome_observation(root: Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and record facts supplied by an external outcome adapter.

    Adapters can report observations, but cannot report a passing policy
    verdict. AgentSpec evaluates the standardized facts against the check
    definition when outcome status is built.

    Args:
        root: AgentSpec project root.
        payload: Observation fields including outcome, gate, check, kind,
            timestamp, source provenance, and facts.

    Returns:
        The stored observation record including its repository-relative path.

    Raises:
        ValueError: If the observation is malformed or attempts to set policy.
    """

    if not isinstance(payload, dict):
        raise ValueError("Outcome observation must be a JSON object.")
    forbidden = sorted({"status", "verdict", "passed"}.intersection(payload))
    if forbidden:
        raise ValueError(
            "Outcome adapters may submit facts only; policy fields are forbidden: "
            + ", ".join(forbidden)
        )
    record = _validated_observation(payload, path=None)
    if record.get("error"):
        raise ValueError(str(record["error"]))
    observation_id = str(payload.get("id") or f"OBS-{uuid.uuid4().hex[:12]}")
    if not _safe_identifier(observation_id):
        raise ValueError("Observation id must contain only letters, numbers, '.', '_', or '-'.")
    stored = {
        "schema": OUTCOME_OBSERVATION_SCHEMA,
        "id": observation_id,
        "outcome_id": record["outcome_id"],
        "gate_id": record["gate_id"],
        "check_id": record["check_id"],
        "kind": record["kind"],
        "observed_at": record["observed_at"],
        "recorded_at": utc_now_iso(),
        "expires_at": record.get("expires_at"),
        "source": record["source"],
        "facts": record["facts"],
    }
    if stored["expires_at"] is None:
        del stored["expires_at"]
    relative_path = OUTCOME_OBSERVATIONS_PATH / f"{observation_id}.yml"
    destination = root.resolve() / relative_path
    if destination.exists():
        raise ValueError(f"Outcome observation {observation_id} already exists; observations are immutable.")
    write_data(destination, stored)
    return {**stored, "path": relative_path.as_posix()}


def write_outcome_verdicts(root: Path) -> dict[str, Any]:
    """Evaluate outcome evidence and persist a separate policy-verdict artifact."""

    root = root.resolve()
    status = build_outcome_status(root)
    verdicts = [
        verdict
        for outcome in _list_or_empty(status.get("outcomes"))
        for gate in _list_or_empty(outcome.get("gates"))
        for verdict in _list_or_empty(gate.get("verdicts"))
    ]
    payload = {
        "schema": OUTCOME_VERDICTS_SCHEMA,
        "evaluated_at": status["evaluated_at"],
        "definitions_path": "agent/outcomes.yml",
        "observations_path": OUTCOME_OBSERVATIONS_PATH.as_posix(),
        "policy_authority": "agentspec.outcome",
        "readiness": status["readiness"],
        "verdicts": verdicts,
    }
    write_data(root / OUTCOME_VERDICTS_PATH, payload)
    return {**payload, "path": OUTCOME_VERDICTS_PATH.as_posix()}


def format_outcome_status(status: dict[str, Any]) -> str:
    """Format a product-outcome status payload for terminal output."""

    lines = [
        "AgentSpec Product Outcomes",
        f"Path: {status.get('path', 'agent/outcomes.yml')}",
        f"Evaluated: {status.get('evaluated_at', '-')}",
        f"Readiness: {status.get('readiness', 'unknown')}",
        f"Score: {_score_text(status.get('score'))}",
        f"Summary: {status.get('summary', '-')}",
        "Interpretation: Product outcomes track proof for critical user-visible workflows. "
        "Required gates are evidence checks that must be ready before claiming outcome readiness.",
    ]

    outcomes = _list_or_empty(status.get("outcomes"))
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

    ready_gates = _required_gates(outcomes, ready=True)
    not_ready_gates = _required_gates(outcomes, ready=False)
    if ready_gates:
        lines.extend(["", "Ready Required Gates:"])
        lines.extend(f"- {_gate_line(gate)}" for gate in ready_gates)
    if not_ready_gates:
        lines.extend(["", "Not Ready Required Gates:"])
        lines.extend(f"- {_gate_line(gate, include_status=True)}" for gate in not_ready_gates[:5])

    typed_verdicts = [
        verdict
        for outcome in outcomes
        for gate in _list_or_empty(outcome.get("gates"))
        for verdict in _list_or_empty(gate.get("verdicts"))
    ]
    if typed_verdicts:
        lines.extend(["", "Typed Evidence Verdicts:"])
        for verdict in typed_verdicts:
            location = "/".join(
                str(verdict.get(key) or "") for key in ("outcome_id", "gate_id", "check_id")
            )
            lines.append(
                f"- {location}: {verdict.get('kind')} [{verdict.get('status')}] "
                f"{verdict.get('reason')}"
            )

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


def _required_gates(outcomes: list[dict[str, Any]], *, ready: bool) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []
    for outcome in outcomes:
        for gate in outcome.get("gates", []):
            if not isinstance(gate, dict) or not gate.get("required"):
                continue
            is_ready = gate.get("status") in READY_GATE_STATUSES
            if is_ready != ready:
                continue
            gates.append(
                {
                    "outcome_id": outcome.get("id"),
                    "gate_id": gate.get("id"),
                    "title": gate.get("title"),
                    "status": gate.get("status"),
                    "next_action": gate.get("next_action"),
                }
            )
    return gates


def _gate_line(gate: dict[str, Any], *, include_status: bool = False) -> str:
    location = "/".join(
        part
        for part in [str(gate.get("outcome_id", "")), str(gate.get("gate_id", ""))]
        if part
    )
    title = gate.get("title") or "Untitled gate"
    status = f" [{gate.get('status')}]" if include_status else ""
    next_action = gate.get("next_action")
    suffix = f" -> {next_action}" if next_action else ""
    return f"{location}: {title}{status}{suffix}"


def _normalize_outcome(
    outcome: dict[str, Any],
    *,
    observations: list[dict[str, Any]],
    evaluated_at: datetime,
) -> dict[str, Any]:
    outcome_id = str(outcome.get("id") or "OUTCOME")
    gates = [
        _normalize_gate(
            gate,
            outcome_id=outcome_id,
            observations=observations,
            evaluated_at=evaluated_at,
        )
        for gate in _list_or_empty(outcome.get("gates"))
    ]
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
        "id": outcome_id,
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


def _normalize_gate(
    gate: dict[str, Any],
    *,
    outcome_id: str,
    observations: list[dict[str, Any]],
    evaluated_at: datetime,
) -> dict[str, Any]:
    gate_id = str(gate.get("id") or "GATE")
    definitions = _check_definitions(gate)
    verdicts = [
        _evaluate_check(
            outcome_id=outcome_id,
            gate_id=gate_id,
            definition=definition,
            observations=observations,
            evaluated_at=evaluated_at,
        )
        for definition in definitions
    ]
    status = _typed_gate_status(verdicts) if definitions else str(gate.get("status") or "missing").strip().lower()
    evidence = _evidence(gate.get("evidence"))
    repair = gate.get("repair") or gate.get("next_action")
    next_action = gate.get("next_action")
    if definitions and status not in READY_GATE_STATUSES:
        next_action = next(
            (
                str(verdict.get("repair"))
                for verdict in verdicts
                if verdict.get("status") not in READY_GATE_STATUSES and verdict.get("repair")
            ),
            next_action,
        )
    return {
        "id": gate_id,
        "title": str(gate.get("title") or gate.get("name") or "Untitled gate"),
        "status": status,
        "required": bool(gate.get("required", True)),
        "evidence": evidence,
        "checks": definitions,
        "verdicts": verdicts,
        "repair": repair,
        "next_action": next_action,
    }


def _check_definitions(gate: dict[str, Any]) -> list[dict[str, Any]]:
    raw_checks = gate.get("checks")
    if isinstance(raw_checks, dict):
        raw_checks = [raw_checks]
    if not isinstance(raw_checks, list):
        return []
    checks: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_checks, start=1):
        if not isinstance(raw, dict):
            checks.append(
                {
                    "id": f"CHECK-{index:03d}",
                    "kind": "invalid",
                    "required": True,
                    "max_age_seconds": DEFAULT_MAX_AGE_SECONDS,
                    "repair": "Replace the malformed check definition with an object.",
                    "definition_error": "Check definition must be an object.",
                }
            )
            continue
        kind = str(raw.get("kind") or "").strip().lower().replace("/", "_").replace("-", "_")
        check_id = str(raw.get("id") or f"CHECK-{index:03d}")
        max_age = raw.get("max_age_seconds", DEFAULT_MAX_AGE_SECONDS)
        definition_error = None
        if kind not in OUTCOME_CHECK_KINDS:
            definition_error = f"Unsupported outcome check kind: {kind or '<missing>'}."
        elif not isinstance(max_age, int) or isinstance(max_age, bool) or max_age <= 0:
            definition_error = "max_age_seconds must be a positive integer."
        elif not _safe_identifier(check_id):
            definition_error = "Check id contains unsupported characters."
        checks.append(
            {
                "id": check_id,
                "kind": kind,
                "required": bool(raw.get("required", True)),
                "max_age_seconds": max_age,
                "repair": str(
                    raw.get("repair")
                    or gate.get("repair")
                    or gate.get("next_action")
                    or _default_repair(kind, check_id)
                ),
                "definition_error": definition_error,
            }
        )
    return checks


def _evaluate_check(
    *,
    outcome_id: str,
    gate_id: str,
    definition: dict[str, Any],
    observations: list[dict[str, Any]],
    evaluated_at: datetime,
) -> dict[str, Any]:
    check_id = str(definition["id"])
    kind = str(definition["kind"])
    base = {
        "schema": OUTCOME_VERDICT_SCHEMA,
        "outcome_id": outcome_id,
        "gate_id": gate_id,
        "check_id": check_id,
        "kind": kind,
        "required": bool(definition.get("required", True)),
        "evaluated_at": _timestamp_text(evaluated_at),
        "policy_authority": "agentspec.outcome",
        "repair": definition.get("repair"),
    }
    definition_error = definition.get("definition_error")
    if definition_error:
        return {**base, "status": "malformed", "reason": str(definition_error), "observation": None}

    candidates = [
        observation
        for observation in observations
        if observation.get("outcome_id") == outcome_id
        and observation.get("gate_id") == gate_id
        and observation.get("check_id") == check_id
    ]
    if not candidates:
        return {
            **base,
            "status": "missing",
            "reason": f"No {kind} observation is recorded for {outcome_id}/{gate_id}/{check_id}.",
            "observation": None,
        }
    candidates.sort(key=lambda item: str(item.get("observed_at") or ""), reverse=True)
    observation = candidates[0]
    observation_ref = _observation_reference(observation)
    error = observation.get("error")
    if error:
        return {**base, "status": "malformed", "reason": str(error), "observation": observation_ref}
    if observation.get("kind") != kind:
        return {
            **base,
            "status": "malformed",
            "reason": f"Observation kind {observation.get('kind')} does not match definition kind {kind}.",
            "observation": observation_ref,
        }
    source = observation.get("source")
    source_type = str(source.get("type") or "") if isinstance(source, dict) else ""
    if source_type in UNTRUSTED_SOURCE_TYPES:
        return {
            **base,
            "status": "untrusted",
            "reason": "Task completion and model self-report are not production outcome evidence.",
            "observation": observation_ref,
        }
    observed_at = _parse_timestamp(str(observation.get("observed_at") or ""))
    expires_at = _parse_timestamp(str(observation.get("expires_at") or "")) if observation.get("expires_at") else None
    if observed_at is None:
        return {**base, "status": "malformed", "reason": "observed_at is invalid.", "observation": observation_ref}
    age_seconds = (evaluated_at - observed_at).total_seconds()
    max_age = int(definition["max_age_seconds"])
    if age_seconds < -300:
        return {
            **base,
            "status": "malformed",
            "reason": "Observation timestamp is more than five minutes in the future.",
            "observation": observation_ref,
        }
    if age_seconds > max_age or (expires_at is not None and evaluated_at > expires_at):
        return {
            **base,
            "status": "stale",
            "reason": f"Latest observation is stale ({round(max(age_seconds, 0))}s old; maximum {max_age}s).",
            "observation": observation_ref,
        }
    fact_status, reason = _evaluate_facts(kind, observation.get("facts"))
    return {
        **base,
        "status": fact_status,
        "reason": reason,
        "observation": observation_ref,
    }


def _evaluate_facts(kind: str, facts: Any) -> tuple[str, str]:
    if not isinstance(facts, dict):
        return "malformed", "Observation facts must be an object."
    if kind == "command":
        exit_code = facts.get("exit_code")
        if not isinstance(exit_code, int) or isinstance(exit_code, bool):
            return "malformed", "Command facts require an integer exit_code."
        return ("passed" if exit_code == 0 else "failed"), f"Command exited with code {exit_code}."
    if kind == "browser_ui":
        total = facts.get("journeys_total")
        passed = facts.get("journeys_passed")
        if not _non_negative_int(total) or not _non_negative_int(passed):
            return "malformed", "Browser/UI facts require valid positive journeys_total and journeys_passed counts."
        if not isinstance(total, int) or not isinstance(passed, int) or total <= 0 or passed > total:
            return "malformed", "Browser/UI facts require valid positive journeys_total and journeys_passed counts."
        return ("passed" if passed == total else "failed"), f"Browser/UI journeys passed {passed}/{total}."
    if kind == "slo":
        compliant = facts.get("compliant")
        if not isinstance(compliant, bool):
            return "malformed", "SLO facts require a boolean compliant field."
        return ("passed" if compliant else "failed"), "SLO is compliant." if compliant else "SLO is not compliant."
    if kind == "api_compatibility":
        breaking = facts.get("breaking_changes")
        if not _non_negative_int(breaking):
            return "malformed", "API compatibility facts require a non-negative breaking_changes count."
        return ("passed" if breaking == 0 else "failed"), f"API compatibility found {breaking} breaking change(s)."
    if kind == "deployment":
        healthy = facts.get("healthy")
        if not isinstance(healthy, bool):
            return "malformed", "Deployment facts require a boolean healthy field."
        return ("passed" if healthy else "failed"), "Deployment is healthy." if healthy else "Deployment is unhealthy."
    if kind == "release":
        ready = facts.get("ready")
        if not isinstance(ready, bool):
            return "malformed", "Release facts require a boolean ready field."
        return ("passed" if ready else "failed"), "Release evidence is ready." if ready else "Release evidence is not ready."
    return "malformed", f"Unsupported outcome check kind: {kind}."


def _typed_gate_status(verdicts: list[dict[str, Any]]) -> str:
    required = [verdict for verdict in verdicts if verdict.get("required", True)]
    if verdicts and not required:
        return "passed"
    selected = required
    if selected and all(verdict.get("status") == "passed" for verdict in selected):
        return "passed"
    priority = ("malformed", "untrusted", "failed", "stale", "missing")
    for status in priority:
        if any(verdict.get("status") == status for verdict in selected):
            return status
    return "missing"


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
    if not actions:
        return ["No outcome gate action is required; run `aspec status` to choose the next lifecycle action."]
    return _dedupe(actions)


def _agent_next_actions(actions: list[str]) -> list[str]:
    agent_actions: list[str] = []
    for action in actions:
        if "aspec " in action:
            agent_actions.append(
                "No outcome gate action is required; choose the next lifecycle action from project status."
            )
        else:
            agent_actions.append(action)
    return _dedupe(agent_actions)


def _load_outcome_observations(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    directory = root / OUTCOME_OBSERVATIONS_PATH
    if not directory.exists():
        return [], []
    observations: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.yml")):
        relative = path.relative_to(root).as_posix()
        try:
            payload = load_data(path, None)
        except (json.JSONDecodeError, OSError) as exc:
            observations.append({"path": relative, "error": f"Malformed observation file: {exc}"})
            issues.append({"path": relative, "message": f"Malformed observation file: {exc}"})
            continue
        observation = _validated_observation(payload, path=relative)
        observations.append(observation)
        if observation.get("error"):
            issues.append({"path": relative, "message": str(observation["error"])})
    return observations, issues


def _validated_observation(payload: Any, *, path: str | None) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"path": path, "error": "Observation must be an object."}
    record = dict(payload)
    record["path"] = path
    if payload.get("schema") not in {None, OUTCOME_OBSERVATION_SCHEMA}:
        record["error"] = f"Unsupported observation schema: {payload.get('schema')}."
        return record
    for key in ("outcome_id", "gate_id", "check_id", "kind", "observed_at"):
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            record["error"] = f"Observation requires a non-empty {key}."
            return record
    kind = str(payload["kind"]).strip().lower().replace("/", "_").replace("-", "_")
    if kind not in OUTCOME_CHECK_KINDS:
        record["error"] = f"Unsupported outcome observation kind: {kind}."
        return record
    observed_at = _parse_timestamp(str(payload["observed_at"]))
    if observed_at is None:
        record["error"] = "Observation observed_at must be an ISO 8601 timestamp with a timezone."
        return record
    expires_at_value = payload.get("expires_at")
    expires_at = _parse_timestamp(str(expires_at_value)) if expires_at_value else None
    if expires_at_value and expires_at is None:
        record["error"] = "Observation expires_at must be an ISO 8601 timestamp with a timezone."
        return record
    source = payload.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("adapter"), str) or not source["adapter"].strip():
        record["error"] = "Observation source requires a non-empty adapter provenance field."
        return record
    if not isinstance(payload.get("facts"), dict):
        record["error"] = "Observation facts must be an object."
        return record
    record.update(
        {
            "schema": OUTCOME_OBSERVATION_SCHEMA,
            "kind": kind,
            "observed_at": _timestamp_text(observed_at),
            "expires_at": _timestamp_text(expires_at) if expires_at is not None else None,
            "source": dict(source),
            "facts": dict(payload["facts"]),
        }
    )
    return record


def _observation_reference(observation: dict[str, Any]) -> dict[str, Any]:
    source = observation.get("source")
    return {
        "id": observation.get("id"),
        "path": observation.get("path"),
        "observed_at": observation.get("observed_at"),
        "source": source if isinstance(source, dict) else None,
    }


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def _timestamp_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_identifier(value: str) -> bool:
    return bool(value) and all(character.isalnum() or character in "._-" for character in value)


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _default_repair(kind: str, check_id: str) -> str:
    label = kind.replace("_", " ") if kind else "outcome"
    return f"Run the {label} adapter and record fresh facts for check {check_id}."


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
