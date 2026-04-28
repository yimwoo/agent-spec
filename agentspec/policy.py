from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass(frozen=True)
class PolicyVerdict:
    decision: str
    reason: str
    flags: list[str]


def evaluate_policy(
    *,
    allowed_paths: list[str],
    touched_paths: list[str],
    iteration: int,
    max_iterations: int,
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

    return PolicyVerdict(
        decision="allow",
        reason="No policy gate blocked this iteration.",
        flags=[],
    )


def _is_allowed(path: str, allowed_paths: list[str]) -> bool:
    normalized = path.strip().lstrip("./")
    for pattern in allowed_paths:
        candidate = pattern.strip().strip("`").lstrip("./")
        if not candidate:
            continue
        if candidate.endswith("/**") and normalized.startswith(candidate[:-3].rstrip("/") + "/"):
            return True
        if candidate.endswith("/"):
            if normalized.startswith(candidate):
                return True
        if fnmatch(normalized, candidate):
            return True
        if normalized == candidate:
            return True
    return False
