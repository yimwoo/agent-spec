from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_data(path: Path, data: Any) -> None:
    """Write deterministic YAML-compatible JSON.

    AgentSpec uses .yml filenames because the product surface is YAML-oriented,
    but the MVP intentionally stays dependency-free. JSON is valid YAML 1.2,
    easy to diff, and round-trips through the standard library.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def load_data(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def copy_text_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def lines_between(path: Path, start_line: int, end_line: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[start_line - 1 : end_line])


def ensure_writable_dir(path: Path, *, label: str = "Report destination") -> None:
    """Create `path` if missing and confirm it is writable.

    Raises PermissionError with the offending path when the directory
    cannot be created or a probe file cannot be written. Callers pass
    `label` so cross-repo report and run-state preflights can keep
    actionable, domain-specific error messages.
    """

    try:
        path.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise PermissionError(f"{label} is not writable: {path}") from exc

    probe = path / ".agentspec-write-probe"
    try:
        probe.write_text("", encoding="utf-8")
    except PermissionError as exc:
        raise PermissionError(f"{label} is not writable: {path}") from exc
    finally:
        try:
            probe.unlink()
        except FileNotFoundError:
            pass
        except PermissionError:
            pass
