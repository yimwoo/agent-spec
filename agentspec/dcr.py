"""Design Change Request parsing and validation.

Implements the schema contract defined by ADR-0002 and the requirements
R-121, R-122, R-123 (DCR-0002). Read-only — produces dicts that callers can
inspect; never modifies a DCR file.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from .io import load_data, write_data, write_text
from .paths import is_untracked_git_ignored, slugify


ALLOWED_CLASSIFICATIONS: frozenset[str] = frozenset(
    {"implement-now", "defer", "spike", "reject", "needs-adr"}
)
ALLOWED_STATUSES: frozenset[str] = frozenset(
    {"open", "classified", "accepted", "superseded", "rejected"}
)
REQUIRED_FIELDS: tuple[str, ...] = (
    "Status",
    "Classification",
    "Submitted",
    "Submitted by",
    "Decided by",
    "Decided on",
    "Confidence",
)

_TITLE_RE = re.compile(r"^#\s+(DCR-\d{4,})\b", re.MULTILINE)
_TABLE_ALIGNMENT_RE = re.compile(r"^\|[\s\-:|]+\|\s*$")


class DCRSchemaError(ValueError):
    """Raised when a DCR document violates the canonical schema."""


def parse_dcr(path: Path) -> dict[str, Any]:
    text = Path(path).read_text(encoding="utf-8")
    dcr_id = _extract_id(text, path)
    fields = _parse_metadata_table(text)
    _check_required(fields, path)

    classification = _extract_classification(fields["Classification"])
    status = _extract_status(fields["Status"])

    return {
        "id": dcr_id,
        "path": str(Path(path)),
        "status": status,
        "classification": classification,
        "submitted": fields["Submitted"],
        "submitted_by": fields["Submitted by"],
        "decided_by": fields["Decided by"],
        "decided_on": fields["Decided on"],
        "confidence": fields["Confidence"],
    }


def is_implementation_eligible(dcr: dict[str, Any]) -> bool:
    """Return True iff a context pack may cite this DCR.

    Per DCR-0002 / R-123: a task context pack may not be created until the
    DCR is classified `implement-now`, OR is `needs-adr` with the related
    ADR accepted (the latter is signalled by the DCR's own status
    transitioning to `accepted`).
    """
    classification = dcr.get("classification")
    status = dcr.get("status")
    if classification == "implement-now" and status in {"classified", "accepted"}:
        return True
    if classification == "needs-adr" and status == "accepted":
        return True
    return False


def find_dcr_by_id(root: Path, dcr_id: str) -> Path | None:
    """Locate a DCR file by its ID (e.g. 'DCR-0099').

    Convention: `docs/change-requests/<DCR-ID>-<slug>.md`.
    """
    directory = Path(root) / "docs" / "change-requests"
    if not directory.is_dir():
        return None
    for candidate in sorted(directory.glob(f"{dcr_id}-*.md")):
        return candidate
    return None


def _extract_id(text: str, path: Path) -> str:
    match = _TITLE_RE.search(text)
    if not match:
        raise DCRSchemaError(
            f"{path}: first heading must be '# DCR-NNNN: ...' (got: {text.splitlines()[0] if text else '<empty>'!r})"
        )
    return match.group(1)


def _parse_metadata_table(text: str) -> dict[str, str]:
    """Return the first markdown pipe-table's body rows as {key: value}."""
    rows: list[str] = []
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            in_block = True
            rows.append(stripped)
        elif in_block:
            break
    if len(rows) < 3:
        return {}
    parsed: dict[str, str] = {}
    for row in rows[1:]:
        if _TABLE_ALIGNMENT_RE.match(row):
            continue
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if len(cells) >= 2:
            parsed[cells[0]] = cells[1]
    return parsed


def _check_required(fields: dict[str, str], path: Path) -> None:
    missing = [name for name in REQUIRED_FIELDS if name not in fields or not fields[name]]
    if missing:
        raise DCRSchemaError(
            f"{path}: DCR metadata table is missing required field(s): {', '.join(missing)}"
        )


def _extract_classification(value: str) -> str:
    cleaned = value.replace("**", "")
    matches: list[tuple[int, str]] = []
    for token in ALLOWED_CLASSIFICATIONS:
        match = re.search(r"(?<![A-Za-z])" + re.escape(token) + r"(?![A-Za-z])", cleaned)
        if match:
            matches.append((match.start(), token))
    if not matches:
        raise DCRSchemaError(
            f"DCR Classification field has no recognised value. "
            f"Got: {value!r}. Allowed: {sorted(ALLOWED_CLASSIFICATIONS)}."
        )
    matches.sort()
    return matches[0][1]


def next_dcr_id(root: Path) -> str:
    directory = Path(root) / "docs" / "change-requests"
    if not directory.is_dir():
        return "DCR-0001"
    highest = 0
    pattern = re.compile(r"^DCR-(\d+)-")
    for path in directory.glob("DCR-*.md"):
        match = pattern.match(path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return f"DCR-{highest + 1:04d}"


def create_dcr_stub(
    root: Path,
    title: str,
    classification: str,
    dcr_id: str | None = None,
    submitted_by: str = "user",
    decided_by: str = "user",
) -> Path:
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise DCRSchemaError(
            f"Unknown classification {classification!r}. Allowed: {sorted(ALLOWED_CLASSIFICATIONS)}."
        )
    if not title.strip():
        raise ValueError("DCR title must not be empty.")

    if dcr_id is None:
        dcr_id = next_dcr_id(root)
    elif not re.match(r"^DCR-\d{4,}$", dcr_id):
        raise ValueError(f"DCR id must look like DCR-NNNN; got {dcr_id!r}.")

    today = date.today().isoformat()
    slug = slugify(title) or "untitled"
    path = Path(root) / "docs" / "change-requests" / f"{dcr_id}-{slug}.md"
    if path.exists():
        raise FileExistsError(f"DCR file already exists: {path}")

    body = (
        f"# {dcr_id}: {title}\n\n"
        f"| Field | Value |\n"
        f"|---|---|\n"
        f"| Status | classified |\n"
        f"| Classification | {classification} |\n"
        f"| Submitted | {today} |\n"
        f"| Submitted by | {submitted_by} |\n"
        f"| Decided by | {decided_by} |\n"
        f"| Decided on | {today} |\n"
        f"| Confidence | medium |\n\n"
        f"## Summary\n\n"
        f"<!-- describe the change in 1-2 paragraphs -->\n\n"
        f"## Motivation\n\n"
        f"<!-- why now, what gap -->\n\n"
        f"## Proposed Change\n\n"
        f"<!-- concrete description -->\n\n"
        f"## Impact Assessment\n\n"
        f"<!-- affected requirements, packs, spec docs, code modules -->\n\n"
        f"## Disposition\n\n"
        f"<!-- recommendation and required follow-ups -->\n\n"
        f"## Acceptance Criteria\n\n"
        f"<!-- what done looks like -->\n"
    )
    write_text(path, body)
    return path


def set_classification(root: Path, dcr_id: str, new_classification: str) -> Path:
    if new_classification not in ALLOWED_CLASSIFICATIONS:
        raise DCRSchemaError(
            f"Unknown classification {new_classification!r}. Allowed: {sorted(ALLOWED_CLASSIFICATIONS)}."
        )
    path = find_dcr_by_id(root, dcr_id)
    if path is None:
        raise FileNotFoundError(f"DCR not found: {dcr_id}")
    parse_dcr(path)  # validate the file is well-formed before mutating
    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r"^\|\s*Classification\s*\|[^\n]*\|\s*$",
        f"| Classification | {new_classification} |",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        raise DCRSchemaError(f"{path}: could not locate Classification row")
    write_text(path, new_text)
    return path


def accept_dcr(root: Path, dcr_id: str) -> dict[str, Any]:
    """Flip a DCR's Status row to `accepted` and update Decided-on to today.

    Per DCR-0004 / R-133, this command does NOT cascade to requirements.
    Requirement-level acceptance is a separate command;
    see `agentspec.requirement.accept_requirement`.
    """
    path = find_dcr_by_id(root, dcr_id)
    if path is None:
        raise FileNotFoundError(f"DCR not found: {dcr_id}")
    parse_dcr(path)

    text = path.read_text(encoding="utf-8")
    new_text, count = re.subn(
        r"^\|\s*Status\s*\|[^\n]*\|\s*$",
        "| Status | accepted |",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    if count == 0:
        raise DCRSchemaError(f"{path}: could not locate Status row")

    today = date.today().isoformat()
    new_text, _ = re.subn(
        r"^\|\s*Decided on\s*\|[^\n]*\|\s*$",
        f"| Decided on | {today} |",
        new_text,
        count=1,
        flags=re.MULTILINE,
    )
    write_text(path, new_text)

    return {"dcr_id": dcr_id, "path": str(path)}


def list_dcrs(root: Path, *, include_untracked_gitignored: bool = True) -> list[dict[str, Any]]:
    directory = Path(root) / "docs" / "change-requests"
    if not directory.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(directory.glob("DCR-*.md")):
        if not include_untracked_gitignored and is_untracked_git_ignored(root, path):
            continue
        try:
            dcr = parse_dcr(path)
        except DCRSchemaError:
            continue
        records.append(dcr)
    return records


def _extract_status(value: str) -> str:
    cleaned = value.replace("**", "").strip().lower()
    # The status field is usually a single token, but allow trailing commentary.
    first_token = re.split(r"\s|[(,]", cleaned, maxsplit=1)[0]
    if first_token not in ALLOWED_STATUSES:
        raise DCRSchemaError(
            f"DCR Status field has no recognised value. "
            f"Got: {value!r}. Allowed: {sorted(ALLOWED_STATUSES)}."
        )
    return first_token
