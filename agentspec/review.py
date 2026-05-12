from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .io import load_data, utc_now_iso, write_data
from .model_review import classify_severity, request_model_review, request_quality_review
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
    acceptance_evidence: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
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

    if _is_research_context_pack(active_context_pack) and acceptance_evidence is not None and test_status == "passed":
        return ReviewVerdict(
            decision="complete",
            confidence="high",
            reason="Research acceptance evidence is valid and verification passed.",
            message_to_executor=None,
            requires_human=False,
            policy_flags=[],
            evidence_refs=[active_context_pack, "acceptance_evidence"],
        )

    if (
        (_looks_complete(text) or _has_scoped_completion_evidence(text))
        and test_status == "passed"
    ):
        return ReviewVerdict(
            decision="complete",
            confidence="medium",
            reason="Executor reports completion and verification passed.",
            message_to_executor=None,
            requires_human=False,
            policy_flags=[],
            evidence_refs=[active_context_pack],
        )

    if test_status == "passed" and _has_passed_verification_evidence(evidence):
        return ReviewVerdict(
            decision="complete",
            confidence="medium",
            reason="Runner evidence records passed verification commands.",
            message_to_executor=None,
            requires_human=False,
            policy_flags=[],
            evidence_refs=[active_context_pack, "runner_evidence"],
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
    acceptance_evidence: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> ReviewVerdict:
    deterministic = classify_executor_output(
        executor_output=executor_output,
        active_context_pack=active_context_pack,
        policy_verdict=policy_verdict,
        test_status=test_status,
        acceptance_evidence=acceptance_evidence,
        evidence=evidence,
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
        if reviewer_mode in {"model", "auto"}:
            return _deterministic_with_model_note(
                deterministic,
                f"Model reviewer was unavailable in {reviewer_mode!r} mode; fell back to deterministic pause.",
            )
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


def _is_research_context_pack(context_pack: str) -> bool:
    return context_pack == "<research-mode>"


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
    acceptance_evidence: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Return ('approve', reason) or ('reject', reason).

    Deterministic rule: quality requires `test_status == "passed"` AND
    explicit acceptance-criteria evidence in the executor output (the
    word "acceptance" plus either "criteria" or one of the evidence
    verbs above). Naked "Done." passes continuation_reviewer but does
    not satisfy quality.

    In model-backed modes, the deterministic result becomes input to the
    configured test/eval reviewer profile. `auto` falls back to the
    deterministic result if the model is unavailable; `model` treats an
    unavailable or invalid model response as a rejection.
    """
    deterministic_decision, deterministic_reason = _deterministic_quality_reviewer_signoff(
        executor_output,
        test_status,
        acceptance_evidence=acceptance_evidence,
        evidence=evidence,
    )
    if test_status != "passed":
        return deterministic_decision, deterministic_reason

    if reviewer_mode in {"model", "auto"} and profile is not None:
        try:
            model_payload = request_quality_review(
                profile=profile,
                executor_output=executor_output,
                test_status=test_status,
                deterministic_reason=deterministic_reason,
                acceptance_evidence=acceptance_evidence,
            )
        except ValueError as exc:
            if reviewer_mode == "model":
                return "reject", f"Model quality reviewer response was invalid: {exc}"
            return (
                deterministic_decision,
                f"{deterministic_reason} Model quality reviewer response was invalid in 'auto' mode; "
                "fell back to deterministic quality review.",
            )
        if model_payload is not None:
            return (
                str(model_payload["decision"]),
                f"Model quality reviewer: {model_payload['reason']}",
            )
        if reviewer_mode == "model":
            return "reject", "Model quality reviewer was unavailable."
        if reviewer_mode == "auto":
            return (
                deterministic_decision,
                f"{deterministic_reason} Model quality reviewer was unavailable in 'auto' mode; "
                "fell back to deterministic quality review.",
            )

    return deterministic_decision, deterministic_reason


def _deterministic_quality_reviewer_signoff(
    executor_output: str,
    test_status: str,
    *,
    acceptance_evidence: dict[str, Any] | None = None,
    evidence: dict[str, Any] | None = None,
) -> tuple[str, str]:
    if test_status != "passed":
        return (
            "reject",
            f"Quality reviewer requires test_status=passed; got {test_status!r}.",
        )
    if acceptance_evidence is not None:
        return (
            "approve",
            "Research acceptance evidence is valid and verification passed.",
        )
    if _has_passed_verification_evidence(evidence):
        return (
            "approve",
            "Tests pass and runner evidence records passed verification commands.",
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
    if _has_scoped_completion_evidence(executor_output):
        return (
            "approve",
            "Tests pass and the executor output references scoped completion evidence.",
        )
    return (
        "reject",
        "Quality reviewer requires explicit acceptance-criteria evidence in the executor output.",
    )


def _has_passed_verification_evidence(evidence: dict[str, Any] | None) -> bool:
    if not isinstance(evidence, dict):
        return False
    commands = evidence.get("verification_commands")
    if not isinstance(commands, list) or not commands:
        return False
    statuses: list[str] = []
    for command in commands:
        if not isinstance(command, dict):
            return False
        status = command.get("status")
        if not isinstance(status, str):
            return False
        statuses.append(status)
    return bool(statuses) and all(status == "passed" for status in statuses)


def _has_scoped_completion_evidence(text: str) -> bool:
    lowered = text.lower()
    has_scope_ref = re.search(r"\b(?:R|T)-\d{3,}\b", text) is not None
    has_completion_verb = any(
        verb in lowered
        for verb in (
            "implemented",
            "finished",
            "completed",
            "fixed",
            "added",
            "updated",
            "shipped",
        )
    )
    has_verification = "passed" in lowered and any(
        marker in lowered
        for marker in ("test", "tests", "build", "verification", "pytest", "unittest", "npm ")
    )
    return has_scope_ref and has_completion_verb and has_verification


RESEARCH_ACCEPTANCE_EVIDENCE_SCHEMA = "agentspec.research_acceptance_evidence.v0"
_RESEARCH_EVIDENCE_PATH_PREFIXES: tuple[str, ...] = (
    "reports/dogfood/",
    "docs/change-requests/",
)
_RESEARCH_EVIDENCE_EXACT_PATHS: frozenset[str] = frozenset(
    {"docs/discovery/open-questions.yml"}
)


def research_acceptance_evidence_template() -> dict[str, Any]:
    return {
        "schema": RESEARCH_ACCEPTANCE_EVIDENCE_SCHEMA,
        "durable_artifacts": [],
        "allowed_path_confirmation": False,
        "verification_commands": [
            {"command": "git diff --check", "status": "<passed|failed>"},
            {"command": "aspec doctor", "status": "<passed|failed>"},
        ],
        "covered_requirements": [],
        "covered_questions": [],
        "source_checks": [],
        "no_task_context_pack_reason": "<required for research-only proposals>",
    }


def validate_research_acceptance_evidence(evidence: Any) -> dict[str, Any]:
    if not isinstance(evidence, dict):
        raise ValueError("acceptance_evidence must be a JSON object.")
    if evidence.get("schema") != RESEARCH_ACCEPTANCE_EVIDENCE_SCHEMA:
        raise ValueError(f"acceptance_evidence schema must be {RESEARCH_ACCEPTANCE_EVIDENCE_SCHEMA}.")

    durable_artifacts = _string_list(evidence.get("durable_artifacts"))
    if not durable_artifacts:
        raise ValueError("acceptance_evidence.durable_artifacts must be a non-empty list of paths.")
    disallowed = [path for path in durable_artifacts if not _is_research_evidence_path(path)]
    if disallowed:
        raise ValueError(
            "acceptance_evidence.durable_artifacts must stay inside the research write surface: "
            + ", ".join(disallowed)
        )

    if evidence.get("allowed_path_confirmation") is not True:
        raise ValueError("acceptance_evidence.allowed_path_confirmation must be true.")

    verification_commands = evidence.get("verification_commands")
    if not isinstance(verification_commands, list) or not verification_commands:
        raise ValueError("acceptance_evidence.verification_commands must be a non-empty list.")
    normalized_commands: list[dict[str, str]] = []
    for item in verification_commands:
        if not isinstance(item, dict) or not isinstance(item.get("command"), str):
            raise ValueError("acceptance_evidence.verification_commands entries require a command string.")
        if item.get("status") != "passed":
            raise ValueError("acceptance_evidence.verification_commands entries must all have status=passed.")
        normalized_commands.append({"command": item["command"], "status": "passed"})

    covered_requirements = _string_list(evidence.get("covered_requirements", []))
    covered_questions = _string_list(evidence.get("covered_questions", []))
    source_checks = _string_list(evidence.get("source_checks", []))
    if not (covered_requirements or covered_questions or source_checks):
        raise ValueError(
            "acceptance_evidence requires at least one covered requirement, covered question, or source check."
        )

    no_task_reason = evidence.get("no_task_context_pack_reason")
    if not isinstance(no_task_reason, str) or not no_task_reason.strip():
        raise ValueError("acceptance_evidence.no_task_context_pack_reason is required.")

    return {
        "schema": RESEARCH_ACCEPTANCE_EVIDENCE_SCHEMA,
        "durable_artifacts": durable_artifacts,
        "allowed_path_confirmation": True,
        "verification_commands": normalized_commands,
        "covered_requirements": covered_requirements,
        "covered_questions": covered_questions,
        "source_checks": source_checks,
        "no_task_context_pack_reason": no_task_reason,
    }


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        return []
    return list(value)


def _is_research_evidence_path(path: str) -> bool:
    return path in _RESEARCH_EVIDENCE_EXACT_PATHS or path.startswith(_RESEARCH_EVIDENCE_PATH_PREFIXES)


DOC_REVIEW_SCHEMA = "agentspec.doc_review.v0"
DOC_REVIEW_CHECK_SCHEMA = "agentspec.doc_review_check.v0"
ALLOWED_DOC_REVIEW_MODES = frozenset({"deterministic", "model"})
ALLOWED_DOC_REVIEW_VERDICTS = frozenset(
    {"ready", "revise", "human_override_required"}
)
ALLOWED_DOC_REVIEW_REVIEWERS = frozenset(
    {"human", "deterministic", "model", "agent"}
)


def record_doc_review(
    root: Path,
    *,
    artifact_selector: str,
    mode: str | None = None,
    verdict: str | None = None,
    reviewer: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    if sum(value is not None for value in (mode, verdict)) != 1:
        raise ValueError("Document review requires exactly one of --mode, --verdict, or --check.")

    artifact_path = _resolve_doc_review_artifact(root, artifact_selector)
    artifact_text = artifact_path.read_text(encoding="utf-8")
    artifact_kind = _doc_artifact_kind(root, artifact_path)
    digests = _artifact_digests(artifact_path)
    requirement_refs = sorted(set(re.findall(r"\bR-\d{3,}\b", artifact_text)))
    dcr_refs = sorted(set(re.findall(r"\bDCR-\d{4,}\b", artifact_text)))

    if mode is not None:
        if mode not in ALLOWED_DOC_REVIEW_MODES:
            allowed = ", ".join(sorted(ALLOWED_DOC_REVIEW_MODES))
            raise ValueError(f"Invalid document review mode {mode!r}; expected one of: {allowed}.")
        if mode == "model":
            raise ValueError("Model-backed document review is not implemented yet; use --mode deterministic or record a manual verdict.")
        review_result = _deterministic_doc_review(artifact_kind, artifact_text)
        verdict_value = review_result["verdict"]
        reviewer_value = "deterministic"
        summary_value = review_result["summary"]
        findings = review_result["findings"]
        rubric = {
            "deterministic_checks": review_result["checks"],
            "ai_checks": [],
        }
    else:
        if verdict not in ALLOWED_DOC_REVIEW_VERDICTS:
            allowed = ", ".join(sorted(ALLOWED_DOC_REVIEW_VERDICTS))
            raise ValueError(f"Invalid document review verdict {verdict!r}; expected one of: {allowed}.")
        if reviewer not in ALLOWED_DOC_REVIEW_REVIEWERS:
            allowed = ", ".join(sorted(ALLOWED_DOC_REVIEW_REVIEWERS))
            raise ValueError(f"Document review reviewer is required and must be one of: {allowed}.")
        if not summary or not summary.strip():
            raise ValueError("Document review summary is required for manual verdicts.")
        verdict_value = verdict
        reviewer_value = reviewer
        summary_value = summary.strip()
        findings = []
        rubric = {"deterministic_checks": [], "ai_checks": []}

    timestamp = utc_now_iso()
    review_id = _next_doc_review_id(root)
    record = {
        "schema": DOC_REVIEW_SCHEMA,
        "id": review_id,
        "artifact_path": _relative_or_absolute(root, artifact_path),
        "artifact_kind": artifact_kind,
        "verdict": verdict_value,
        "reviewer": reviewer_value,
        "summary": summary_value,
        "findings": findings,
        "rubric": rubric,
        "requirement_refs": requirement_refs,
        "dcr_refs": dcr_refs,
        "artifact_digest": digests["artifact_digest"],
        "normalized_artifact_digest": digests["normalized_artifact_digest"],
        "artifact_revision": None,
        "author_type": "unknown",
        "generated_by": None,
        "reviewed_at": timestamp,
        "created_at": timestamp,
    }
    write_data(_doc_review_path(root, review_id), record)
    return record


def check_doc_review(root: Path, *, artifact_selector: str) -> dict[str, Any]:
    root = root.resolve()
    artifact_path = _resolve_doc_review_artifact(root, artifact_selector)
    artifact_kind = _doc_artifact_kind(root, artifact_path)
    digests = _artifact_digests(artifact_path)
    artifact_rel = _relative_or_absolute(root, artifact_path)
    latest_ready = _latest_ready_doc_review(root, artifact_rel)

    if latest_ready is None:
        readiness = "missing"
        current = False
    elif (
        latest_ready.get("artifact_digest") == digests["artifact_digest"]
        or latest_ready.get("normalized_artifact_digest") == digests["normalized_artifact_digest"]
    ):
        readiness = "current"
        current = True
    else:
        readiness = "stale"
        current = False

    latest_summary = None
    if latest_ready is not None:
        latest_summary = {
            "id": latest_ready.get("id"),
            "path": _relative_or_absolute(root, _doc_review_path(root, str(latest_ready.get("id")))),
            "verdict": latest_ready.get("verdict"),
            "reviewer": latest_ready.get("reviewer"),
            "reviewed_at": latest_ready.get("reviewed_at"),
        }

    return {
        "schema": DOC_REVIEW_CHECK_SCHEMA,
        "artifact_path": artifact_rel,
        "artifact_kind": artifact_kind,
        "readiness": readiness,
        "current": current,
        "latest_review": latest_summary,
        "artifact_digest": digests["artifact_digest"],
        "normalized_artifact_digest": digests["normalized_artifact_digest"],
    }


def _resolve_doc_review_artifact(root: Path, selector: str) -> Path:
    if not selector or not selector.strip():
        raise ValueError("Document review artifact path is required.")
    candidate = Path(selector)
    path = candidate if candidate.is_absolute() else root / candidate
    path = path.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Document review artifact must be inside the project root: {selector}") from exc
    if not path.exists():
        raise FileNotFoundError(f"Document review artifact not found: {selector}")
    if not path.is_file():
        raise ValueError(f"Document review artifact path is not a file: {selector}")
    return path


def _doc_artifact_kind(root: Path, path: Path) -> str:
    rel = _relative_or_absolute(root, path).replace("\\", "/")
    name = path.name
    if rel.startswith("docs/change-requests/") and name.startswith("DCR-"):
        return "dcr"
    if rel.startswith("docs/discovery/spikes/") and name.endswith(".md"):
        return "spike"
    if rel.startswith("agent/workflows/") or ("/plans/" in rel and "workflow" in name):
        return "workflow"
    if rel.startswith("docs/designs/") and name.endswith(".md"):
        return "design"
    if "source" in rel and "candidate" in rel:
        return "source_candidate"
    if rel == "docs/ROADMAP.md":
        return "roadmap"
    return "other"


def _artifact_digests(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    normalized = _normalized_artifact_text(path).encode("utf-8")
    return {
        "artifact_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "normalized_artifact_digest": "sha256:" + hashlib.sha256(normalized).hexdigest(),
    }


def _normalized_artifact_text(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n"))


def _deterministic_doc_review(artifact_kind: str, text: str) -> dict[str, Any]:
    checks: list[str] = []
    findings: list[dict[str, str]] = []
    if artifact_kind == "dcr":
        checks.append("dcr_required_sections_present")
        for heading in ("Summary", "Motivation", "Proposed Change", "Acceptance Criteria"):
            if not re.search(rf"^##\s+{re.escape(heading)}\s*$", text, flags=re.MULTILINE):
                findings.append(
                    _doc_review_finding(
                        issue=f"DCR section is missing: {heading}.",
                        evidence=f"Expected '## {heading}'.",
                        suggestion=f"Add a {heading} section before accepting or tasking this DCR.",
                    )
                )
    elif artifact_kind == "workflow":
        checks.extend(["workflow_allowed_paths_present", "workflow_verification_present"])
        lowered = text.lower()
        if "allowed_paths" not in lowered and not re.search(r"^##\s+allowed paths\s*$", text, flags=re.MULTILINE | re.IGNORECASE):
            findings.append(
                _doc_review_finding(
                    issue="Workflow allowed paths are missing.",
                    evidence="No allowed_paths metadata or Allowed Paths section found.",
                    suggestion="Declare workflow allowed paths before execution.",
                )
            )
        if (
            "verification_commands" not in lowered
            and "verify:" not in lowered
            and not re.search(r"^##\s+verification", text, flags=re.MULTILINE | re.IGNORECASE)
        ):
            findings.append(
                _doc_review_finding(
                    issue="Workflow verification commands are missing.",
                    evidence="No verification_commands metadata, verify field, or Verification section found.",
                    suggestion="Declare verification commands or review gates before execution.",
                )
            )
    else:
        checks.append("artifact_nonempty")
        if not text.strip():
            findings.append(
                _doc_review_finding(
                    issue="Artifact is empty.",
                    evidence="Reviewed artifact has no non-whitespace content.",
                    suggestion="Add content before recording a ready document review.",
                )
            )

    verdict = "ready" if not findings else "revise"
    summary = "Deterministic document review passed." if not findings else f"Deterministic document review found {len(findings)} finding(s)."
    return {"verdict": verdict, "summary": summary, "findings": findings, "checks": checks}


def _doc_review_finding(*, issue: str, evidence: str, suggestion: str) -> dict[str, str]:
    return {
        "severity": "high",
        "issue": issue,
        "evidence": evidence,
        "suggestion": suggestion,
    }


def _latest_ready_doc_review(root: Path, artifact_path: str) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    for path in sorted((root / "agent" / "doc-reviews").glob("DOCREVIEW-*.yml")):
        record = load_data(path, {})
        if not isinstance(record, dict):
            continue
        if record.get("schema") != DOC_REVIEW_SCHEMA:
            continue
        if record.get("artifact_path") != artifact_path:
            continue
        if record.get("verdict") == "ready":
            candidates.append(record)
    if not candidates:
        return None
    candidates.sort(key=lambda item: str(item.get("reviewed_at") or item.get("id") or ""))
    return candidates[-1]


def _next_doc_review_id(root: Path) -> str:
    review_dir = root / "agent" / "doc-reviews"
    highest = 0
    for path in review_dir.glob("DOCREVIEW-*.yml"):
        stem = path.stem
        if stem.startswith("DOCREVIEW-") and stem.split("-", 1)[1].isdigit():
            highest = max(highest, int(stem.split("-", 1)[1]))
    return f"DOCREVIEW-{highest + 1:04d}"


def _doc_review_path(root: Path, review_id: str) -> Path:
    candidate = Path(review_id)
    if candidate.is_absolute():
        return candidate
    if candidate.suffix == ".yml":
        if len(candidate.parts) > 1:
            return root / candidate
        return root / "agent" / "doc-reviews" / candidate.name
    if len(candidate.parts) > 1:
        return root / candidate
    return root / "agent" / "doc-reviews" / f"{review_id}.yml"


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
