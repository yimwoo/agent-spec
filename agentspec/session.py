from __future__ import annotations

import json
import os
import re
import subprocess
import time
import uuid
from collections import Counter
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .io import load_data, sha256_text, utc_now_iso


SESSION_LEASE_SCHEMA = "agentspec.session_lease.v0"
SESSION_LIST_SCHEMA = "agentspec.session_list.v0"
SESSION_PREFLIGHT_SCHEMA = "agentspec.session_preflight.v0"
SESSION_CLEANUP_SCHEMA = "agentspec.session_cleanup.v0"
ALLOWED_SESSION_MODES = {"observer", "owner", "patcher"}
ALLOWED_FINISH_DISPOSITIONS = {"discard", "keep", "merge", "pr"}
ALLOWED_TEST_STATUSES = {"failed", "not_run", "passed"}
WRITE_SESSION_MODES = {"owner", "patcher"}
DELIVERY_CLOSED_DISPOSITIONS = {"discard", "merge", "pr"}
PROTECTED_BRANCHES = {"main", "master"}
SESSION_START_LOCK_TIMEOUT_SECONDS = 10.0
SESSION_START_LOCK_POLL_SECONDS = 0.02


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
    with _session_start_lock(root):
        archived_path = _archived_path(root, session_id)
        if active_path.exists() or archived_path.exists():
            raise FileExistsError(f"Session already exists: {session_id}")

        branch = branch or _current_git_branch(root)
        worktree = worktree or _current_git_worktree(root)
        if (
            mode in WRITE_SESSION_MODES
            and context.get("task_type") == "implementation"
            and not _explicit_host_worktree_execution(context)
            and _protected_branch(branch)
        ):
            raise ValueError(
                "Implementation sessions require an isolated branch/worktree; "
                f"refusing protected branch {branch!r}. Declare Host Worktree Execution: `explicit` "
                "in the task or workflow only when host-worktree execution is intentional."
            )
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
    active_records = _records_in(_active_dir(root))
    archived_records = _records_in(_archived_dir(root))
    active = [_summary(root, path, record) for path, record in active_records]
    active_write_leases = _active_write_leases(root, active)
    archived = [
        _summary(
            root,
            path,
            record,
            cleanup_eligibility=_cleanup_eligibility(root, record, active_write_leases),
        )
        for path, record in archived_records
    ]
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
        "cleanup": _cleanup_projection(archived),
    }


def build_session_preflight(
    root: Path,
    *,
    task_selector: str | None = None,
    context_pack: str | None = None,
    task_id: str | None = None,
    task_type: str | None = None,
) -> dict[str, Any]:
    """Report whether a task has an active write lease before execution."""

    root = root.resolve()
    context = _preflight_context(
        root,
        task_selector=task_selector,
        context_pack=context_pack,
        task_id=task_id,
        task_type=task_type,
    )
    required = context["task_type"] == "implementation"
    if not required:
        return {
            "schema": SESSION_PREFLIGHT_SCHEMA,
            "status": "not_required",
            "required": False,
            **context,
            "active_session": None,
            "satisfied_by": None,
            "message": "Branch/worktree session preflight applies only to implementation tasks.",
            "recommended_command": None,
            "agent_guidance": "Continue under the task context pack rules.",
        }

    if _explicit_host_worktree_execution(context):
        return {
            "schema": SESSION_PREFLIGHT_SCHEMA,
            "status": "satisfied",
            "required": True,
            **context,
            "active_session": None,
            "satisfied_by": "explicit_host_worktree",
            "message": "Explicit host-worktree execution is declared for this implementation task.",
            "recommended_command": None,
            "agent_guidance": (
                "Continue execution in the declared host worktree only because the "
                "context pack records host-worktree execution as an intentional mode."
            ),
        }

    context_blocker = _branch_isolation_blocker(context)
    if context_blocker is not None:
        return {
            "schema": SESSION_PREFLIGHT_SCHEMA,
            "status": "blocked",
            "required": True,
            **context,
            "active_session": None,
            "satisfied_by": None,
            "blocker": context_blocker,
            "message": context_blocker["message"],
            "recommended_command": _session_start_command(root, context),
            "agent_guidance": context_blocker["guidance"],
        }

    active = _active_write_session_for_context(
        root,
        context_pack=context.get("context_pack"),
        task_id=context.get("task_id"),
    )
    if active is not None:
        active_blocker = _branch_isolation_blocker(active)
        if active_blocker is not None:
            return {
                "schema": SESSION_PREFLIGHT_SCHEMA,
                "status": "blocked",
                "required": True,
                **context,
                "active_session": active,
                "satisfied_by": None,
                "blocker": active_blocker,
                "message": active_blocker["message"],
                "recommended_command": _session_start_command(root, context),
                "agent_guidance": active_blocker["guidance"],
            }
        return {
            "schema": SESSION_PREFLIGHT_SCHEMA,
            "status": "satisfied",
            "required": True,
            **context,
            "active_session": active,
            "satisfied_by": "session_lease",
            "message": "Active owner/patcher session lease with isolated branch and worktree metadata is present.",
            "recommended_command": None,
            "agent_guidance": "Continue execution inside the active session lease and task allowed paths.",
        }

    command = _session_start_command(root, context)
    return {
        "schema": SESSION_PREFLIGHT_SCHEMA,
        "status": "missing",
        "required": True,
        **context,
        "active_session": None,
        "satisfied_by": None,
        "message": (
            "No active owner or patcher session lease with branch and worktree metadata "
            "covers this implementation task."
        ),
        "recommended_command": command,
        "agent_guidance": (
            "Claim or create a branch/worktree session before mutating code, or record "
            "an explicit host-worktree session when sharing this checkout is intentional."
        ),
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


def _session_start_lock_path(root: Path) -> Path:
    return _active_dir(root) / ".session-start.lock"


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
    workflow = _first_metadata_value(text, "Workflow")
    return {
        "context_pack": str(path.relative_to(root)),
        "title": title,
        "sha256": sha256_text(text),
        "task_id": task_id,
        "task_type": _first_metadata_value(text, "Type") or "implementation",
        "originating_dcr": _first_metadata_value(text, "Originating DCR"),
        "workflow": workflow,
        "branch": _effective_metadata_value(text, "Branch") or _workflow_metadata_value(root, workflow, "branch"),
        "worktree": _effective_metadata_value(text, "Worktree") or _workflow_metadata_value(root, workflow, "worktree"),
        "host_worktree_execution": _first_metadata_value(text, "Host Worktree Execution")
        or _workflow_metadata_value(root, workflow, "host_worktree_execution"),
        "requirements": _requirement_ids(text),
        "allowed_paths": _markdown_list_after_heading(text, "Allowed Paths"),
    }


def _first_metadata_value(text: str, name: str) -> str | None:
    match = re.search(rf"^{re.escape(name)}:\s*`?([^`\n]+)`?\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _effective_metadata_value(text: str, name: str) -> str | None:
    value = _first_metadata_value(text, name)
    if value is None or value.strip().lower() in {"", "none", "unassigned"}:
        return None
    return value


def _workflow_metadata_value(root: Path, workflow: str | None, name: str) -> str | None:
    if not workflow:
        return None
    path = Path(workflow)
    candidate = path if path.is_absolute() else root / path
    try:
        candidate = candidate.resolve()
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    text = candidate.read_text(encoding="utf-8")
    frontmatter = _frontmatter(text)
    match = re.search(rf"^\s*{re.escape(name)}:\s*`?([^`\n]+)`?\s*$", frontmatter, flags=re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip().strip('"').strip("'")
    return value or None


def _frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    return parts[1] if len(parts) >= 3 else ""


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


@contextmanager
def _session_start_lock(root: Path):
    lock_path = _session_start_lock_path(root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + SESSION_START_LOCK_TIMEOUT_SECONDS
    acquired = False
    while not acquired:
        try:
            with lock_path.open("x", encoding="utf-8") as handle:
                handle.write(f"{os.getpid()}\n")
            acquired = True
        except FileExistsError as exc:
            if _clear_stale_session_start_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for session start lock: {lock_path}") from exc
            time.sleep(SESSION_START_LOCK_POLL_SECONDS)
    try:
        yield
    finally:
        with suppress(FileNotFoundError):
            lock_path.unlink()


def _clear_stale_session_start_lock(lock_path: Path) -> bool:
    pid = _read_session_start_lock_pid(lock_path)
    if pid is None or _process_exists(pid):
        return False
    with suppress(FileNotFoundError):
        lock_path.unlink()
        return True
    return False


def _read_session_start_lock_pid(lock_path: Path) -> int | None:
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw.isdigit():
        return None
    return int(raw)


def _process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (PermissionError, OSError):
        return True
    return True


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


def _preflight_context(
    root: Path,
    *,
    task_selector: str | None,
    context_pack: str | None,
    task_id: str | None,
    task_type: str | None,
) -> dict[str, Any]:
    context: dict[str, Any] = {
        "context_pack": context_pack,
        "task_id": task_id,
        "task_type": task_type or "implementation",
    }
    selector = task_selector or context_pack
    if selector:
        try:
            parsed = _parse_context_pack(root, _resolve_context_pack_selector(root, selector))
        except (FileNotFoundError, ValueError):
            parsed = {}
        if parsed:
            context.update(
                {
                    "context_pack": parsed.get("context_pack"),
                    "task_id": parsed.get("task_id"),
                    "task_type": parsed.get("task_type") or context["task_type"],
                    "workflow": parsed.get("workflow"),
                    "branch": parsed.get("branch"),
                    "worktree": parsed.get("worktree"),
                    "host_worktree_execution": parsed.get("host_worktree_execution"),
                }
            )
    return context


def _explicit_host_worktree_execution(context: dict[str, Any]) -> bool:
    value = context.get("host_worktree_execution")
    return isinstance(value, str) and value.strip().lower() == "explicit"


def _branch_isolation_blocker(context: dict[str, Any]) -> dict[str, Any] | None:
    branch = context.get("branch")
    if _protected_branch(branch):
        return {
            "type": "protected_branch",
            "branch": branch,
            "message": (
                "Implementation lifecycle requires an isolated branch/worktree; "
                f"protected branch {branch!r} is not allowed without an explicit host-worktree escape hatch."
            ),
            "guidance": (
                "Create or switch to a dedicated branch/worktree before implementation, "
                "or declare Host Worktree Execution: `explicit` in the task/workflow when this is intentional."
            ),
        }
    return None


def _protected_branch(branch: Any) -> bool:
    return isinstance(branch, str) and branch.strip() in PROTECTED_BRANCHES


def _active_write_session_for_context(
    root: Path,
    *,
    context_pack: Any,
    task_id: Any,
) -> dict[str, Any] | None:
    for path, record in _records_in(_active_dir(root)):
        if record.get("mode") not in WRITE_SESSION_MODES:
            continue
        if not record.get("branch") or not record.get("worktree"):
            continue
        if context_pack and record.get("context_pack") == context_pack:
            return _summary(root, path, record)
        if task_id and record.get("task_id") == task_id:
            return _summary(root, path, record)
    return None


def _session_start_command(root: Path, context: dict[str, Any]) -> str:
    task_selector = _session_start_task_selector(root, context)
    branch = _recommended_session_branch(root, context)
    worktree = _current_git_worktree(root) or str(root)
    return (
        f"aspec session start --task {task_selector} --owner <owner> "
        f"--branch {branch} --worktree {worktree}"
    )


def _recommended_session_branch(root: Path, context: dict[str, Any]) -> str:
    context_branch = context.get("branch")
    if isinstance(context_branch, str) and context_branch.strip() and not _protected_branch(context_branch):
        return context_branch.strip()
    current = _current_git_branch(root)
    if current and not _protected_branch(current):
        return current
    task_id = str(context.get("task_id") or "task").lower()
    return f"codex/{task_id}-implementation"


def _session_start_task_selector(root: Path, context: dict[str, Any]) -> str:
    task_id = context.get("task_id")
    context_pack = context.get("context_pack")
    if isinstance(task_id, str) and task_id:
        if isinstance(context_pack, str) and context_pack and _task_id_is_ambiguous(root, task_id):
            return context_pack
        return task_id
    if isinstance(context_pack, str) and context_pack:
        return context_pack
    return "<task>"


def _task_id_is_ambiguous(root: Path, task_id: str) -> bool:
    if not re.fullmatch(r"T-\d{3,}", task_id):
        return False
    matches = sorted((root / "agent" / "context-packs").glob(f"{task_id}-*.md"))
    return len(matches) > 1


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


def _summary(
    root: Path,
    path: Path,
    record: dict[str, Any],
    *,
    cleanup_eligibility: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = {
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
    if cleanup_eligibility is not None:
        summary["cleanup_eligibility"] = cleanup_eligibility
    return summary


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


def _cleanup_projection(archived: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        _cleanup_summary(record)
        for record in archived
        if _dict(record.get("cleanup_eligibility")).get("eligible") is True
    ]
    blocked = [
        _cleanup_summary(record)
        for record in archived
        if _dict(record.get("cleanup_eligibility")).get("eligible") is False
    ]
    by_status = _counts(
        [
            _dict(record.get("cleanup_eligibility")).get("status")
            for record in archived
            if isinstance(record.get("cleanup_eligibility"), dict)
        ]
    )
    return {
        "schema": SESSION_CLEANUP_SCHEMA,
        "advisory": True,
        "summary": "Cleanup is advisory; AgentSpec does not delete branches or worktrees without explicit confirmation.",
        "counts": {
            "eligible": len(eligible),
            "blocked": len(blocked),
            "by_status": by_status,
        },
        "eligible": eligible,
        "blocked": blocked,
    }


def _cleanup_summary(record: dict[str, Any]) -> dict[str, Any]:
    eligibility = _dict(record.get("cleanup_eligibility"))
    return {
        "session_id": record.get("session_id"),
        "task_id": record.get("task_id"),
        "branch": record.get("branch"),
        "worktree": record.get("worktree"),
        "disposition": record.get("disposition"),
        "status": eligibility.get("status"),
        "reasons": eligibility.get("reasons", []),
        "closures": eligibility.get("closures", {}),
        "resources": eligibility.get("resources", {}),
    }


def _cleanup_eligibility(
    root: Path,
    record: dict[str, Any],
    active_write_leases: list[dict[str, Any]],
) -> dict[str, Any]:
    resources = {
        "branch": _branch_cleanup_eligibility(root, record),
        "worktree": _worktree_cleanup_eligibility(root, record),
    }
    task_closure = _task_closure(root, record)
    delivery_closure = _delivery_closure(record)
    local_resource_closure = _local_resource_closure(resources, delivery_closure)
    closures = {
        "task": task_closure,
        "delivery": delivery_closure,
        "local_resources": local_resource_closure,
    }
    reasons = _cleanup_blocking_reasons(root, record, active_write_leases)
    for closure in closures.values():
        reasons.extend(str(reason) for reason in closure.get("reasons", []))

    reasons = sorted(set(reasons))
    eligible = (
        not reasons
        and task_closure.get("status") == "closed"
        and delivery_closure.get("status") == "closed"
        and local_resource_closure.get("status") == "eligible"
    )
    status = _cleanup_status(
        eligible=eligible,
        task_closure=task_closure,
        delivery_closure=delivery_closure,
        local_resource_closure=local_resource_closure,
    )
    return {
        "schema": SESSION_CLEANUP_SCHEMA,
        "eligible": eligible,
        "status": status,
        "advisory": True,
        "reasons": reasons,
        "closures": closures,
        "resources": resources,
        "message": _cleanup_message(eligible, status, reasons),
    }


def _cleanup_status(
    *,
    eligible: bool,
    task_closure: dict[str, Any],
    delivery_closure: dict[str, Any],
    local_resource_closure: dict[str, Any],
) -> str:
    if eligible:
        return "eligible"
    if delivery_closure.get("status") == "kept":
        return "kept"
    if delivery_closure.get("status") == "released":
        return "released"
    if (
        task_closure.get("status") == "closed"
        and delivery_closure.get("status") == "closed"
        and local_resource_closure.get("status") == "already_removed"
    ):
        return "already_removed"
    return "blocked"


def _task_closure(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    if record.get("mode") not in WRITE_SESSION_MODES:
        return _closure_status("not_applicable", ["not_write_session"])
    if record.get("status") == "released":
        return _closure_status("released", ["released_without_task_closure"])
    if record.get("status") != "finished" or not record.get("terminal"):
        return _closure_status("blocked", ["session_not_finished"])

    reasons: list[str] = []
    if record.get("test_status") != "passed":
        reasons.append("session_verification_not_passed")
    if not record.get("review_id"):
        reasons.append("session_review_missing")

    context_pack = record.get("context_pack")
    if not isinstance(context_pack, str) or not context_pack.strip():
        reasons.append("missing_context_pack")
    else:
        ledger_entry = _task_ledger_entry(root, context_pack)
        if not isinstance(ledger_entry, dict) or ledger_entry.get("status") != "complete":
            reasons.append("task_writeback_missing")
        else:
            verification = _dict(ledger_entry.get("verification"))
            if verification.get("status") != "passed":
                reasons.append("task_verification_not_passed")
            if not _dict(ledger_entry.get("code_review")).get("id"):
                reasons.append("task_review_missing")

    return _closure_status("closed" if not reasons else "blocked", reasons)


def _delivery_closure(record: dict[str, Any]) -> dict[str, Any]:
    disposition = record.get("disposition")
    if record.get("status") == "released":
        return _closure_status("released", ["released_without_delivery_closure"], disposition=disposition)
    if disposition == "keep":
        return _closure_status("kept", ["disposition_keep"], disposition=disposition)
    if disposition in DELIVERY_CLOSED_DISPOSITIONS:
        return _closure_status("closed", [], disposition=disposition)
    return _closure_status("blocked", ["missing_delivery_disposition"], disposition=disposition)


def _local_resource_closure(
    resources: dict[str, dict[str, Any]],
    delivery_closure: dict[str, Any],
) -> dict[str, Any]:
    if delivery_closure.get("status") != "closed":
        return _closure_status("blocked", [])

    blocked_reasons: list[str] = []
    for name, resource in resources.items():
        if _dict(resource).get("status") == "blocked":
            blocked_reasons.extend(f"{name}:{reason}" for reason in _dict(resource).get("reasons", []))

    if blocked_reasons:
        return _closure_status("blocked", blocked_reasons)
    if any(_dict(resource).get("eligible") is True for resource in resources.values()):
        return _closure_status("eligible", [])
    if resources and all(_dict(resource).get("status") == "already_removed" for resource in resources.values()):
        return _closure_status("already_removed", [])
    return _closure_status("blocked", ["no_cleanup_resource"])


def _closure_status(status: str, reasons: list[str], **extra: Any) -> dict[str, Any]:
    return {
        "status": status,
        "closed": status == "closed",
        "reasons": reasons,
        **extra,
    }


def _cleanup_blocking_reasons(
    root: Path,
    record: dict[str, Any],
    active_write_leases: list[dict[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    if record.get("mode") not in WRITE_SESSION_MODES:
        reasons.append("not_write_session")
    if not record.get("terminal"):
        reasons.append("session_not_terminal")
    if _record_worktree_has_changes(root, record):
        reasons.append("worktree_dirty")
    branch = record.get("branch")
    worktree_key = _worktree_key(root, record.get("worktree"))
    for lease in active_write_leases:
        if branch and lease.get("branch") == branch:
            reasons.append("active_session_same_branch")
        if worktree_key and lease.get("worktree_key") == worktree_key:
            reasons.append("active_session_same_worktree")
    return sorted(set(reasons))


def _branch_cleanup_eligibility(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    branch = record.get("branch")
    if not isinstance(branch, str) or not branch.strip():
        return _resource_status("blocked", False, ["missing_branch_metadata"])
    if branch in PROTECTED_BRANCHES:
        return _resource_status("blocked", False, ["protected_branch"])
    if not _git_branch_exists(root, branch):
        return _resource_status("already_removed", False, ["branch_missing"])

    disposition = record.get("disposition")
    if disposition == "discard":
        reasons = ["discard_disposition"]
    elif disposition in {"merge", "pr"}:
        target = _merge_target(root)
        if target and _git_ref_is_ancestor(root, branch, target):
            reasons = [f"merged_into_{target}"]
        else:
            return _resource_status("blocked", False, ["missing_merge_evidence"])
    else:
        return _resource_status("blocked", False, ["delivery_not_closed"])

    checkout_status = _branch_checkout_status(root, branch, record)
    if checkout_status == "cleanup_worktree":
        return _resource_status("eligible_after_worktree", True, [*reasons, "remove_worktree_first"])
    if checkout_status == "other_worktree":
        return _resource_status("blocked", False, ["branch_checked_out"])
    return _resource_status("eligible", True, reasons)


def _worktree_cleanup_eligibility(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    worktree = record.get("worktree")
    if not isinstance(worktree, str) or not worktree.strip():
        return _resource_status("blocked", False, ["missing_worktree_metadata"])
    path = Path(worktree)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if path == root:
        return _resource_status("blocked", False, ["host_worktree_not_removed"])
    if not path.exists():
        return _resource_status("already_removed", False, ["worktree_missing"])
    status = _git_status_porcelain(path)
    if status is None:
        return _resource_status("blocked", False, ["worktree_status_unavailable"])
    if status.strip():
        return _resource_status("blocked", False, ["worktree_dirty"])
    if record.get("disposition") in DELIVERY_CLOSED_DISPOSITIONS:
        return _resource_status("eligible", True, ["clean_worktree"])
    return _resource_status("blocked", False, ["delivery_not_closed"])


def _resource_status(status: str, eligible: bool, reasons: list[str]) -> dict[str, Any]:
    return {
        "status": status,
        "eligible": eligible,
        "reasons": reasons,
    }


def _cleanup_message(eligible: bool, status: str, reasons: list[str]) -> str:
    if eligible:
        return "Branch/worktree cleanup is eligible after explicit confirmation."
    if status == "kept":
        return "Branch/worktree is intentionally kept."
    if status == "released":
        return "Session was released without final delivery closure; cleanup is not implied."
    if status == "already_removed":
        return "Recorded branch/worktree resources are already absent."
    return "Branch/worktree cleanup is blocked: " + ", ".join(reasons)


def _active_write_leases(root: Path, active: list[dict[str, Any]]) -> list[dict[str, Any]]:
    leases: list[dict[str, Any]] = []
    for record in active:
        if record.get("mode") not in WRITE_SESSION_MODES:
            continue
        leases.append(
            {
                "session_id": record.get("session_id"),
                "branch": record.get("branch"),
                "worktree_key": _worktree_key(root, record.get("worktree")),
            }
        )
    return leases


def _task_ledger_entry(root: Path, context_pack: str) -> dict[str, Any] | None:
    ledger = load_data(root / "agent" / "task-ledger.yml", {}) or {}
    tasks = ledger.get("tasks") if isinstance(ledger, dict) else {}
    if not isinstance(tasks, dict):
        return None
    entry = tasks.get(context_pack)
    return entry if isinstance(entry, dict) else None


def _git_branch_exists(root: Path, branch: str) -> bool:
    return _git_success(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}")


def _branch_checkout_status(root: Path, branch: str, record: dict[str, Any]) -> str | None:
    ref = f"refs/heads/{branch}"
    checkouts = [git_record for git_record in _git_worktree_records(root) if git_record.get("branch") == ref]
    if not checkouts:
        return None
    worktree_key = _worktree_key(root, record.get("worktree"))
    if worktree_key and all(_worktree_key(root, git_record.get("worktree")) == worktree_key for git_record in checkouts):
        if worktree_key != str(root.resolve()):
            return "cleanup_worktree"
    return "other_worktree"


def _merge_target(root: Path) -> str | None:
    for branch in ("main", "master"):
        if _git_branch_exists(root, branch):
            return branch
    return "HEAD" if _git_stdout(root, "rev-parse", "--verify", "HEAD") else None


def _git_ref_is_ancestor(root: Path, ref: str, target: str) -> bool:
    return _git_success(root, "merge-base", "--is-ancestor", ref, target)


def _worktree_has_changes(path: Path) -> bool:
    status = _git_status_porcelain(path)
    return bool(status and status.strip())


def _git_status_porcelain(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout


def _record_worktree_has_changes(root: Path, record: dict[str, Any]) -> bool:
    worktree = record.get("worktree")
    if not isinstance(worktree, str) or not worktree.strip():
        return False
    path = Path(worktree)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    return path.exists() and _worktree_has_changes(path)


def _git_success(root: Path, *args: str) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _git_worktree_records(root: Path) -> list[dict[str, str]]:
    text = _git_stdout(root, "worktree", "list", "--porcelain")
    if not text:
        return []
    records: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        if not line.strip():
            if current:
                records.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        records.append(current)
    return records


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _relative_or_absolute(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
