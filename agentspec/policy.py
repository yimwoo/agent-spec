"""Execution-scope, content-safety, and source-emission policy checks."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import load_data
from .paths import path_matches_pattern


@dataclass(frozen=True)
class PolicyVerdict:
    """Deterministic execution policy decision and supporting flags."""

    decision: str
    reason: str
    flags: list[str]


# ADR-0004 autonomous-mode hard-limit detectors. The patterns are
# deliberately conservative; in autonomous mode any match is a halt. In
# supervised mode a human is in the loop, so these gates do not fire.
_DESTRUCTIVE_GIT_RE = re.compile(
    r"\bgit\s+(?:"
    r"push\s+[^\n]*--force"
    r"|push\s+[^\n]*-f\b"
    r"|reset\s+--hard"
    r"|branch\s+-D"
    r"|clean\s+-f"
    r"|--no-verify"
    r"|--no-gpg-sign"
    r")",
    re.IGNORECASE,
)
_REMOTE_PUSH_RE = re.compile(r"\bgit\s+push\b", re.IGNORECASE)
# Detects API-key / token shapes. Conservative — false positives are
# preferred to leaking secrets into committed audit artifacts.
_CREDENTIAL_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),                # OpenAI-style
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                  # AWS access key id
    re.compile(r"ghp_[A-Za-z0-9]{30,}"),                  # GitHub PAT
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),          # Slack
    re.compile(r"-----BEGIN\s+(?:RSA|OPENSSH|PRIVATE)\s+KEY"),
    re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),  # JWT
)
_CREDENTIAL_REDACTION = "[REDACTED_CREDENTIAL]"
_AUTO_ACCEPTANCE_RE = re.compile(
    r"\baspec\s+(?:dcr\s+accept|requirement\s+accept)\b",
    re.IGNORECASE,
)

_BODY_EMIT_CLASSIFICATIONS = frozenset({"public", "internal"})
_BODY_EMIT_STORAGE_MODES = frozenset({"committed"})


def evaluate_policy(
    *,
    allowed_paths: list[str],
    touched_paths: list[str],
    iteration: int,
    max_iterations: int,
    executor_output: str = "",
    mode: str = "supervised",
) -> PolicyVerdict:
    """Evaluate path, iteration, and autonomous-content policy gates."""

    if iteration > max_iterations:
        return PolicyVerdict(
            decision="halt",
            reason=f"Iteration {iteration} exceeds max_iterations={max_iterations}.",
            flags=["max_iterations_exceeded"],
        )

    outside = [path for path in touched_paths if not _is_allowed(path, allowed_paths)]
    if outside:
        return PolicyVerdict(
            decision="halt",
            reason=f"Touched path(s) outside allowed scope: {', '.join(outside)}.",
            flags=["forbidden_path"],
        )

    # ADR-0004 hard limits + ADR-0005 research-mode safety: the content
    # gates fire on any non-supervised mode. Supervised mode keeps the
    # human in the loop, so the gates are noise there.
    if mode in {"autonomous", "research"} and executor_output:
        autonomous_verdict = _evaluate_autonomous_content(executor_output)
        if autonomous_verdict is not None:
            return autonomous_verdict

    return PolicyVerdict(
        decision="allow",
        reason="No policy gate blocked this iteration.",
        flags=[],
    )


def _evaluate_autonomous_content(executor_output: str) -> PolicyVerdict | None:
    """Per ADR-0004: hard limits that always halt in autonomous mode.

    Order matters — destructive git is checked before plain remote push so
    the more specific reason wins.
    """
    if _DESTRUCTIVE_GIT_RE.search(executor_output):
        return PolicyVerdict(
            decision="halt",
            reason="Destructive git command detected in executor output (autonomous mode).",
            flags=["destructive_git"],
        )
    if _REMOTE_PUSH_RE.search(executor_output):
        return PolicyVerdict(
            decision="halt",
            reason="Remote push detected in executor output (autonomous mode requires explicit opt-in).",
            flags=["remote_push"],
        )
    if has_credential_pattern(executor_output):
        return PolicyVerdict(
            decision="halt",
            reason="Credential-shaped string detected in executor output; autonomous mode refuses to persist run state that may exfiltrate secrets.",
            flags=["credential_pattern"],
        )
    if _AUTO_ACCEPTANCE_RE.search(executor_output):
        return PolicyVerdict(
            decision="halt",
            reason="Artifact auto-acceptance attempt (aspec dcr accept / requirement accept) is forbidden in autonomous mode.",
            flags=["auto_acceptance"],
        )
    return None


def has_credential_pattern(text: str) -> bool:
    """Return whether text contains a supported credential-shaped pattern."""

    return any(pattern.search(text) for pattern in _CREDENTIAL_PATTERNS)


def redact_sensitive_text(text: str) -> str:
    """Replace supported credential-shaped patterns with a stable marker."""

    redacted = text
    for pattern in _CREDENTIAL_PATTERNS:
        redacted = pattern.sub(_CREDENTIAL_REDACTION, redacted)
    return redacted


def _is_allowed(path: str, allowed_paths: list[str]) -> bool:
    for pattern in allowed_paths:
        if path_matches_pattern(path, pattern):
            return True
    return False


def can_emit_source_body(source: dict[str, Any]) -> bool:
    """Return whether source body text may be emitted into generated artifacts."""

    classification = str(source.get("classification", "internal"))
    storage_mode = str(source.get("storage_mode", "committed"))
    return (
        classification in _BODY_EMIT_CLASSIFICATIONS
        and storage_mode in _BODY_EMIT_STORAGE_MODES
    )


def source_body_redaction(
    source: dict[str, Any],
    section: dict[str, Any] | None = None,
) -> str:
    """Metadata-only placeholder for sources whose body must not be emitted."""

    source_id = str(source.get("id", "-"))
    section_id = str((section or {}).get("id", "-"))
    classification = str(source.get("classification", "internal"))
    storage_mode = str(source.get("storage_mode", "committed"))
    uri = str(source.get("uri") or source.get("remote_uri") or "-")
    content_hash = str(
        (section or {}).get("content_hash")
        or source.get("content_hash")
        or "-"
    )
    return (
        "[Source content withheld: "
        f"classification={classification}, "
        f"storage_mode={storage_mode}, "
        f"source_id={source_id}, "
        f"section_id={section_id}, "
        f"uri={uri}, "
        f"content_hash={content_hash}]"
    )


def evaluate_project_invariants(root: Path, files: list[str] | None = None) -> dict[str, Any]:
    """Evaluate optional repo-local invariants for doctor/reporting."""

    path = root / "agent" / "policies" / "invariants.yml"
    rel_path = "agent/policies/invariants.yml"
    if not path.exists():
        return {
            "status": "not_configured",
            "path": rel_path,
            "results": [],
        }

    try:
        invariants = load_data(path, [])
    except ValueError as exc:
        return _invalid_project_invariants_config(rel_path, f"Invalid JSON content: {exc}")
    if not isinstance(invariants, list):
        return _invalid_project_invariants_config(rel_path, "agent/policies/invariants.yml must contain a list of invariants.")
    repo_files = files if files is not None else _repo_file_list(root)
    results = []
    for index, invariant in enumerate(invariants, start=1):
        try:
            results.append(_evaluate_project_invariant(root, repo_files, invariant))
        except ValueError as exc:
            results.append(_invalid_project_invariant_result(invariant, index, str(exc)))
    if any(result["status"] == "invalid" for result in results):
        status = "invalid_config"
    elif any(result["status"] == "failed" for result in results):
        status = "failed"
    else:
        status = "passed"
    return {
        "status": status,
        "path": rel_path,
        "results": results,
    }


def _evaluate_project_invariant(root: Path, files: list[str], invariant: Any) -> dict[str, Any]:
    if not isinstance(invariant, dict):
        raise ValueError("Project invariant entries must be JSON objects.")
    invariant_id = _required_invariant_string(invariant, "id")
    kind = _required_invariant_string(invariant, "kind")
    severity = str(invariant.get("severity", "warning"))
    description = str(invariant.get("description", invariant_id))

    if kind == "required_path":
        rel_path = _required_invariant_path(invariant, "path")
        exists = (root / rel_path).exists()
        return _invariant_result(
            invariant_id,
            kind,
            severity,
            "passed" if exists else "failed",
            description,
            f"Required path exists: {rel_path}" if exists else f"Required path is missing: {rel_path}",
            path=rel_path,
        )

    if kind == "forbidden_path":
        pattern = _required_invariant_string(invariant, "pattern")
        matches = [path for path in files if path_matches_pattern(path, pattern)]
        return _invariant_result(
            invariant_id,
            kind,
            severity,
            "failed" if matches else "passed",
            description,
            f"Forbidden path pattern matched: {', '.join(matches)}" if matches else f"No files match forbidden pattern: {pattern}",
            pattern=pattern,
            matches=matches,
        )

    raise ValueError(f"Unknown project invariant kind {kind!r}.")


def _invalid_project_invariants_config(path: str, message: str) -> dict[str, Any]:
    return {
        "status": "invalid_config",
        "path": path,
        "results": [
            _invariant_result(
                "INVALID-CONFIG",
                "invalid_config",
                "error",
                "invalid",
                "Invalid project invariant configuration.",
                message,
            )
        ],
    }


def _invalid_project_invariant_result(invariant: Any, index: int, message: str) -> dict[str, Any]:
    if isinstance(invariant, dict):
        invariant_id = invariant.get("id")
        kind = invariant.get("kind")
        severity = invariant.get("severity")
        description = invariant.get("description")
    else:
        invariant_id = None
        kind = None
        severity = None
        description = None
    return _invariant_result(
        invariant_id if isinstance(invariant_id, str) and invariant_id.strip() else f"INVALID-{index:03d}",
        kind if isinstance(kind, str) and kind.strip() else "invalid_config",
        severity if isinstance(severity, str) and severity.strip() else "error",
        "invalid",
        description if isinstance(description, str) and description.strip() else "Invalid project invariant entry.",
        message,
    )


def _invariant_result(
    invariant_id: str,
    kind: str,
    severity: str,
    status: str,
    description: str,
    message: str,
    **extra: Any,
) -> dict[str, Any]:
    result = {
        "id": invariant_id,
        "kind": kind,
        "status": status,
        "severity": severity,
        "description": description,
        "message": message,
    }
    result.update(extra)
    return result


def _required_invariant_string(invariant: dict[str, Any], field: str) -> str:
    value = invariant.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Project invariant requires non-empty string field {field!r}.")
    return value.strip()


def _required_invariant_path(invariant: dict[str, Any], field: str) -> str:
    value = _required_invariant_string(invariant, field)
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"Project invariant field {field!r} must be repo-relative and must not contain '..'.")
    return value


def _repo_file_list(root: Path) -> list[str]:
    return sorted(str(path.relative_to(root)) for path in root.rglob("*") if path.is_file())
