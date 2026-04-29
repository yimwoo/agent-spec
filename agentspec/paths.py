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
