from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .paths import path_matches_pattern


@dataclass(frozen=True)
class PolicyVerdict:
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
    if any(pattern.search(executor_output) for pattern in _CREDENTIAL_PATTERNS):
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
