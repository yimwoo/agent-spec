from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import load_data, utc_now_iso, write_data
from .model_review import classify_severity, request_model_review
from .policy import PolicyVerdict
from .task import list_task_context_packs


DECISIONS = {"auto_continue", "pause_for_human", "halt", "complete"}
SEVERITIES = {"minor", "high"}


@dataclass(frozen=True)
class ReviewVerdict:
    decision: str
    confidence: str
    reason: str
    message_to_executor: str | None
    requires_human: bool
    policy_flags: list[str]
    evidence_refs: list[str]
    # R-143: severity is populated when decision == pause_for_human.
    # Stays None for other decisions.
    severity: str | None = None
    # The default value the reviewer is willing to assume for a minor pause.
    # For minor severity, this is recorded in the open-question entry and
    # threaded into the next executor handoff. None when not applicable.
    proposed_default: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reason": self.reason,
            "message_to_executor": self.message_to_executor,
            "requires_human": self.requires_human,
            "policy_flags": self.policy_flags,
            "evidence_refs": self.evidence_refs,
            "severity": self.severity,
            "proposed_default": self.proposed_default,
        }


def classify_executor_output(
    *,
    executor_output: str,
    active_context_pack: str,
    policy_verdict: PolicyVerdict,
    test_status: str = "not_run",
) -> ReviewVerdict:
    if policy_verdict.decision == "halt":
        return ReviewVerdict(
            decision="halt",
            confidence="high",
            reason=policy_verdict.reason,
            message_to_executor=None,
            requires_human=True,
            policy_flags=policy_verdict.flags,
            evidence_refs=[active_context_pack],
        )

    text = executor_output.strip()
    task_id = _task_id_from_context_pack(active_context_pack)

    if _looks_complete(text) and test_status == "passed":
        return ReviewVerdict(
            decision="complete",
            confidence="medium",
            reason="Executor reports completion and verification passed.",
            message_to_executor=None,
            requires_human=False,
            policy_flags=[],
            evidence_refs=[active_context_pack],
        )

    if _asks_to_choose_task(text):
        if task_id and _mentions_task(text, task_id):
            return ReviewVerdict(
                decision="auto_continue",
                confidence="high",
                reason=f"{task_id} is already the active context pack; proceeding does not select a new task or expand scope.",
                message_to_executor=(
                    f"Continue with {task_id}. Use the {task_id} context pack as the active scope, "
                    "work only inside its allowed paths, and run its listed verification before reporting completion."
                ),
                requires_human=False,
                policy_flags=[],
                evidence_refs=[active_context_pack],
            )
        return ReviewVerdict(
            decision="pause_for_human",
            confidence="high",
            reason="Executor asked the human to choose among tasks, and no active task match was found.",
            message_to_executor=None,
            requires_human=True,
            policy_flags=[],
            evidence_refs=[active_context_pack],
        )

    if _asks_for_approval(text):
        return ReviewVerdict(
            decision="pause_for_human",
            confidence="medium",
            reason="Executor asked for approval that is not a low-risk continuation prompt.",
            message_to_executor=None,
            requires_human=True,
            policy_flags=[],
            evidence_refs=[active_context_pack],
            severity=classify_severity(text),
        )

    return ReviewVerdict(
        decision="pause_for_human",
        confidence="medium",
        reason="No deterministic auto-continue rule matched the executor output.",
        message_to_executor=None,
        requires_human=True,
        policy_flags=[],
        evidence_refs=[active_context_pack],
        severity=classify_severity(text),
    )


def review_executor_output(
    *,
    executor_output: str,
    active_context_pack: str,
    policy_verdict: PolicyVerdict,
    test_status: str = "not_run",
    reviewer_mode: str = "deterministic",
    reviewer_profile: dict[str, Any] | None = None,
) -> ReviewVerdict:
    deterministic = classify_executor_output(
        executor_output=executor_output,
        active_context_pack=active_context_pack,
        policy_verdict=policy_verdict,
        test_status=test_status,
    )
    if reviewer_mode == "deterministic" or deterministic.decision != "pause_for_human":
        return deterministic

    profile = reviewer_profile or {}
    try:
        model_payload = request_model_review(
            profile=profile,
            executor_output=executor_output,
            active_context_pack=active_context_pack,
            deterministic_reason=deterministic.reason,
            test_status=test_status,
        )
    except ValueError as exc:
        return _deterministic_with_model_note(deterministic, f"Model reviewer response was invalid: {exc}")

    if model_payload is None:
        if reviewer_mode == "model":
            return _deterministic_with_model_note(deterministic, "Model reviewer was unavailable; fell back to deterministic pause.")
        return deterministic

    return _sanitize_model_verdict(
        payload=model_payload,
        deterministic=deterministic,
        active_context_pack=active_context_pack,
        test_status=test_status,
    )


def _sanitize_model_verdict(
    *,
    payload: dict[str, Any],
    deterministic: ReviewVerdict,
    active_context_pack: str,
    test_status: str,
) -> ReviewVerdict:
    decision = str(payload["decision"])
    if decision == "complete" and test_status != "passed":
        return _deterministic_with_model_note(
            deterministic,
            "Model reviewer requested completion, but verification has not passed.",
        )

    message = payload.get("message_to_executor")
    if decision == "auto_continue" and not message:
        task_id = _task_id_from_context_pack(active_context_pack)
        suffix = f" with {task_id}" if task_id else ""
        message = f"Continue{suffix}. Stay inside the active context pack and its allowed paths."

    return ReviewVerdict(
        decision=decision,
        confidence=str(payload.get("confidence", "medium")),
        reason=f"Model reviewer: {payload.get('reason', 'structured verdict')}",
        message_to_executor=message if isinstance(message, str) else None,
        requires_human=decision in {"pause_for_human", "halt"},
        policy_flags=[],
        evidence_refs=[active_context_pack, "model_reviewer"],
    )


def _deterministic_with_model_note(verdict: ReviewVerdict, note: str) -> ReviewVerdict:
    return ReviewVerdict(
        decision=verdict.decision,
        confidence=verdict.confidence,
        reason=f"{verdict.reason} {note}",
        message_to_executor=verdict.message_to_executor,
        requires_human=verdict.requires_human,
        policy_flags=[*verdict.policy_flags, "model_review_unavailable"],
        evidence_refs=verdict.evidence_refs,
    )


def _task_id_from_context_pack(context_pack: str) -> str | None:
    match = re.match(r"^(T-\d{3,})", Path(context_pack).name)
    return match.group(1) if match else None


def _mentions_task(text: str, task_id: str) -> bool:
    return re.search(rf"\b{re.escape(task_id)}\b", text, flags=re.IGNORECASE) is not None


def _asks_to_choose_task(text: str) -> bool:
    lowered = text.lower()
    return "pick one" in lowered or "which task" in lowered or "one of the others" in lowered


def _asks_for_approval(text: str) -> bool:
    lowered = text.lower()
    return "want me to" in lowered or "should i" in lowered or "approve" in lowered


def _looks_complete(text: str) -> bool:
    lowered = text.lower()
    return "complete" in lowered or "done" in lowered or "acceptance criteria" in lowered


# R-144 / ADR-0005: quality_reviewer is the second-opinion signoff
# autonomous mode requires before emitting `complete`. Stricter than
# `_looks_complete` on purpose — disagreement is the whole point.
_QUALITY_EVIDENCE_VERBS = ("met", "covered", "passed", "verified", "satisfied")


def quality_reviewer_signoff(
    executor_output: str,
    test_status: str,
    *,
    profile: dict[str, Any] | None = None,
    reviewer_mode: str = "deterministic",
) -> tuple[str, str]:
    """Return ('approve', reason) or ('reject', reason).

    Deterministic rule: quality requires `test_status == "passed"` AND
    explicit acceptance-criteria evidence in the executor output (the
    word "acceptance" plus either "criteria" or one of the evidence
    verbs above). Naked "Done." passes continuation_reviewer but does
    not satisfy quality.

    The model-backed branch is reserved for a future enhancement; for
    R-144's MVP it falls through to the deterministic check.
    """
    if test_status != "passed":
        return (
            "reject",
            f"Quality reviewer requires test_status=passed; got {test_status!r}.",
        )

    lowered = executor_output.lower()
    has_acceptance = "acceptance" in lowered
    has_criteria = "criteria" in lowered or "criterion" in lowered
    has_evidence_verb = any(verb in lowered for verb in _QUALITY_EVIDENCE_VERBS)
    if has_acceptance and (has_criteria or has_evidence_verb):
        return (
            "approve",
            "Tests pass and the executor output references acceptance evidence.",
        )
    return (
        "reject",
        "Quality reviewer requires explicit acceptance-criteria evidence in the executor output.",
    )


CODE_REVIEW_SCHEMA = "agentspec.code_review.v0"
ALLOWED_CODE_REVIEW_VERDICTS = frozenset(
    {"ready", "ready-with-warnings", "not-ready"}
)
PASSING_CODE_REVIEW_VERDICTS = frozenset({"ready", "ready-with-warnings"})


def record_code_review(
    root: Path,
    *,
    task_selector: str,
    verdict: str,
    summary: str,
    reviewer: str = "human",
    range_ref: str = "worktree",
) -> dict[str, Any]:
    root = root.resolve()
    if verdict not in ALLOWED_CODE_REVIEW_VERDICTS:
        allowed = ", ".join(sorted(ALLOWED_CODE_REVIEW_VERDICTS))
        raise ValueError(f"Invalid code review verdict {verdict!r}; expected one of: {allowed}.")
    if not summary.strip():
        raise ValueError("Code review summary is required.")

    context_pack = _resolve_review_context_pack(root, task_selector)
    review_id = _next_review_id(root)
    record = {
        "schema": CODE_REVIEW_SCHEMA,
        "id": review_id,
        "task": {
            "selector": task_selector,
            "context_pack": context_pack,
        },
        "verdict": verdict,
        "summary": summary,
        "reviewer": reviewer,
        "range": range_ref,
        "created_at": utc_now_iso(),
    }
    write_data(_review_path(root, review_id), record)
    return record


def load_code_review(root: Path, review_id: str) -> dict[str, Any]:
    path = _review_path(root.resolve(), review_id)
    record = load_data(path)
    if not isinstance(record, dict):
        raise FileNotFoundError(f"Code review not found: {review_id}")
    if record.get("schema") != CODE_REVIEW_SCHEMA:
        raise ValueError(f"Invalid code review schema in {path}.")
    if record.get("verdict") not in ALLOWED_CODE_REVIEW_VERDICTS:
        raise ValueError(f"Invalid code review verdict in {path}: {record.get('verdict')!r}.")
    return record


def validate_completion_review(
    root: Path,
    review_id: str,
    *,
    context_pack: str,
) -> dict[str, Any]:
    root = root.resolve()
    record = load_code_review(root, review_id)
    verdict = str(record.get("verdict"))
    if verdict not in PASSING_CODE_REVIEW_VERDICTS:
        raise ValueError(f"Code review {record.get('id')} is {verdict}; task completion is blocked.")

    task = record.get("task")
    reviewed_context_pack = task.get("context_pack") if isinstance(task, dict) else None
    if reviewed_context_pack != context_pack:
        raise ValueError(
            f"Code review {record.get('id')} belongs to {reviewed_context_pack}, "
            f"not {context_pack}."
        )
    return code_review_summary(root, record)


def code_review_summary(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    review_id = str(record.get("id"))
    return {
        "id": review_id,
        "verdict": record.get("verdict"),
        "summary": record.get("summary"),
        "reviewer": record.get("reviewer"),
        "range": record.get("range"),
        "path": _relative_or_absolute(root.resolve(), _review_path(root.resolve(), review_id)),
    }


def _resolve_review_context_pack(root: Path, selector: str) -> str:
    records = list_task_context_packs(root)

    by_id = [record for record in records if record.get("id") == selector]
    if len(by_id) == 1:
        return str(by_id[0]["path"])
    if len(by_id) > 1:
        raise ValueError(f"Task selector is ambiguous: {selector}")

    candidate = Path(selector)
    candidate_path = candidate if candidate.is_absolute() else root / candidate
    if candidate_path.exists():
        try:
            rel = str(candidate_path.relative_to(root))
        except ValueError:
            rel = str(candidate_path)
        if any(record.get("path") == rel for record in records):
            return rel

    raise FileNotFoundError(f"Task not found: {selector}")


def _next_review_id(root: Path) -> str:
    review_dir = root / "agent" / "reviews"
    highest = 0
    for path in review_dir.glob("REVIEW-*.yml"):
        stem = path.stem
        if stem.startswith("REVIEW-") and stem.split("-", 1)[1].isdigit():
            highest = max(highest, int(stem.split("-", 1)[1]))
    return f"REVIEW-{highest + 1:04d}"


def _review_path(root: Path, review_id: str) -> Path:
    candidate = Path(review_id)
    if candidate.is_absolute():
        return candidate
    if candidate.suffix == ".yml":
        if len(candidate.parts) > 1:
            return root / candidate
        return root / "agent" / "reviews" / candidate.name
    if len(candidate.parts) > 1:
        return root / candidate
    return root / "agent" / "reviews" / f"{review_id}.yml"


def _relative_or_absolute(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
