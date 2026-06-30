"""Public evidence projections for release and task-completion records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import load_data, utc_now_iso, write_data
from .paths import is_untracked_git_ignored


PUBLIC_RELEASE_EVIDENCE_SCHEMA = "agentspec.release_evidence.v0"
PUBLIC_RELEASE_EVIDENCE_PATH = Path("docs/release/evidence.yml")
PRIVATE_TASK_LEDGER_PATH = Path("agent/task-ledger.yml")
ALLOWED_PUBLIC_VERIFICATION_STATUSES = frozenset({"failed", "not_run", "passed"})
ALLOWED_PUBLIC_REVIEW_VERDICTS = frozenset({"not-ready", "ready", "ready-with-warnings"})
PASSING_PUBLIC_REVIEW_VERDICTS = frozenset({"ready", "ready-with-warnings"})
ALLOWED_PUBLIC_TASK_STATES = frozenset({"blocked", "halted", "in_progress", "paused"})


def should_write_public_release_evidence(root: Path) -> bool:
    """Return whether task completion should mirror evidence into public docs.

    AgentSpec projects may keep `agent/` runtime state private or ignored. When
    the task ledger is ignored, a small public evidence projection preserves the
    completion, verification, and review signal in a trackable path. Existing
    public evidence files continue to be updated even if ignore policy changes.
    """

    root = root.resolve()
    evidence_path = root / PUBLIC_RELEASE_EVIDENCE_PATH
    if evidence_path.exists():
        return True
    return is_untracked_git_ignored(root, root / "agent" / "task-ledger.yml")


def write_public_release_evidence(root: Path, completion: dict[str, Any]) -> dict[str, Any] | None:
    """Mirror one completion into the public release evidence artifact.

    Args:
        root: AgentSpec project root.
        completion: Completion/run state containing at least `context_pack`.

    Returns:
        The written task evidence entry, or `None` when public evidence mirroring
        is not enabled for the project.

    Raises:
        ValueError: If mirroring is enabled but the completion lacks a context
            pack identifier.
    """

    root = root.resolve()
    if not should_write_public_release_evidence(root):
        return None

    context_pack = str(completion.get("context_pack") or "")
    if not context_pack:
        raise ValueError("public release evidence requires completion.context_pack.")

    path = root / PUBLIC_RELEASE_EVIDENCE_PATH
    tasks = load_public_release_tasks(root)
    task_states = load_public_task_states(root)

    entry = _completion_entry(root, context_pack, completion)
    entry = _merge_review_history(tasks.get(context_pack), entry)
    tasks[context_pack] = entry
    task_states.pop(context_pack, None)
    payload = {
        "schema": PUBLIC_RELEASE_EVIDENCE_SCHEMA,
        "updated_at": entry["updated_at"],
        "tasks": {key: tasks[key] for key in sorted(tasks)},
    }
    if task_states:
        payload["task_states"] = {key: task_states[key] for key in sorted(task_states)}
    write_data(path, payload)
    return entry


def load_public_release_tasks(root: Path) -> dict[str, dict[str, Any]]:
    """Load validated task completion evidence from the public artifact.

    Unsupported schemas and malformed task records are ignored so advisory
    maturity and roadmap projections cannot treat hand-written placeholders as
    verified release evidence.
    """

    data = load_data(root.resolve() / PUBLIC_RELEASE_EVIDENCE_PATH, {})
    if not isinstance(data, dict) or data.get("schema") != PUBLIC_RELEASE_EVIDENCE_SCHEMA:
        return {}
    tasks = data.get("tasks")
    if not isinstance(tasks, dict):
        return {}
    validated: dict[str, dict[str, Any]] = {}
    for context_pack, entry in tasks.items():
        if _valid_public_task_entry(context_pack, entry):
            validated[context_pack] = entry
    return validated


def load_public_task_states(root: Path) -> dict[str, dict[str, Any]]:
    """Load validated non-terminal task states from public evidence."""

    data = load_data(root.resolve() / PUBLIC_RELEASE_EVIDENCE_PATH, {})
    if not isinstance(data, dict) or data.get("schema") != PUBLIC_RELEASE_EVIDENCE_SCHEMA:
        return {}
    task_states = data.get("task_states")
    if not isinstance(task_states, dict):
        return {}
    validated: dict[str, dict[str, Any]] = {}
    for context_pack, entry in task_states.items():
        if _valid_public_task_state_entry(context_pack, entry):
            validated[context_pack] = entry
    return validated


def write_public_task_state(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Persist one non-terminal task state in the public evidence projection.

    Args:
        root: AgentSpec project root.
        state: Normalized task-state record containing context, status, and
            recovery reason.

    Returns:
        The validated public task-state entry.

    Raises:
        ValueError: If the state is malformed or attempts to reopen a task with
            public completion evidence.
    """

    root = root.resolve()
    context_pack = state.get("context_pack")
    if not isinstance(context_pack, str) or not context_pack:
        raise ValueError("public task state requires context_pack.")
    entry = dict(state)
    if not _valid_public_task_state_entry(context_pack, entry):
        allowed = ", ".join(sorted(ALLOWED_PUBLIC_TASK_STATES))
        raise ValueError(f"public task state must be valid and use one of: {allowed}.")

    tasks = load_public_release_tasks(root)
    if context_pack in tasks:
        raise ValueError("Cannot publish a non-terminal state for a completed task.")
    task_states = load_public_task_states(root)
    task_states[context_pack] = entry
    payload = {
        "schema": PUBLIC_RELEASE_EVIDENCE_SCHEMA,
        "updated_at": entry["updated_at"],
        "tasks": {key: tasks[key] for key in sorted(tasks)},
        "task_states": {key: task_states[key] for key in sorted(task_states)},
    }
    write_data(root / PUBLIC_RELEASE_EVIDENCE_PATH, payload)
    return entry


def load_task_evidence(
    root: Path,
    *,
    include_untracked_gitignored: bool = False,
) -> dict[str, dict[str, Any]]:
    """Load the authoritative merged task-evidence projection.

    Args:
        root: AgentSpec project root.
        include_untracked_gitignored: Include private ledger residue that Git
            ignores. This diagnostic-only option defaults to ``False`` so
            clean-checkout and active-worktree projections agree.

    Returns:
        Task records keyed by context-pack path. Valid private ledger fields
        take precedence over public release fields, except that a newer public
        review remains authoritative for review metadata.
    """

    root = root.resolve()
    public_states = {
        context_pack: {
            **entry,
            "_evidence_sources": [PUBLIC_RELEASE_EVIDENCE_PATH.as_posix()],
        }
        for context_pack, entry in load_public_task_states(root).items()
    }
    public_tasks = {
        context_pack: {
            **entry,
            "_evidence_sources": [PUBLIC_RELEASE_EVIDENCE_PATH.as_posix()],
        }
        for context_pack, entry in load_public_release_tasks(root).items()
    }
    public_evidence = {**public_states, **public_tasks}
    private_tasks = _load_private_task_evidence(
        root,
        include_untracked_gitignored=include_untracked_gitignored,
    )
    return _merge_task_evidence(public_evidence, private_tasks)


def task_evidence_sources(entry: dict[str, Any]) -> list[str]:
    """Return stable repository paths that contributed to a task record."""

    sources = entry.get("_evidence_sources")
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, str) and source]


def write_public_release_review(root: Path, review: dict[str, Any]) -> dict[str, Any] | None:
    """Refresh an existing public completion entry with a later code review.

    Reviews are projected only after a task has public completion evidence.
    The latest review is stored in ``code_review`` while ``reviews`` preserves
    the ordered, deduplicated review history.

    Args:
        root: AgentSpec project root.
        review: Persisted ``agentspec.code_review.v0`` record.

    Returns:
        The projected review summary, or ``None`` when the task does not yet
        have public completion evidence.
    """

    root = root.resolve()
    task = review.get("task")
    context_pack = task.get("context_pack") if isinstance(task, dict) else None
    if not isinstance(context_pack, str) or not context_pack:
        return None

    tasks = load_public_release_tasks(root)
    task_states = load_public_task_states(root)
    existing = tasks.get(context_pack)
    if existing is None:
        return None

    summary = _review_summary(review)
    if not _valid_review_summary(summary):
        return None

    history = _review_history(existing)
    history = _append_review(history, summary)
    updated_at = str(review.get("created_at") or utc_now_iso())
    tasks[context_pack] = {
        **existing,
        "code_review": summary,
        "reviews": history,
        "review_updated_at": updated_at,
    }
    payload = {
        "schema": PUBLIC_RELEASE_EVIDENCE_SCHEMA,
        "updated_at": updated_at,
        "tasks": {key: tasks[key] for key in sorted(tasks)},
    }
    if task_states:
        payload["task_states"] = {key: task_states[key] for key in sorted(task_states)}
    write_data(root / PUBLIC_RELEASE_EVIDENCE_PATH, payload)
    return summary


def public_release_evidence_path() -> str:
    """Return the repo-relative public release evidence path."""

    return PUBLIC_RELEASE_EVIDENCE_PATH.as_posix()


def _completion_entry(
    root: Path,
    context_pack: str,
    completion: dict[str, Any],
) -> dict[str, Any]:
    raw_verification = completion.get("verification")
    verification: dict[str, Any] = raw_verification if isinstance(raw_verification, dict) else {}
    raw_code_review = completion.get("code_review")
    code_review: dict[str, Any] | None = raw_code_review if isinstance(raw_code_review, dict) else None
    entry: dict[str, Any] = {
        "task_id": _task_id_from_context_pack(context_pack),
        "context_pack": context_pack,
        "status": str(completion.get("status") or "complete"),
        "run_id": str(completion.get("run_id") or "-"),
        "verification": {"status": str(verification.get("status") or completion.get("test_status") or "not_run")},
        "updated_at": str(completion.get("updated_at") or utc_now_iso()),
    }
    requirements = _completion_requirement_ids(root, context_pack, completion)
    if requirements:
        entry["requirements"] = requirements
    reason = completion.get("completion_reason") or completion.get("reason")
    if reason:
        entry["completion_reason"] = str(reason)
    if code_review is not None:
        entry["code_review"] = _review_summary(code_review)
    return entry


def _review_summary(code_review: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key in ("id", "verdict", "summary", "reviewer", "range", "path", "created_at"):
        value = code_review.get(key)
        if value is not None:
            summary[key] = value
    review_id = summary.get("id")
    if "path" not in summary and isinstance(review_id, str) and review_id:
        summary["path"] = f"agent/reviews/{review_id}.yml"
    return summary


def _merge_review_history(
    existing: dict[str, Any] | None,
    entry: dict[str, Any],
) -> dict[str, Any]:
    history = _review_history(existing or {})
    current = entry.get("code_review")
    if isinstance(current, dict) and _valid_review_summary(current):
        history = _append_review(history, current)
    if history:
        entry["reviews"] = history
    return entry


def _review_history(entry: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = entry.get("reviews")
    if isinstance(reviews, list):
        return [review for review in reviews if isinstance(review, dict) and _valid_review_summary(review)]
    current = entry.get("code_review")
    if isinstance(current, dict) and _valid_review_summary(current):
        return [current]
    return []


def _append_review(
    history: list[dict[str, Any]],
    review: dict[str, Any],
) -> list[dict[str, Any]]:
    review_id = review.get("id")
    retained = [item for item in history if item.get("id") != review_id]
    return [*retained, review]


def _valid_public_task_entry(context_pack: Any, entry: Any) -> bool:
    if not isinstance(context_pack, str) or not isinstance(entry, dict):
        return False
    task_id = _task_id_from_context_pack(context_pack)
    if task_id == "-" or entry.get("task_id") != task_id:
        return False
    if entry.get("context_pack") != context_pack or entry.get("status") != "complete":
        return False
    if not _nonempty_string(entry.get("run_id")) or not _nonempty_string(entry.get("updated_at")):
        return False
    verification = entry.get("verification")
    if not isinstance(verification, dict) or verification.get("status") not in ALLOWED_PUBLIC_VERIFICATION_STATUSES:
        return False
    current = entry.get("code_review")
    if current is not None and not _valid_review_summary(current):
        return False
    reviews = entry.get("reviews")
    if reviews is not None:
        if not isinstance(reviews, list) or not all(_valid_review_summary(review) for review in reviews):
            return False
        if current is not None and (not reviews or reviews[-1].get("id") != current.get("id")):
            return False
    requirements = entry.get("requirements")
    if requirements is not None and (
        not isinstance(requirements, list)
        or not all(
            isinstance(value, str) and re.fullmatch(r"R-\d{3,}", value)
            for value in requirements
        )
    ):
        return False
    return True


def _valid_public_task_state_entry(context_pack: Any, entry: Any) -> bool:
    if not isinstance(context_pack, str) or not isinstance(entry, dict):
        return False
    task_id = _task_id_from_context_pack(context_pack)
    if task_id == "-" or entry.get("task_id") != task_id:
        return False
    if entry.get("context_pack") != context_pack:
        return False
    if entry.get("status") not in ALLOWED_PUBLIC_TASK_STATES:
        return False
    if not _nonempty_string(entry.get("reason")) or not _nonempty_string(entry.get("updated_at")):
        return False
    verification = entry.get("verification")
    if not isinstance(verification, dict) or verification.get("status") not in ALLOWED_PUBLIC_VERIFICATION_STATUSES:
        return False
    title = entry.get("title")
    if title is not None and not _nonempty_string(title):
        return False
    task_type = entry.get("type")
    if task_type is not None and not _nonempty_string(task_type):
        return False
    requirements = entry.get("requirements")
    if requirements is not None and (
        not isinstance(requirements, list)
        or not all(isinstance(value, str) and re.fullmatch(r"R-\d{3,}", value) for value in requirements)
    ):
        return False
    return True


def _load_private_task_evidence(
    root: Path,
    *,
    include_untracked_gitignored: bool,
) -> dict[str, dict[str, Any]]:
    path = root / PRIVATE_TASK_LEDGER_PATH
    if not include_untracked_gitignored and is_untracked_git_ignored(root, path):
        return {}
    data = load_data(path, {})
    if not isinstance(data, dict):
        return {}
    tasks = data.get("tasks")
    if not isinstance(tasks, dict):
        return {}

    validated: dict[str, dict[str, Any]] = {}
    for context_pack, entry in tasks.items():
        if not isinstance(context_pack, str) or not isinstance(entry, dict):
            continue
        status = entry.get("status")
        if not isinstance(status, str) or not status:
            continue
        validated[context_pack] = {
            **entry,
            "task_id": _task_id_from_context_pack(context_pack),
            "context_pack": context_pack,
            "_evidence_sources": [PRIVATE_TASK_LEDGER_PATH.as_posix()],
        }
    return validated


def _merge_task_evidence(
    public_tasks: dict[str, dict[str, Any]],
    private_tasks: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    merged = {context_pack: dict(entry) for context_pack, entry in public_tasks.items()}
    for context_pack, private_entry in private_tasks.items():
        public_entry = public_tasks.get(context_pack)
        if public_entry is None:
            merged[context_pack] = dict(private_entry)
            continue
        combined = {**public_entry, **private_entry}
        if _public_review_is_newer(public_entry, private_entry):
            for key in ("code_review", "reviews", "review_updated_at"):
                if key in public_entry:
                    combined[key] = public_entry[key]
        combined["_evidence_sources"] = sorted(
            set(task_evidence_sources(public_entry) + task_evidence_sources(private_entry))
        )
        merged[context_pack] = combined
    return merged


def _public_review_is_newer(
    public_entry: dict[str, Any],
    private_entry: dict[str, Any],
) -> bool:
    public_review = public_entry.get("code_review")
    if not isinstance(public_review, dict):
        return False
    public_updated = str(public_entry.get("review_updated_at") or public_entry.get("updated_at") or "")
    private_updated = str(private_entry.get("review_updated_at") or private_entry.get("updated_at") or "")
    return bool(public_updated) and public_updated > private_updated


def _completion_requirement_ids(
    root: Path,
    context_pack: str,
    completion: dict[str, Any],
) -> list[str]:
    raw = completion.get("requirements")
    identifiers: list[str] = []
    if isinstance(raw, list):
        for value in raw:
            candidate = value.get("id") if isinstance(value, dict) else value
            if isinstance(candidate, str) and re.fullmatch(r"R-\d{3,}", candidate):
                identifiers.append(candidate)
    if identifiers:
        return sorted(set(identifiers))

    path = root / context_pack
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    section = _markdown_section(text, "Requirements")
    return sorted(set(re.findall(r"\bR-\d{3,}\b", section)))


def _markdown_section(text: str, heading: str) -> str:
    lines = text.splitlines()
    collected: list[str] = []
    in_section = False
    for line in lines:
        if line.strip().lower() == f"## {heading}".lower():
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section:
            collected.append(line)
    return "\n".join(collected)


def _valid_review_summary(review: Any) -> bool:
    if not isinstance(review, dict):
        return False
    review_id = review.get("id")
    verdict = review.get("verdict")
    return (
        isinstance(review_id, str)
        and re.fullmatch(r"REVIEW-\d+", review_id) is not None
        and verdict in ALLOWED_PUBLIC_REVIEW_VERDICTS
    )


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value != "-"


def _task_id_from_context_pack(context_pack: str) -> str:
    name = Path(context_pack).name
    match = re.match(r"^(T-\d+)", name)
    return match.group(1) if match else "-"
