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
