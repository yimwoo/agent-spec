"""Deterministic text, structured-data, hashing, and write-safety helpers."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    """Return the current UTC time as a second-precision ISO 8601 string."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    """Return a prefixed SHA-256 digest for UTF-8 text."""

    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_text(path: Path) -> str:
    """Read a UTF-8 text file."""

    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    """Write UTF-8 text, creating parent directories as needed."""

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
    """Load YAML-compatible JSON, returning a default for missing/empty files."""

    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def copy_text_file(source: Path, destination: Path) -> None:
    """Copy UTF-8 text while creating the destination parent directory."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def lines_between(path: Path, start_line: int, end_line: int) -> str:
    """Return an inclusive one-based line range from a UTF-8 text file."""

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
