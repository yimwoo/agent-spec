"""Post-artifact lifecycle guidance for human and adapter-facing responses."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .dcr import parse_dcr
from .markdown import document_title
from .review import check_doc_review
from .session import build_session_preflight
from .task import list_task_context_packs
from .workflow import workflow_lifecycle_for_context_pack


POST_ARTIFACT_GUIDANCE_SCHEMA = "agentspec.post_artifact_guidance.v0"


def build_post_artifact_guidance(root: Path, artifact_path: str | Path) -> dict[str, Any]:
    """Build state-aware next-step guidance for a newly touched artifact.

    Args:
        root: AgentSpec project root.
        artifact_path: Absolute or project-relative artifact path.

    Returns:
        A structured guidance payload with human-facing text and optional
        adapter commands for the next lifecycle transition.

    Raises:
        FileNotFoundError: If the artifact path does not exist.
        ValueError: If the path is outside the project root.
    """

    root = root.resolve()
    path = _resolve_artifact_path(root, artifact_path)
    rel_path = _relative(root, path)
    if _is_dcr_path(rel_path, path):
        return _dcr_guidance(root, path, rel_path)
    if _is_design_path(rel_path, path):
        return _design_guidance(root, path, rel_path)
    if _is_task_context_pack_path(rel_path, path):
        return _task_context_pack_guidance(root, path, rel_path)
    return _unsupported_guidance(rel_path)


def format_post_artifact_guidance(guidance: dict[str, Any]) -> str:
    """Format post-artifact guidance for command-free human output.

    Args:
        guidance: Structured payload returned by
            :func:`build_post_artifact_guidance`.

    Returns:
        A concise CLI-safe summary that omits internal terminal commands.
    """

    display = _dict_or_empty(guidance.get("agent_display"))
    lines = [str(guidance.get("summary") or "Post-artifact guidance is available.")]
    display_guidance = str(display.get("guidance") or "").strip()
    if display_guidance:
        lines.append(f"Next: {display_guidance}")
    prompt = str(display.get("prompt") or "").strip()
    if prompt:
        lines.append(f"Prompt: {prompt}")
    return "\n".join(lines)


def _dcr_guidance(root: Path, path: Path, rel_path: str) -> dict[str, Any]:
    dcr = parse_dcr(path)
    review = check_doc_review(root, artifact_selector=rel_path)
    review_state = str(review.get("readiness") or "missing")
    dcr_id = str(dcr["id"])
    title = _dcr_title(path, dcr_id)

    if review_state == "current":
        next_actions = _review_ready_dcr_actions(dcr)
        state = "review_ready"
        summary = f"{dcr_id} has current document review evidence."
    elif review_state == "stale":
        next_actions = _review_needed_dcr_actions(dcr_id, rel_path, stale=True)
        state = "review_stale"
        summary = f"{dcr_id} changed after its latest ready document review."
    else:
        next_actions = _review_needed_dcr_actions(dcr_id, rel_path, stale=False)
        state = "review_missing"
        summary = f"{dcr_id} needs document review before acceptance or tasking."

    return _guidance_payload(
        artifact={
            "kind": "dcr",
            "id": dcr_id,
            "title": title,
            "path": rel_path,
            "status": dcr.get("status"),
            "classification": dcr.get("classification"),
        },
        state=state,
        review={
            "readiness": review_state,
            "current": bool(review.get("current")),
            "latest_review": review.get("latest_review"),
        },
        summary=summary,
        next_actions=next_actions,
    )


def _design_guidance(root: Path, path: Path, rel_path: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    title = document_title(text, fallback=path.stem)
    review = check_doc_review(root, artifact_selector=rel_path)
    review_state = str(review.get("readiness") or "missing")

    if review_state == "current":
        state = "review_ready"
        summary = f"Design {title!r} has current document review evidence."
        next_actions = _review_ready_design_actions(title, rel_path)
    elif review_state == "stale":
        state = "review_stale"
        summary = f"Design {title!r} changed after its latest ready document review."
        next_actions = _review_needed_actions(
            artifact_label=f"design {title!r}",
            rel_path=rel_path,
            stale=True,
            prompt=f"Review the updated design {rel_path} before promoting it as source.",
        )
    else:
        state = "review_missing"
        summary = f"Design {title!r} needs document review before source promotion or tasking."
        next_actions = _review_needed_actions(
            artifact_label=f"design {title!r}",
            rel_path=rel_path,
            stale=False,
            prompt=f"Review the design {rel_path} before promoting it as source.",
        )

    return _guidance_payload(
        artifact={
            "kind": "design",
            "title": title,
            "path": rel_path,
        },
        state=state,
        review={
            "readiness": review_state,
            "current": bool(review.get("current")),
            "latest_review": review.get("latest_review"),
        },
        summary=summary,
        next_actions=next_actions,
    )


def _task_context_pack_guidance(root: Path, path: Path, rel_path: str) -> dict[str, Any]:
    record = _task_context_pack_record(root, rel_path) or _fallback_task_record(path, rel_path)
    task_id = str(record.get("id") or path.stem.split("-", 2)[0])
    title = str(record.get("title") or path.stem)
    workflow_plan = workflow_lifecycle_for_context_pack(root, rel_path)
    workflow_present = bool(workflow_plan.get("present"))

    artifact = {
        "kind": "task_context_pack",
        "id": task_id,
        "title": title,
        "path": rel_path,
        "status": record.get("status"),
        "type": record.get("type"),
        "workflow": record.get("workflow"),
        "workflow_plan": workflow_plan,
    }

    if not workflow_present:
        state = "task_created_workflow_needed"
        summary = f"Task {task_id} has a context pack but no linked workflow plan yet."
        next_actions = [
            {
                "id": "plan_workflow",
                "label": "Plan the workflow",
                "description": "Create or link a workflow before branch/session execution.",
                "prompt": f"Plan workflow for {task_id}, then start a branch/worktree session before implementation.",
                "commands": [f"aspec plan {task_id} --json"],
            },
            {
                "id": "revise_task_scope",
                "label": "Revise task scope",
                "description": "Update allowed paths, verification, or requirement scope before planning execution.",
                "prompt": f"Revise {task_id} before workflow planning if the scope is not correct.",
                "commands": [],
            },
        ]
    else:
        session_preflight = build_session_preflight(
            root,
            context_pack=rel_path,
            task_id=task_id,
            task_type=str(record.get("type") or "implementation"),
        )
        artifact["session_preflight"] = session_preflight
        preflight_status = str(session_preflight.get("status") or "missing")
        if preflight_status == "blocked":
            state = "task_created_session_blocked"
            summary = f"Task {task_id} has a workflow plan, but branch/worktree session preflight is blocked."
            next_actions = [_session_action(session_preflight, task_id, blocked=True)]
        elif preflight_status == "missing":
            state = "task_created_session_needed"
            summary = f"Task {task_id} has a workflow plan; claim a branch/worktree session before implementation."
            next_actions = [_session_action(session_preflight, task_id, blocked=False)]
        else:
            state = "task_ready"
            summary = f"Task {task_id} has workflow and session preflight ready."
            next_actions = [
                {
                    "id": "start_execution",
                    "label": "Start execution",
                    "description": "Run the task through the planned workflow under the active session lease.",
                    "prompt": f"Start execution for {task_id} under its workflow and active session lease.",
                    "commands": [f"aspec run loop {rel_path}"],
                }
            ]

    return _guidance_payload(
        artifact=artifact,
        state=state,
        review=None,
        summary=summary,
        next_actions=next_actions,
    )


def _review_needed_dcr_actions(dcr_id: str, rel_path: str, *, stale: bool) -> list[dict[str, Any]]:
    verb = "Review the updated DCR" if stale else "Review the DCR"
    reason = (
        "Document review is stale; review it again before acceptance or tasking."
        if stale
        else "Document review is missing; review it before acceptance or tasking."
    )
    return [
        {
            "id": "review_document",
            "label": verb,
            "description": reason,
            "prompt": f"Review {dcr_id}, then accept it if ready.",
            "commands": [f"aspec review doc {rel_path} --mode deterministic --json"],
        },
        {
            "id": "revise_document",
            "label": "Revise the DCR",
            "description": "Update the DCR content before recording review evidence.",
            "prompt": f"Revise {dcr_id} to address the missing or stale review evidence.",
            "commands": [],
        },
    ]


def _review_ready_dcr_actions(dcr: dict[str, Any]) -> list[dict[str, Any]]:
    dcr_id = str(dcr["id"])
    status = str(dcr.get("status") or "")
    actions: list[dict[str, Any]] = []
    if status != "accepted":
        actions.append(
            {
                "id": "accept_dcr",
                "label": "Accept the DCR",
                "description": "Document review is current; the DCR can be accepted, revised, or left classified.",
                "prompt": f"Accept {dcr_id} and create the next implementation task when ready.",
                "commands": [f"aspec dcr accept {dcr_id}"],
            }
        )
    actions.extend(
        [
            {
                "id": "create_task",
                "label": "Create implementation scope",
                "description": "Use the reviewed DCR as source for a requirement and bounded task pack.",
                "prompt": f"Create a task context pack for {dcr_id} and start implementation.",
                "commands": ["aspec task create --requirement <R-id> --type implementation"],
            },
            {
                "id": "revise_dcr",
                "label": "Revise the DCR",
                "description": "Change the DCR if the current proposal is not the right scope.",
                "prompt": f"Revise {dcr_id} before accepting or tasking it.",
                "commands": [],
            },
        ]
    )
    return actions


def _review_ready_design_actions(title: str, rel_path: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "promote_source",
            "label": "Promote as source",
            "description": "Document review is current; promote the design as source and compile requirements before tasking.",
            "prompt": f"Promote {rel_path} as AgentSpec source, compile requirements, and create the next task pack.",
            "commands": [f"aspec ingest {rel_path}", "aspec compile"],
        },
        {
            "id": "create_task",
            "label": "Create implementation scope",
            "description": "After source promotion and requirement compilation, create a bounded task context pack.",
            "prompt": f"Create requirements and a task context pack from {title} when the source projection is ready.",
            "commands": ["aspec task create --requirement <R-id> --type implementation"],
        },
        {
            "id": "revise_design",
            "label": "Revise the design",
            "description": "Change the design if it is not the right source for implementation.",
            "prompt": f"Revise {rel_path} before source promotion.",
            "commands": [],
        },
    ]


def _review_needed_actions(
    *,
    artifact_label: str,
    rel_path: str,
    stale: bool,
    prompt: str,
) -> list[dict[str, Any]]:
    return [
        {
            "id": "review_document",
            "label": "Review the updated artifact" if stale else "Review the artifact",
            "description": (
                "Document review is stale; review it again before promotion or tasking."
                if stale
                else "Document review is missing; review it before promotion or tasking."
            ),
            "prompt": prompt,
            "commands": [f"aspec review doc {rel_path} --mode deterministic --json"],
        },
        {
            "id": "revise_document",
            "label": f"Revise {artifact_label}",
            "description": "Update the artifact content before recording review evidence.",
            "prompt": f"Revise {rel_path} before document review.",
            "commands": [],
        },
    ]


def _session_action(session_preflight: dict[str, Any], task_id: str, *, blocked: bool) -> dict[str, Any]:
    command = str(session_preflight.get("recommended_command") or f"aspec session start --task {task_id}")
    return {
        "id": "fix_session" if blocked else "claim_session",
        "label": "Fix branch/worktree session" if blocked else "Claim branch/worktree session",
        "description": str(
            session_preflight.get("agent_guidance")
            or "Claim a branch/worktree session before implementation."
        ),
        "prompt": (
            f"Fix branch/worktree session preflight for {task_id} before implementation."
            if blocked
            else f"Start a branch/worktree session for {task_id} before implementation."
        ),
        "commands": [command],
    }


def _guidance_payload(
    *,
    artifact: dict[str, Any],
    state: str,
    review: dict[str, Any] | None,
    summary: str,
    next_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    primary = next_actions[0] if next_actions else {
        "label": "Inspect artifact manually",
        "description": "No state-aware next action is available for this artifact type yet.",
        "prompt": "",
    }
    return {
        "schema": POST_ARTIFACT_GUIDANCE_SCHEMA,
        "artifact": artifact,
        "state": state,
        "review": review,
        "summary": summary,
        "next_actions": next_actions,
        "agent_display": {
            "label": str(primary["label"]),
            "guidance": str(primary["description"]),
            "prompt": str(primary.get("prompt") or ""),
            "show_terminal_commands": False,
        },
    }


def _task_context_pack_record(root: Path, rel_path: str) -> dict[str, Any] | None:
    for record in list_task_context_packs(root):
        if record.get("path") == rel_path:
            return record
    return None


def _fallback_task_record(path: Path, rel_path: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    first_line = text.splitlines()[0] if text.splitlines() else ""
    match = re.match(r"^#\s+(T-\d{3,}):?\s*(.*)$", first_line.strip())
    task_id = match.group(1) if match else path.stem.split("-", 2)[0]
    title = match.group(2).strip() if match and match.group(2).strip() else path.stem
    return {
        "id": task_id,
        "title": title,
        "type": _metadata_value(text, "Type") or "implementation",
        "path": rel_path,
        "status": "ready",
        "workflow": _metadata_value(text, "Workflow"),
    }


def _metadata_value(text: str, name: str) -> str | None:
    match = re.search(rf"^{re.escape(name)}:\s*`?([^`\n]+)`?\s*$", text, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _unsupported_guidance(rel_path: str) -> dict[str, Any]:
    return _guidance_payload(
        artifact={
            "kind": "other",
            "path": rel_path,
        },
        state="unsupported",
        review=None,
        summary="No post-artifact guidance is available for this artifact type yet.",
        next_actions=[],
    )


def _resolve_artifact_path(root: Path, artifact_path: str | Path) -> Path:
    path = Path(artifact_path)
    candidate = path if path.is_absolute() else root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Artifact must be inside the project root: {artifact_path}") from exc
    if not resolved.is_file():
        raise FileNotFoundError(f"Artifact not found: {artifact_path}")
    return resolved


def _is_dcr_path(rel_path: str, path: Path) -> bool:
    return rel_path.startswith("docs/change-requests/DCR-") and path.suffix == ".md"


def _is_design_path(rel_path: str, path: Path) -> bool:
    return rel_path.startswith("docs/designs/") and path.suffix == ".md"


def _is_task_context_pack_path(rel_path: str, path: Path) -> bool:
    return rel_path.startswith("agent/context-packs/T-") and path.suffix == ".md"


def _dcr_title(path: Path, dcr_id: str) -> str:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    prefix = f"# {dcr_id}:"
    if first_line.startswith(prefix):
        return first_line.removeprefix(prefix).strip()
    return path.stem


def _relative(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
