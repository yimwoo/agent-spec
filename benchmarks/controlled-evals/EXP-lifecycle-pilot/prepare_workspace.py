"""Prepare isolated control or AgentSpec workspaces for the lifecycle pilot."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

from agentspec.init import init_project
from agentspec.io import write_data, write_text


PILOT_ROOT = Path(__file__).resolve().parent


def prepare_workspace(destination: Path, condition: str) -> None:
    """Create one committed evaluation workspace.

    Args:
        destination: New workspace directory to populate.
        condition: Either ``control`` or ``with-agentspec``.

    Raises:
        FileExistsError: If ``destination`` already exists.
        ValueError: If ``condition`` is unsupported.
        subprocess.CalledProcessError: If Git initialization fails.
    """

    if condition not in {"control", "with-agentspec"}:
        raise ValueError("condition must be control or with-agentspec")
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")

    shutil.copytree(PILOT_ROOT / "fixture", destination)
    shutil.copy2(PILOT_ROOT / "task.md", destination / "task.md")
    if condition == "with-agentspec":
        _add_agentspec_contract(destination)
    _git(destination, "init", "-q")
    _git(destination, "config", "user.name", "AgentSpec Evaluation")
    _git(destination, "config", "user.email", "evaluation@example.invalid")
    _git(destination, "add", "-A")
    _git(destination, "commit", "-q", "-m", f"Prepare {condition} evaluation fixture")


def _add_agentspec_contract(root: Path) -> None:
    init_project(root, mode="existing", targets="claude,codex")
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {
                "id": "R-001",
                "title": "Normalize accented Latin identifiers without dependencies",
                "status": "accepted",
                "priority": "P0",
                "confidence": "high",
                "source_sections": [],
                "acceptance_criteria": [
                    "Accented Latin text normalizes to ASCII identifiers.",
                    "ASCII, separator collapsing, trimming, and fallback behavior remain compatible.",
                    "The implementation adds no dependency.",
                ],
            }
        ],
    )
    write_data(
        root / "docs" / "discovery" / "readiness.yml",
        {
            "score": 100,
            "mode": "normal-implementation",
            "dimensions": {},
            "summary": "The fixed evaluation task is ready for implementation.",
        },
    )
    write_text(
        root / "agent" / "context-packs" / "T-001-normalize-identifiers.md",
        """# T-001: Normalize identifiers without dependencies

Type: `implementation`
Branch: `unassigned`
Workflow: `none`

## Goal

Fix the Unicode normalization defect described in `task.md`.

## Requirements

- `R-001` Normalize accented Latin identifiers without dependencies (P0, high)

## Allowed Paths

- `src/identifier.py`
- `tests/**`
- `agent/context-packs/T-*.md`
- `agent/handoff.yml`
- `agent/reviews/*.yml`
- `agent/task-ledger.yml`
- `agent/workflows/W-*.md`
- `docs/ROADMAP.md`
- `docs/release/evidence.yml`

## Tests To Add Or Update

- `tests/test_identifier.py`

## Acceptance Criteria

- Use only the Python standard library.
- Preserve the public `slugify` signature.
- Normalize ordinary accented Latin input to its ASCII equivalent.
- Preserve ASCII, separator collapsing, trimming, and fallback behavior.
- Run `python -m unittest discover -s tests -v` before finishing.
""",
    )


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--condition", required=True, choices=("control", "with-agentspec"))
    args = parser.parse_args()
    prepare_workspace(args.destination.resolve(), args.condition)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
