"""Pure transition helpers for AgentSpec supervised runs.

This module owns small, deterministic decisions that are shared across run
resume, prompt, summary, and reuse flows. It intentionally avoids filesystem
I/O so these rules stay easy to read and test in isolation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, TypedDict


RunDecision = Literal["auto_continue", "pause_for_human", "halt", "complete"]
RunStatus = Literal["started", "running", "paused", "complete", "halted", "aborted"]
NextRunAction = Literal["continue_executor", "await_human", "complete", "stop"]

TERMINAL_RUN_STATUSES: frozenset[RunStatus] = frozenset({"halted", "complete", "aborted"})
REUSABLE_RUN_STATUSES: frozenset[RunStatus] = frozenset({"started", "running"})
MODEL_REVIEW_UNAVAILABLE_FLAG = "model_review_unavailable"


class RunTransitionState(TypedDict, total=False):
    """Run state fields needed for transition decisions.

    Attributes:
        mode: Run execution mode, such as `supervised`, `autonomous`, or
            `research`.
        infrastructure_blocker: Optional infrastructure failure metadata from
            a terminal autonomous/research run.
    """

    mode: str
    infrastructure_blocker: dict[str, object]


class RunTransitionEvent(TypedDict, total=False):
    """Run event fields needed for transition decisions.

    Attributes:
        kind: Event type from the run event log.
        decision: Reviewer decision recorded on verdict events.
        reason: Human-readable reason recorded by the controller or reviewer.
    """

    kind: str
    decision: str
    reason: str


class ReviewWithPolicyFlags(Protocol):
    """Minimal review object contract used by transition helpers.

    Attributes:
        policy_flags: Structured policy flags emitted with a review verdict.
    """

    policy_flags: Sequence[str]


def status_for_decision(decision: str) -> RunStatus:
    """Map a reviewer decision to the persisted run status.

    Args:
        decision: Reviewer decision from the continuation or quality reviewer.

    Returns:
        The run status written to `state.yml`. Unknown decisions conservatively
        map to `paused` so execution does not advance silently.
    """
    return {
        "auto_continue": "running",
        "pause_for_human": "paused",
        "halt": "halted",
        "complete": "complete",
    }.get(decision, "paused")


def next_action_for_status(status: str) -> NextRunAction:
    """Map a run status to the controller's next action.

    Args:
        status: Current run status from persisted state.

    Returns:
        The next controller action. Unknown statuses default to `await_human`
        because the safe fallback is to stop and ask for review.
    """
    return {
        "started": "continue_executor",
        "running": "continue_executor",
        "paused": "await_human",
        "complete": "complete",
        "halted": "stop",
        "aborted": "stop",
    }.get(status, "await_human")


def halted_run_accepts_corrected_evidence(
    state: RunTransitionState,
    events: Sequence[RunTransitionEvent],
) -> bool:
    """Return whether a halted autonomous/research run can be reopened.

    Args:
        state: Persisted run state with at least the run mode and optional
            infrastructure blocker metadata.
        events: Run events in chronological order.

    Returns:
        True when the halt came from reviewer infrastructure or a quality
        review rejection that accepts corrected evidence. False for supervised
        runs, ordinary reviewer halts, and ambiguous terminal halt history.
    """
    if state.get("mode") not in {"autonomous", "research"}:
        return False

    for event in reversed(events):
        kind = event.get("kind")
        if kind == "autonomous_infrastructure_block":
            return True
        if kind == "autonomous_pause_to_dcr" and is_quality_review_halt_event(event):
            return True
        if kind == "reviewer_verdict" and event.get("decision") == "halt":
            return False
    return isinstance(state.get("infrastructure_blocker"), dict)


def is_quality_review_halt_event(event: RunTransitionEvent) -> bool:
    """Return whether an autonomous pause-to-DCR event came from quality review.

    Args:
        event: Event payload from `events.jsonl`.

    Returns:
        True when the event reason matches the quality-review rejection marker.
    """
    reason = event.get("reason")
    return (
        isinstance(reason, str)
        and reason.startswith("Quality reviewer rejected autonomous-mode complete:")
    )


def is_model_review_unavailable_pause(review: ReviewWithPolicyFlags) -> bool:
    """Return whether a pause was caused by model-review infrastructure.

    Args:
        review: Review verdict-like object with policy flags.

    Returns:
        True when the model-review unavailable policy flag is present.
    """
    flags = getattr(review, "policy_flags", [])
    return MODEL_REVIEW_UNAVAILABLE_FLAG in flags
