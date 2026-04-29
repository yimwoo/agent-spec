from __future__ import annotations

import re
from pathlib import Path


ROLE_NAMES = [
    "coordinator",
    "spec-compiler",
    "architect-reviewer",
    "security-reviewer",
    "test-eval-reviewer",
    "brownfield-mapper",
]

ARTIFACT_DIRS = [
    ".agentspec/cache",
    ".agentspec/locks",
    "docs/source",
    "docs/spec",
    "docs/traceability",
    "docs/discovery",
    "docs/adr",
    "docs/change-requests",
    "agent/context-packs",
    "agent/roles",
    "agent/workflows",
    "agent/runs",
    "reports/drift",
    "reports/doctor",
    "reports/traceability",
    "reports/eval",
    "reports/dogfood",
    ".claude/agents",
    ".claude/skills",
    ".codex/agents",
    ".agents/skills",
    ".agents/plugins",
    ".github/workflows",
]


def project_root(path: str | Path = ".") -> Path:
    return Path(path).resolve()


def slugify(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def ensure_dirs(root: Path) -> None:
    for directory in ARTIFACT_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)


def next_numbered_id(prefix: str, existing_ids: list[str]) -> str:
    highest = 0
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for existing_id in existing_ids:
        match = pattern.match(existing_id)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"{prefix}-{highest + 1:03d}"


def path_matches_pattern(path: str, pattern: str) -> bool:
    """Return True when a repo-relative path matches an AgentSpec path pattern.

    AgentSpec patterns intentionally use common globstar semantics:
    `**` crosses directory boundaries and `**/` may match zero or more
    directories, while `*` never crosses `/`.
    """
    normalized_path = _normalize_repo_path(path)
    normalized_pattern = _normalize_repo_path(pattern.strip().strip("`"))
    if not normalized_path or not normalized_pattern:
        return False

    if not _has_glob_syntax(normalized_pattern):
        if normalized_pattern.endswith("/"):
            return normalized_path.startswith(normalized_pattern)
        return normalized_path == normalized_pattern or normalized_path.startswith(normalized_pattern.rstrip("/") + "/")

    return re.match(_glob_to_regex(normalized_pattern), normalized_path) is not None


def _normalize_repo_path(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./").lstrip("/")


def _has_glob_syntax(value: str) -> bool:
    return any(char in value for char in "*?[")


def _glob_to_regex(pattern: str) -> str:
    out = ["^"]
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if i + 1 < len(pattern) and pattern[i + 1] == "*":
                if i + 2 < len(pattern) and pattern[i + 2] == "/":
                    out.append("(?:.*/)?")
                    i += 3
                else:
                    out.append(".*")
                    i += 2
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        i += 1
    out.append("$")
    return "".join(out)


def truncate_on_word_boundary(text: str, limit: int = 96) -> str:
    """Truncate `text` on a word boundary at or before `limit` chars.

    Implements R-141: pack titles must not end mid-word. If `text` is
    already short enough, it is returned unchanged. Otherwise the slice
    falls back to the previous space; if that would shorten too
    aggressively (more than half the limit lost), the original slice is
    used and an ellipsis is appended without word-boundary correction.
    """
    text = text.rstrip(" .,;:")
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    last_space = truncated.rfind(" ")
    if last_space >= max(1, limit // 2):
        truncated = truncated[:last_space]
    return truncated.rstrip(" .,;:") + "…"
