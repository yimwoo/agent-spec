from __future__ import annotations

import json
import re
import subprocess
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import load_data, sha256_text, utc_now_iso


SESSION_LEASE_SCHEMA = "agentspec.session_lease.v0"
SESSION_LIST_SCHEMA = "agentspec.session_list.v0"
ALLOWED_SESSION_MODES = {"observer", "owner", "patcher"}
ALLOWED_FINISH_DISPOSITIONS = {"discard", "keep", "merge", "pr"}
ALLOWED_TEST_STATUSES = {"failed", "not_run", "passed"}
WRITE_SESSION_MODES = {"owner", "patcher"}


def start_session(
    root: Path,
    *,
    task_selector: str,
    owner: str | None = None,
    mode: str = "owner",
    branch: str | None = None,
    worktree: str | None = None,
    allow_shared: bool = False,
    session_id: str | None = None,
    run_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    if mode not in ALLOWED_SESSION_MODES:
        raise ValueError(f"mode must be one of: {', '.join(sorted(ALLOWED_SESSION_MODES))}.")

    context_path = _resolve_context_pack_selector(root, task_selector)
    context = _parse_context_pack(root, context_path)
    session_id = session_id or _default_session_id(root, context.get("task_id"))
    _validate_session_id(session_id)

    active_path = _active_path(root, session_id)
    archived_path = _archived_path(root, session_id)
    if active_path.exists() or archived_path.exists():
        raise FileExistsError(f"Session already exists: {session_id}")

    branch = branch or _current_git_branch(root)
    worktree = worktree or _current_git_worktree(root)
    if not allow_shared:
        conflict = _find_write_lease_conflict(
            root,
            mode=mode,
            branch=branch,
            worktree=worktree,
        )
        if conflict is not None:
            raise ValueError(_format_write_lease_conflict(conflict))

    now = utc_now_iso()
    lease = {
        "schema": SESSION_LEASE_SCHEMA,
        "session_id": session_id,
        "status": "active",
        "terminal": False,
        "owner": owner or "unknown",
        "mode": mode,
        "created_at": now,
        "updated_at": now,
        "context_pack": context["context_pack"],
        "context_pack_title": context["title"],
        "context_pack_sha256": context["sha256"],
        "task_id": context.get("task_id"),
        "task_type": context.get("task_type"),
        "originating_dcr": context.get("originating_dcr"),
        "requirements": context.get("requirements", []),
        "allowed_paths": context.get("allowed_paths", []),
        "branch": branch,
        "worktree": worktree,
        "run_id": run_id,
        "note": note,
        "history": [
            {
                "at": now,
                "action": "started",
                "by": owner or "unknown",
                "note": note,
            }
        ],
    }
    _write_new_session(active_path, lease)
    return _with_dynamic_path(root, active_path, lease)


def list_sessions(root: Path) -> dict[str, Any]:
    return build_session_status(root)


def build_session_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    active = [_summary(root, path, record) for path, record in _records_in(_active_dir(root))]
    archived = [_summary(root, path, record) for path, record in _records_in(_archived_dir(root))]
    active = sorted(active, key=lambda record: str(record.get("updated_at", "")), reverse=True)
    archived = sorted(archived, key=lambda record: str(record.get("updated_at", "")), reverse=True)
    by_status = _counts([record.get("status") for record in active + archived])
    return {
        "schema": SESSION_LIST_SCHEMA,
        "root": str(root),
        "total": len(active) + len(archived),
        "counts": {
            "active": len(active),
            "archived": len(archived),
        },
        "by_status": by_status,
        "active": active,
        "archived": archived,
    }


def inspect_session(root: Path, session_id: str) -> dict[str, Any]:
    root = root.resolve()
    _validate_session_id(session_id)
    path = _find_session_path(root, session_id)
    record = _load_session(path)
    return _with_dynamic_path(root, path, record)


def finish_session(
    root: Path,
    session_id: str,
    *,
    disposition: str,
    review_id: str | None = None,
    test_status: str = "not_run",
    note: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    _validate_session_id(session_id)
    if disposition not in ALLOWED_FINISH_DISPOSITIONS:
        raise ValueError(f"disposition must be one of: {', '.join(sorted(ALLOWED_FINISH_DISPOSITIONS))}.")
    if test_status not in ALLOWED_TEST_STATUSES:
        raise ValueError(f"test_status must be one of: {', '.join(sorted(ALLOWED_TEST_STATUSES))}.")

    active_path = _active_path(root, session_id)
    record = _load_active_session(active_path, session_id)
    now = utc_now_iso()
    record.update(
        {
            "status": "finished",
            "terminal": True,
            "disposition": disposition,
            "review_id": review_id,
            "test_status": test_status,
            "finish_note": note,
            "finished_at": now,
            "updated_at": now,
        }
    )
    _append_history(record, at=now, action="finished", note=note, disposition=disposition)
    archived_path = _archive_record(root, active_path, session_id, record)
    return _with_dynamic_path(root, archived_path, record)


def release_session(
    root: Path,
    session_id: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    _validate_session_id(session_id)
    active_path = _active_path(root, session_id)
    record = _load_active_session(active_path, session_id)
    now = utc_now_iso()
    record.update(
        {
            "status": "released",
            "terminal": True,
            "release_reason": reason,
            "released_at": now,
            "updated_at": now,
        }
    )
    _append_history(record, at=now, action="released", note=reason)
    archived_path = _archive_record(root, active_path, session_id, record)
    return _with_dynamic_path(root, archived_path, record)


def format_session_list(payload: dict[str, Any]) -> str:
    counts = payload.get("counts") if isinstance(payload.get("counts"), dict) else {}
    lines = [
        "AgentSpec Sessions",
        f"Active: {counts.get('active', 0)}",
        f"Archived: {counts.get('archived', 0)}",
    ]
    active = payload.get("active") if isinstance(payload.get("active"), list) else []
    if active:
        lines.extend(["", "Active Sessions:"])
        lines.extend(f"- {_session_summary_text(record)}" for record in active)
    archived = payload.get("archived") if isinstance(payload.get("archived"), list) else []
    if archived:
        lines.extend(["", "Archived Sessions:"])
        lines.extend(f"- {_session_summary_text(record)}" for record in archived)
    return "\n".join(lines)


def format_session_record(record: dict[str, Any]) -> str:
    lines = [
        f"Session: {record.get('session_id')}",
        f"Status: {record.get('status')}",
        f"Mode: {record.get('mode')}",
        f"Owner: {record.get('owner')}",
        f"Task: {record.get('task_id') or '-'} {record.get('context_pack') or '-'}",
        f"Branch: {record.get('branch') or '-'}",
        f"Worktree: {record.get('worktree') or '-'}",
        f"Updated: {record.get('updated_at') or '-'}",
    ]
    disposition = record.get("disposition")
    if disposition:
        lines.append(f"Disposition: {disposition}")
    path = record.get("path")
    if path:
        lines.append(f"Path: {path}")
    return "\n".join(lines)


def _active_dir(root: Path) -> Path:
    return root / "agent" / "sessions" / "active"


def _archived_dir(root: Path) -> Path:
    return root / "agent" / "sessions" / "archived"


def _active_path(root: Path, session_id: str) -> Path:
    return _active_dir(root) / f"{session_id}.yml"


def _archived_path(root: Path, session_id: str) -> Path:
    return _archived_dir(root) / f"{session_id}.yml"


def _resolve_context_pack_selector(root: Path, selector: str) -> Path:
    raw = selector.strip()
    if not raw:
        raise ValueError("task selector is required.")
    candidate = Path(raw)
    if candidate.suffix == ".md" or "/" in raw:
        path = candidate if candidate.is_absolute() else root / candidate
        if not path.exists():
            raise FileNotFoundError(f"Context pack not found: {selector}")
        return path.resolve()

    if re.fullmatch(r"T-\d{3,}", raw):
        matches = sorted((root / "agent" / "context-packs").glob(f"{raw}-*.md"))
        if not matches:
            raise FileNotFoundError(f"Context pack not found for task id: {raw}")
        if len(matches) > 1:
            rels = ", ".join(str(path.relative_to(root)) for path in matches)
            raise ValueError(f"Task id {raw} is ambiguous: {rels}")
        return matches[0].resolve()

    raise ValueError("task selector must be a task id like T-001 or a context pack path.")


def _parse_context_pack(root: Path, path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    heading = lines[0].strip() if lines else f"# {path.stem}"
    match = re.match(r"^#\s+(T-\d{3,}):?\s*(.*)$", heading)
    task_id = match.group(1) if match else path.stem.split("-", 2)[0]
    title = match.group(2).strip() if match and match.group(2).strip() else heading.lstrip("# ").strip()
    return {
        "context_pack": str(path.relative_to(root)),
        "title": title,
        "sha256": sha256_text(text),
        "task_id": task_id,
        "task_type": _first_metadata_value(text, "Type") or "implementation",
        "originating_dcr": _first_metadata_value(text, "Originating DCR"),
        "requirements": _requirement_ids(text),
        "allowed_paths": _markdown_list_after_heading(text, "Allowed Paths"),
    }


def _first_metadata_value(text: str, name: str) -> str | None:
    match = re.search(rf"^{re.escape(name)}:\s*`?([^`\n]+)`?\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _requirement_ids(text: str) -> list[str]:
    section = _section_text(text, "Requirements")
    return sorted(set(re.findall(r"`(R-\d{3,})`", section)))


def _section_text(text: str, heading: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_section = False
    heading_re = re.compile(rf"^##\s+{re.escape(heading)}\s*$", flags=re.IGNORECASE)
    for line in lines:
        if heading_re.match(line.strip()):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            out.append(line)
    return "\n".join(out)


def _markdown_list_after_heading(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    items: list[str] = []
    in_section = False
    heading_re = re.compile(rf"^##\s+{re.escape(heading)}\s*$", flags=re.IGNORECASE)
    for line in lines:
        if heading_re.match(line.strip()):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            match = re.match(r"^\s*-\s+`?([^`]+?)`?\s*$", line)
            if match:
                items.append(match.group(1).strip())
    return items


def _default_session_id(root: Path, task_id: str | None) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    task_slug = (task_id or "session").lower()
    base = f"S-{stamp}-{task_slug}-{uuid.uuid4().hex[:8]}"
    candidate = base
    index = 2
    while _active_path(root, candidate).exists() or _archived_path(root, candidate).exists():
        candidate = f"{base}-{index}"
        index += 1
    return candidate


def _current_git_branch(root: Path) -> str | None:
    branch = _git_stdout(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    if branch is None:
        branch = _git_stdout(root, "rev-parse", "--abbrev-ref", "HEAD")
    if not branch or branch == "HEAD":
        return None
    return branch


def _current_git_worktree(root: Path) -> str | None:
    worktree = _git_stdout(root, "rev-parse", "--show-toplevel")
    if not worktree:
        return None
    return str(Path(worktree).resolve())


def _git_stdout(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    value = result.stdout.strip()
    return value or None


def _find_write_lease_conflict(
    root: Path,
    *,
    mode: str,
    branch: str | None,
    worktree: str | None,
) -> dict[str, Any] | None:
    if mode not in WRITE_SESSION_MODES:
        return None
    worktree_key = _worktree_key(root, worktree)
    for _path, record in _records_in(_active_dir(root)):
        if record.get("mode") not in WRITE_SESSION_MODES:
            continue
        existing_branch = record.get("branch")
        if branch and existing_branch == branch:
            return {"record": record, "kind": "branch", "value": branch}
        existing_worktree_key = _worktree_key(root, record.get("worktree"))
        if worktree_key and existing_worktree_key == worktree_key:
            return {"record": record, "kind": "worktree", "value": record.get("worktree") or worktree}
    return None


def _worktree_key(root: Path, worktree: Any) -> str | None:
    if not isinstance(worktree, str) or not worktree.strip():
        return None
    path = Path(worktree)
    if not path.is_absolute():
        path = root / path
    return str(path.resolve())


def _format_write_lease_conflict(conflict: dict[str, Any]) -> str:
    record = conflict["record"]
    subject = f"{conflict['kind']} {conflict['value']}"
    task = record.get("task_id") or record.get("context_pack") or "unknown task"
    return (
        f"Active write session {record.get('session_id')} already leases {subject} for {task}. "
        "Finish or release that session, start a dedicated branch/worktree, "
        "use --mode observer for read-only work, or pass --allow-shared when intentionally sharing."
    )


def _validate_session_id(session_id: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", session_id):
        raise ValueError("session id may contain only letters, digits, '.', '_', and '-'.")


def _records_in(directory: Path) -> list[tuple[Path, dict[str, Any]]]:
    if not directory.is_dir():
        return []
    records: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(directory.glob("*.yml")):
        data = _load_session(path)
        records.append((path, data))
    return records


def _load_session(path: Path) -> dict[str, Any]:
    data = load_data(path, {})
    if not isinstance(data, dict):
        raise ValueError(f"Session record must be an object: {path}")
    if data.get("schema") != SESSION_LEASE_SCHEMA:
        raise ValueError(f"Unsupported session schema in {path}: {data.get('schema')!r}")
    return data


def _load_active_session(path: Path, session_id: str) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Active session not found: {session_id}")
    record = _load_session(path)
    if record.get("status") != "active":
        raise ValueError(f"Session {session_id} is not active.")
    return record


def _write_new_session(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=False)
        handle.write("\n")


def _find_session_path(root: Path, session_id: str) -> Path:
    active_path = _active_path(root, session_id)
    if active_path.exists():
        return active_path
    archived_path = _archived_path(root, session_id)
    if archived_path.exists():
        return archived_path
    raise FileNotFoundError(f"Session not found: {session_id}")


def _archive_record(root: Path, active_path: Path, session_id: str, record: dict[str, Any]) -> Path:
    archived_path = _archived_path(root, session_id)
    if archived_path.exists():
        raise FileExistsError(f"Archived session already exists: {session_id}")
    _write_new_session(archived_path, record)
    active_path.unlink(missing_ok=True)
    return archived_path


def _append_history(record: dict[str, Any], **event: Any) -> None:
    history = record.setdefault("history", [])
    if not isinstance(history, list):
        history = []
        record["history"] = history
    history.append({key: value for key, value in event.items() if value is not None})


def _summary(root: Path, path: Path, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "session_id": record.get("session_id") or path.stem,
        "status": record.get("status"),
        "terminal": bool(record.get("terminal")),
        "owner": record.get("owner"),
        "mode": record.get("mode"),
        "context_pack": record.get("context_pack"),
        "context_pack_title": record.get("context_pack_title"),
        "task_id": record.get("task_id"),
        "task_type": record.get("task_type"),
        "branch": record.get("branch"),
        "worktree": record.get("worktree"),
        "run_id": record.get("run_id"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "disposition": record.get("disposition"),
        "path": _relative_or_absolute(root, path),
    }


def _with_dynamic_path(root: Path, path: Path, record: dict[str, Any]) -> dict[str, Any]:
    out = dict(record)
    out["path"] = _relative_or_absolute(root, path)
    return out


def _counts(values: list[Any]) -> dict[str, int]:
    counter = Counter(str(value) for value in values if value is not None)
    return {key: counter[key] for key in sorted(counter)}


def _session_summary_text(record: dict[str, Any]) -> str:
    bits = [
        str(record.get("session_id")),
        str(record.get("status")),
        str(record.get("mode")),
    ]
    context_pack = record.get("context_pack")
    if context_pack:
        bits.append(str(context_pack))
    branch = record.get("branch")
    if branch:
        bits.append(f"branch {branch}")
    worktree = record.get("worktree")
    if worktree:
        bits.append(f"worktree {worktree}")
    updated_at = record.get("updated_at")
    if updated_at:
        bits.append(f"updated {updated_at}")
    return " | ".join(bits)


def _relative_or_absolute(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
