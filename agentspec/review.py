from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .model_review import request_model_review
from .policy import PolicyVerdict


DECISIONS = {"auto_continue", "pause_for_human", "halt", "complete"}


@dataclass(frozen=True)
class ReviewVerdict:
    decision: str
    confidence: str
    reason: str
    message_to_executor: str | None
    requires_human: bool
    policy_flags: list[str]
    evidence_refs: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision,
            "confidence": self.confidence,
            "reason": self.reason,
            "message_to_executor": self.message_to_executor,
            "requires_human": self.requires_human,
            "policy_flags": self.policy_flags,
            "evidence_refs": self.evidence_refs,
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
        )

    return ReviewVerdict(
        decision="pause_for_human",
        confidence="medium",
        reason="No deterministic auto-continue rule matched the executor output.",
        message_to_executor=None,
        requires_human=True,
        policy_flags=[],
        evidence_refs=[active_context_pack],
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
