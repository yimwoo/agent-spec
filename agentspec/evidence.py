"""Public evidence projections for release and task-completion records."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import load_data, utc_now_iso, write_data
from .paths import is_untracked_git_ignored


PUBLIC_RELEASE_EVIDENCE_SCHEMA = "agentspec.release_evidence.v0"
PUBLIC_RELEASE_EVIDENCE_PATH = Path("docs/release/evidence.yml")
ALLOWED_PUBLIC_VERIFICATION_STATUSES = frozenset({"failed", "not_run", "passed"})
ALLOWED_PUBLIC_REVIEW_VERDICTS = frozenset({"not-ready", "ready", "ready-with-warnings"})
PASSING_PUBLIC_REVIEW_VERDICTS = frozenset({"ready", "ready-with-warnings"})


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

    entry = _completion_entry(context_pack, completion)
    entry = _merge_review_history(tasks.get(context_pack), entry)
    tasks[context_pack] = entry
    payload = {
        "schema": PUBLIC_RELEASE_EVIDENCE_SCHEMA,
        "updated_at": entry["updated_at"],
        "tasks": {key: tasks[key] for key in sorted(tasks)},
    }
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
    write_data(root / PUBLIC_RELEASE_EVIDENCE_PATH, payload)
    return summary


def public_release_evidence_path() -> str:
    """Return the repo-relative public release evidence path."""

    return PUBLIC_RELEASE_EVIDENCE_PATH.as_posix()


def _completion_entry(context_pack: str, completion: dict[str, Any]) -> dict[str, Any]:
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
    return True


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
