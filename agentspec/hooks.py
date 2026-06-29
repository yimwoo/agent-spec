"""Provider-neutral lifecycle hook policy and native host translations."""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from .evidence import PASSING_PUBLIC_REVIEW_VERDICTS, load_task_evidence
from .io import utc_now_iso
from .paths import path_matches_pattern
from .policy import evaluate_policy, redact_sensitive_text
from .session import build_session_status, inspect_session


HOOK_REQUEST_SCHEMA = "agentspec.hook_request.v0"
HOOK_DECISION_SCHEMA = "agentspec.hook_decision.v0"
HOOK_EVIDENCE_SCHEMA = "agentspec.hook_evidence.v0"
HOOK_EVALUATION_SCHEMA = "agentspec.hook_evaluation.v0"
HOOK_ERROR_SCHEMA = "agentspec.hook_error.v0"
ALLOWED_HOOK_PROVIDERS = frozenset({"claude", "codex"})
ALLOWED_HOOK_EVENTS = frozenset(
    {"pre-execution", "scope-expansion", "stop-verification", "finish-evidence"}
)
BLOCKING_HOOK_EVENTS = frozenset({"pre-execution", "scope-expansion", "stop-verification"})
HOOK_EVIDENCE_PATH = Path("agent/hook-evidence/events.jsonl")
_PATCH_PATH_RE = re.compile(r"^\*\*\* (?:Add|Delete|Update) File:\s*(.+?)\s*$", re.MULTILINE)
_FINISH_COMMAND_RE = re.compile(r"\baspec\s+(?:finish\b|task\s+complete\b)", re.IGNORECASE)


def evaluate_native_hook(
    root: Path,
    *,
    provider: str,
    event: str,
    native_input: Any,
) -> dict[str, Any]:
    """Evaluate one Codex or Claude lifecycle hook through AgentSpec policy.

    Args:
        root: AgentSpec project root.
        provider: Native host provider, ``codex`` or ``claude``.
        event: Provider-neutral AgentSpec hook event.
        native_input: Native hook JSON payload.

    Returns:
        Provider-neutral request, decision, evidence, and translated native
        output. Blocking events fail closed when input is malformed.
    """

    root = root.resolve()
    normalized_provider = provider.strip().lower()
    normalized_event = event.strip().lower()
    error = _input_error(normalized_provider, normalized_event, native_input)
    if error is not None:
        request = _minimal_request(normalized_provider, normalized_event, native_input)
        decision = _error_decision(normalized_event, error)
    else:
        request = _normalize_request(
            root,
            provider=normalized_provider,
            event=normalized_event,
            native_input=native_input,
        )
        decision = _evaluate_request(root, request, native_input)

    evidence = _hook_evidence(request, decision, error=error)
    evidence, write_error = _record_evidence(root, evidence)
    if write_error is not None and normalized_event in BLOCKING_HOOK_EVENTS:
        error = write_error
        decision = _error_decision(normalized_event, error)
        evidence["decision"] = decision

    return {
        "schema": HOOK_EVALUATION_SCHEMA,
        "request": request,
        "decision": decision,
        "evidence": evidence,
        "native_output": _native_output(normalized_provider, normalized_event, decision),
        "error": error,
    }


def _input_error(provider: str, event: str, native_input: Any) -> dict[str, Any] | None:
    if provider not in ALLOWED_HOOK_PROVIDERS:
        return _hook_error(
            "ASPEC_HOOK_PROVIDER_INVALID",
            f"Hook provider must be one of {sorted(ALLOWED_HOOK_PROVIDERS)}.",
        )
    if event not in ALLOWED_HOOK_EVENTS:
        return _hook_error(
            "ASPEC_HOOK_EVENT_INVALID",
            f"Hook event must be one of {sorted(ALLOWED_HOOK_EVENTS)}.",
        )
    if not isinstance(native_input, dict):
        return _hook_error("ASPEC_HOOK_INPUT_INVALID", "Native hook input must be a JSON object.")
    if event in {"pre-execution", "scope-expansion", "finish-evidence"}:
        tool_name = native_input.get("tool_name")
        tool_input = native_input.get("tool_input")
        if not isinstance(tool_name, str) or not tool_name.strip() or not isinstance(tool_input, dict):
            return _hook_error(
                "ASPEC_HOOK_INPUT_INVALID",
                "Tool hook input requires non-empty tool_name and object tool_input fields.",
            )
    return None


def _normalize_request(
    root: Path,
    *,
    provider: str,
    event: str,
    native_input: dict[str, Any],
) -> dict[str, Any]:
    session = _active_write_session(root, native_input)
    tool_input = native_input.get("tool_input")
    normalized_tool_input: dict[str, Any] = tool_input if isinstance(tool_input, dict) else {}
    requested_paths = _requested_paths(root, event, normalized_tool_input, native_input)
    command = normalized_tool_input.get("command")
    return {
        "schema": HOOK_REQUEST_SCHEMA,
        "id": f"HOOKREQ-{uuid.uuid4().hex[:12]}",
        "provider": provider,
        "event": event,
        "native_event": str(native_input.get("hook_event_name") or ""),
        "native_session_id": str(native_input.get("session_id") or ""),
        "cwd": str(native_input.get("cwd") or root),
        "tool_name": str(native_input.get("tool_name") or ""),
        "requested_paths": requested_paths,
        "command": redact_sensitive_text(command) if isinstance(command, str) else None,
        "completion_requested": _completion_requested(native_input),
        "stop_hook_active": bool(native_input.get("stop_hook_active")),
        "task": _session_task(session),
        "provenance": {
            "adapter": f"agentspec-{provider}-hook",
            "policy": "agentspec.core",
            "native_permissions_authoritative": True,
        },
    }


def _minimal_request(provider: str, event: str, native_input: Any) -> dict[str, Any]:
    native_type = type(native_input).__name__
    return {
        "schema": HOOK_REQUEST_SCHEMA,
        "id": f"HOOKREQ-{uuid.uuid4().hex[:12]}",
        "provider": provider,
        "event": event,
        "native_event": "",
        "native_session_id": "",
        "cwd": "",
        "tool_name": "",
        "requested_paths": [],
        "command": None,
        "completion_requested": False,
        "stop_hook_active": False,
        "task": None,
        "provenance": {
            "adapter": f"agentspec-{provider or 'unknown'}-hook",
            "policy": "agentspec.core",
            "native_input_type": native_type,
            "native_permissions_authoritative": True,
        },
    }


def _evaluate_request(
    root: Path,
    request: dict[str, Any],
    native_input: dict[str, Any],
) -> dict[str, Any]:
    event = str(request["event"])
    if event in {"pre-execution", "scope-expansion"}:
        return _evaluate_pre_execution(request)
    if event == "stop-verification":
        return _evaluate_stop_verification(root, request)
    return _evaluate_finish_evidence(request, native_input)


def _evaluate_pre_execution(request: dict[str, Any]) -> dict[str, Any]:
    task = request.get("task")
    if not isinstance(task, dict):
        return _decision(
            request,
            outcome="deny",
            reason="Implementation tool use requires an active AgentSpec owner/patcher session lease.",
            flags=["missing_session_lease"],
        )

    allowed_paths = task.get("allowed_paths")
    allowed = [path for path in allowed_paths if isinstance(path, str)] if isinstance(allowed_paths, list) else []
    command = request.get("command")
    if isinstance(command, str) and command:
        verdict = evaluate_policy(
            allowed_paths=allowed,
            touched_paths=[],
            iteration=1,
            max_iterations=1,
            executor_output=command,
            mode="autonomous",
        )
        if verdict.decision != "allow":
            return _decision(
                request,
                outcome="deny",
                reason=verdict.reason,
                flags=verdict.flags,
            )

    requested_paths = request.get("requested_paths")
    requested = [path for path in requested_paths if isinstance(path, str)] if isinstance(requested_paths, list) else []
    outside = [path for path in requested if not any(path_matches_pattern(path, pattern) for pattern in allowed)]
    if outside:
        return _decision(
            request,
            outcome="scope_expansion_required",
            reason=(
                "Requested path(s) are outside the active task scope: "
                f"{', '.join(outside)}. Revise the task before retrying."
            ),
            flags=["scope_expansion_required"],
            requested_paths=outside,
        )

    return _decision(
        request,
        outcome="allow",
        reason="AgentSpec scope check passed; host sandbox and permission rules still apply.",
        flags=[],
    )


def _evaluate_stop_verification(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    if request.get("stop_hook_active"):
        return _decision(
            request,
            outcome="allow",
            reason="Stop hook recursion guard is active; do not start another verification loop.",
            flags=["stop_hook_recursion_guard"],
        )
    if not request.get("completion_requested"):
        return _decision(
            request,
            outcome="allow",
            reason="Stop observed without an AgentSpec completion request; verification remains advisory.",
            flags=[],
        )
    task = request.get("task")
    if not isinstance(task, dict):
        return _decision(
            request,
            outcome="deny",
            reason="Cannot verify completion without an active AgentSpec task session.",
            flags=["missing_session_lease"],
        )
    context_pack = task.get("context_pack")
    evidence = load_task_evidence(root, include_untracked_gitignored=True)
    entry = evidence.get(context_pack) if isinstance(context_pack, str) else None
    flags: list[str] = []
    if not isinstance(entry, dict) or entry.get("status") != "complete":
        flags.append("finish_evidence_missing")
    verification = entry.get("verification") if isinstance(entry, dict) else None
    if not isinstance(verification, dict) or verification.get("status") != "passed":
        flags.append("verification_evidence_missing")
    review = entry.get("code_review") if isinstance(entry, dict) else None
    if not isinstance(review, dict) or review.get("verdict") not in PASSING_PUBLIC_REVIEW_VERDICTS:
        flags.append("review_evidence_missing")
    if flags:
        return _decision(
            request,
            outcome="deny",
            reason=(
                "AgentSpec completion evidence is incomplete: "
                f"{', '.join(flags)}. Run verification, record review, and finish the task."
            ),
            flags=flags,
        )
    return _decision(
        request,
        outcome="allow",
        reason="AgentSpec verification, review, and finish evidence are complete.",
        flags=[],
    )


def _evaluate_finish_evidence(
    request: dict[str, Any],
    native_input: dict[str, Any],
) -> dict[str, Any]:
    command = request.get("command")
    finish_detected = isinstance(command, str) and bool(_FINISH_COMMAND_RE.search(command))
    response = native_input.get("tool_response")
    response_summary = _safe_response_summary(response)
    return _decision(
        request,
        outcome="record" if finish_detected else "allow",
        reason=(
            "Recorded native finish command evidence and provenance."
            if finish_detected
            else "No AgentSpec finish command was present; recorded hook provenance only."
        ),
        flags=["finish_evidence_recorded"] if finish_detected else [],
        details={"finish_detected": finish_detected, "tool_response": response_summary},
    )


def _decision(
    request: dict[str, Any],
    *,
    outcome: str,
    reason: str,
    flags: list[str],
    requested_paths: list[str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    task = request.get("task")
    task_record: dict[str, Any] = task if isinstance(task, dict) else {}
    return {
        "schema": HOOK_DECISION_SCHEMA,
        "event": request.get("event"),
        "outcome": outcome,
        "reason": reason,
        "flags": flags,
        "requested_paths": requested_paths or list(request.get("requested_paths") or []),
        "task_id": task_record.get("task_id"),
        "context_pack": task_record.get("context_pack"),
        "policy_source": "agentspec.policy.evaluate_policy",
        "preserves_host_permissions": True,
        "details": details or {},
    }


def _error_decision(event: str, error: dict[str, Any]) -> dict[str, Any]:
    blocking = event in BLOCKING_HOOK_EVENTS
    return {
        "schema": HOOK_DECISION_SCHEMA,
        "event": event,
        "outcome": "deny" if blocking else "record",
        "reason": str(error["message"]),
        "flags": ["malformed_hook_input" if error["code"] == "ASPEC_HOOK_INPUT_INVALID" else "hook_error"],
        "requested_paths": [],
        "task_id": None,
        "context_pack": None,
        "policy_source": "agentspec.hooks.fail_closed",
        "preserves_host_permissions": True,
        "details": {"error": error},
    }


def _hook_evidence(
    request: dict[str, Any],
    decision: dict[str, Any],
    *,
    error: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "schema": HOOK_EVIDENCE_SCHEMA,
        "id": f"HOOKEV-{uuid.uuid4().hex[:12]}",
        "recorded_at": utc_now_iso(),
        "provider": request.get("provider"),
        "event": request.get("event"),
        "native_event": request.get("native_event"),
        "native_session_id": request.get("native_session_id"),
        "request_id": request.get("id"),
        "task": request.get("task"),
        "request": {
            "tool_name": request.get("tool_name"),
            "requested_paths": request.get("requested_paths"),
            "command": request.get("command"),
            "completion_requested": request.get("completion_requested"),
        },
        "decision": decision,
        "error": error,
        "provenance": request.get("provenance"),
    }


def _record_evidence(
    root: Path,
    evidence: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    path = root / HOOK_EVIDENCE_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(evidence, sort_keys=True) + "\n")
    except OSError as exc:
        result = dict(evidence)
        result.update({"recorded": False, "path": HOOK_EVIDENCE_PATH.as_posix()})
        return result, _hook_error(
            "ASPEC_HOOK_EVIDENCE_WRITE_FAILED",
            f"Could not record hook evidence at {HOOK_EVIDENCE_PATH.as_posix()}: {exc}",
        )
    result = dict(evidence)
    result.update({"recorded": True, "path": HOOK_EVIDENCE_PATH.as_posix()})
    return result, None


def _active_write_session(root: Path, native_input: dict[str, Any]) -> dict[str, Any] | None:
    status = build_session_status(root)
    raw_active = status.get("active")
    active = [
        record
        for record in raw_active
        if isinstance(record, dict)
        and record.get("status") == "active"
        and record.get("mode") in {"owner", "patcher"}
    ] if isinstance(raw_active, list) else []
    if not active:
        return None
    cwd = _resolved_path(str(native_input.get("cwd") or root))
    matching = [
        record
        for record in active
        if _resolved_path(str(record.get("worktree") or root)) == cwd
    ]
    candidates = matching or active
    if len(candidates) != 1:
        return None
    session_id = candidates[0].get("session_id")
    return inspect_session(root, session_id) if isinstance(session_id, str) else None


def _session_task(session: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(session, dict):
        return None
    allowed_paths = session.get("allowed_paths")
    return {
        "session_id": session.get("session_id"),
        "task_id": session.get("task_id"),
        "context_pack": session.get("context_pack"),
        "branch": session.get("branch"),
        "worktree": session.get("worktree"),
        "allowed_paths": [
            path for path in allowed_paths if isinstance(path, str)
        ] if isinstance(allowed_paths, list) else [],
    }


def _requested_paths(
    root: Path,
    event: str,
    tool_input: dict[str, Any],
    native_input: dict[str, Any],
) -> list[str]:
    raw_paths: list[str] = []
    for key in ("file_path", "path", "notebook_path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            raw_paths.append(value)
    patch = tool_input.get("patch") or tool_input.get("input")
    if isinstance(patch, str):
        raw_paths.extend(match.strip() for match in _PATCH_PATH_RE.findall(patch))
    if event == "scope-expansion":
        requested = native_input.get("requested_paths")
        if isinstance(requested, list):
            raw_paths.extend(path for path in requested if isinstance(path, str))
    return sorted({_repo_relative_path(root, path) for path in raw_paths if path.strip()})


def _repo_relative_path(root: Path, path: str) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix().lstrip("./")
    try:
        return candidate.resolve().relative_to(root).as_posix()
    except ValueError:
        return candidate.resolve().as_posix()


def _completion_requested(native_input: dict[str, Any]) -> bool:
    explicit = native_input.get("completion_requested")
    if isinstance(explicit, bool):
        return explicit
    value = os.environ.get("AGENTSPEC_HOOK_ENFORCE_STOP", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _native_output(provider: str, event: str, decision: dict[str, Any]) -> dict[str, Any]:
    if provider == "claude":
        return _claude_native_output(event, decision)
    return _codex_native_output(event, decision)


def _codex_native_output(event: str, decision: dict[str, Any]) -> dict[str, Any]:
    return _shared_native_output(event, decision)


def _claude_native_output(event: str, decision: dict[str, Any]) -> dict[str, Any]:
    return _shared_native_output(event, decision)


def _shared_native_output(event: str, decision: dict[str, Any]) -> dict[str, Any]:
    outcome = decision.get("outcome")
    reason = str(decision.get("reason") or "AgentSpec hook decision.")
    if event in {"pre-execution", "scope-expansion"}:
        output: dict[str, Any] = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
            }
        }
        hook_output = output["hookSpecificOutput"]
        if outcome in {"deny", "scope_expansion_required"}:
            hook_output["permissionDecision"] = "deny"
            hook_output["permissionDecisionReason"] = reason
        else:
            hook_output["additionalContext"] = (
                "AgentSpec scope check passed. Host sandbox, permission, and managed policy rules still apply."
            )
        return output
    if event == "stop-verification" and outcome == "deny":
        return {"decision": "block", "reason": reason}
    return {}


def _safe_response_summary(response: Any) -> Any:
    if isinstance(response, dict):
        return {
            key: value
            for key, value in response.items()
            if key in {"exit_code", "returncode", "status", "success"}
            and isinstance(value, (bool, int, str, type(None)))
        }
    return None


def _hook_error(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": HOOK_ERROR_SCHEMA,
        "code": code,
        "message": message,
        "action": "Inspect the hook payload, active AgentSpec session, and evidence path before retrying.",
    }


def _resolved_path(path: str) -> Path:
    try:
        return Path(path).resolve()
    except OSError:
        return Path(path)
