from __future__ import annotations

import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io import utc_now_iso
from .paths import slugify, truncate_on_word_boundary


WORKFLOW_CONTRACT_SCHEMA = "agentspec.workflow_contract.v0"
WORKFLOW_PARSE_SCHEMA = "agentspec.workflow_parse.v0"
WORKFLOW_PLAN_RESULT_SCHEMA = "agentspec.workflow_plan_result.v0"


@dataclass(frozen=True)
class WorkflowArtifact:
    kind: str
    path: str
    title: str
    reference_paths: tuple[str, ...] = field(default_factory=tuple)
    task_pack: str | None = None


def build_workflow_contract_status(root: Path) -> dict[str, Any]:
    root = root.resolve()
    context_pack_texts = _context_pack_texts(root)
    artifacts = list_workflow_artifacts(root)
    records: list[dict[str, Any]] = []
    for artifact in artifacts:
        referenced_by = _referenced_by(context_pack_texts, artifact)
        orphan = not referenced_by and artifact.task_pack is None
        records.append(
            {
                "kind": artifact.kind,
                "path": artifact.path,
                "title": artifact.title,
                "reference_paths": list(artifact.reference_paths),
                "task_pack": artifact.task_pack,
                "referenced_by": referenced_by,
                "status": "orphan" if orphan else "referenced",
                "backfill_command": f"aspec task create --from-workflow {artifact.path}",
            }
        )

    orphans = [record for record in records if record["status"] == "orphan"]
    broken_links = _broken_links(root, context_pack_texts, artifacts)
    return {
        "schema": WORKFLOW_CONTRACT_SCHEMA,
        "total": len(records),
        "orphan_count": len(orphans),
        "broken_link_count": len(broken_links),
        "artifacts": records,
        "orphans": orphans,
        "broken_links": broken_links,
        "summary": _summary(records, orphans),
    }


def list_workflow_artifacts(root: Path) -> list[WorkflowArtifact]:
    root = root.resolve()
    artifacts: list[WorkflowArtifact] = []
    seen: set[str] = set()

    for path in sorted(root.glob("docs/**/plans/**/*.md")):
        if not path.is_file() or not path.name.endswith("workflow.md"):
            continue
        rel = _relative(root, path)
        seen.add(rel)
        parsed = parse_workflow_file(root, Path(rel))
        artifacts.append(
            WorkflowArtifact(
                kind="workflow",
                path=rel,
                title=str(parsed.get("title") or Path(rel).stem),
                reference_paths=(rel,),
                task_pack=_first_string(parsed.get("task_pack")),
            )
        )

    for path in sorted((root / "agent" / "workflows").glob("W-*.md")):
        if not path.is_file():
            continue
        rel = _relative(root, path)
        if rel in seen:
            continue
        seen.add(rel)
        parsed = parse_workflow_file(root, Path(rel))
        artifacts.append(
            WorkflowArtifact(
                kind="workflow",
                path=rel,
                title=str(parsed.get("title") or Path(rel).stem),
                reference_paths=(rel,),
                task_pack=_first_string(parsed.get("task_pack")),
            )
        )

    state_root = root / ".hotl" / "state"
    if state_root.is_dir():
        for path in sorted(state_root.rglob("*.json")):
            if not path.is_file():
                continue
            rel = _relative(root, path)
            parsed = parse_workflow_file(root, Path(rel))
            refs = [rel]
            workflow_path = parsed.get("workflow_path")
            if isinstance(workflow_path, str) and workflow_path and workflow_path not in refs:
                refs.append(workflow_path)
            if rel in seen:
                continue
            seen.add(rel)
            artifacts.append(
                WorkflowArtifact(
                    kind="state",
                    path=rel,
                    title=str(parsed.get("title") or Path(rel).stem),
                    reference_paths=tuple(refs),
                    task_pack=_first_string(parsed.get("task_pack")),
                )
            )

    return artifacts


def parse_workflow_file(root: Path, workflow_file: Path) -> dict[str, Any]:
    root = root.resolve()
    path = _resolve_under_root(root, workflow_file)
    rel = _relative(root, path)
    if path.suffix.lower() == ".json":
        return _parse_json_state(root, path, rel)
    return _parse_markdown_workflow(root, path, rel)


def workflow_warning_lines(status: dict[str, Any]) -> list[str]:
    orphans = status.get("orphans") if isinstance(status.get("orphans"), list) else []
    lines: list[str] = []
    for orphan in orphans:
        if not isinstance(orphan, dict):
            continue
        label = _artifact_warning_label(orphan)
        lines.append(
            f"{label} without task pack: "
            f"{orphan.get('path')} -> {orphan.get('backfill_command')}"
        )
    return lines


def create_or_link_native_workflow(root: Path, task_selector: str | Path) -> dict[str, Any]:
    root = root.resolve()
    task_path = _resolve_context_pack(root, task_selector)
    task_rel = _relative(root, task_path)
    task = _parse_context_pack_for_plan(root, task_path)

    existing_workflow = task.get("workflow")
    if existing_workflow:
        workflow_path = root / str(existing_workflow)
        if not str(existing_workflow).startswith("agent/workflows/"):
            raise ValueError(
                f"Task context pack already links to non-native workflow {existing_workflow}; "
                "resolve that link before creating a native workflow."
            )
        if not workflow_path.exists():
            raise ValueError(f"Task context pack references missing workflow {existing_workflow}.")
        parsed = parse_workflow_file(root, Path(str(existing_workflow)))
        linked_task = parsed.get("task_pack")
        if linked_task and linked_task != task_rel:
            raise ValueError(
                f"Workflow {existing_workflow} links to {linked_task}, "
                f"not {task_rel}."
            )
        if linked_task == task_rel:
            return _plan_result(task, str(existing_workflow), created=False, updated_task=False)
        _write_native_workflow(root, workflow_path, task, workflow_id=_workflow_id_from_path(workflow_path))
        return _plan_result(task, str(existing_workflow), created=False, updated_task=False)

    for artifact in list_workflow_artifacts(root):
        if artifact.path.startswith("agent/workflows/") and artifact.task_pack == task_rel:
            _write_task_workflow_link(task_path, artifact.path)
            return _plan_result(task, artifact.path, created=False, updated_task=True)

    workflow_id, workflow_path = _next_native_workflow_path(root, task)
    _write_native_workflow(root, workflow_path, task, workflow_id=workflow_id)
    workflow_rel = _relative(root, workflow_path)
    _write_task_workflow_link(task_path, workflow_rel)
    return _plan_result(task, workflow_rel, created=True, updated_task=True)


def _parse_markdown_workflow(root: Path, path: Path, rel: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _frontmatter(text)
    metadata = _parse_simple_metadata(frontmatter)
    warnings: list[str] = []
    historical_evidence: list[str] = []
    title = (
        _first_string(metadata.get("title"))
        or _first_string(metadata.get("intent"))
        or _first_heading(body)
        or _title_from_filename(path)
    )
    verification_commands = _verification_commands_from_markdown(
        text,
        metadata,
        historical_evidence=historical_evidence,
        warnings=warnings,
    )
    allowed_paths = _allowed_paths_from_markdown(root, text, metadata, verification_commands, warnings)
    task_pack = _normalize_optional_path(root, _first_string(metadata.get("task_pack")))
    return {
        "schema": WORKFLOW_PARSE_SCHEMA,
        "kind": "workflow",
        "path": rel,
        "workflow_path": rel,
        "task_pack": task_pack,
        "title": truncate_on_word_boundary(title, limit=96),
        "intent": _first_string(metadata.get("intent")) or title,
        "allowed_paths": allowed_paths,
        "verification_commands": verification_commands,
        "extraction_warnings": _dedupe(warnings),
        "historical_evidence": _dedupe(historical_evidence),
    }


def _parse_json_state(root: Path, path: Path, rel: str) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        data = {}
    title = (
        _first_json_string(data, ("title", "intent", "workflow_title", "name"))
        or _title_from_filename(path)
    )
    workflow_path = _normalize_optional_path(
        root,
        _first_json_string(data, ("workflow_path", "workflow_file", "plan_path", "workflow")),
    )
    task_pack = _normalize_optional_path(root, _first_json_string(data, ("task_pack", "context_pack")))
    warnings: list[str] = []
    historical_evidence: list[str] = []
    allowed_paths = _dedupe(
        normalized
        for value in _json_values_by_key(data, {"allowed_paths", "write_scope", "paths", "touched_paths"})
        if (normalized := _normalize_path_candidate(root, value, warnings=warnings)) is not None
    )
    verification_commands = _dedupe(
        normalized
        for value in _json_values_by_key(data, {"verify", "verification", "verification_commands", "command"})
        if (
            normalized := _normalize_verification_command(
                value,
                historical_evidence=historical_evidence,
                warnings=warnings,
            )
        )
        is not None
    )
    allowed_paths = _dedupe([*allowed_paths, *_paths_from_commands(root, verification_commands, warnings)])
    if not allowed_paths:
        allowed_paths = ["docs/**"]
    return {
        "schema": WORKFLOW_PARSE_SCHEMA,
        "kind": "state",
        "path": rel,
        "workflow_path": workflow_path or rel,
        "task_pack": task_pack,
        "title": truncate_on_word_boundary(title, limit=96),
        "intent": title,
        "allowed_paths": allowed_paths,
        "verification_commands": verification_commands,
        "extraction_warnings": _dedupe(warnings),
        "historical_evidence": _dedupe(historical_evidence),
    }


def _frontmatter(text: str) -> tuple[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return "", text


def _parse_simple_metadata(text: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key_match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if key_match:
            key = key_match.group(1)
            value = key_match.group(2).strip()
            current_key = key
            if value:
                data[key] = _strip_quotes(value)
            else:
                data[key] = []
            continue
        item_match = re.match(r"^\s*-\s*(.+)$", line)
        if item_match and current_key:
            value = _strip_quotes(item_match.group(1).strip())
            existing = data.setdefault(current_key, [])
            if isinstance(existing, list):
                existing.append(value)
    return data


def _verification_commands_from_markdown(
    text: str,
    metadata: dict[str, Any],
    *,
    historical_evidence: list[str],
    warnings: list[str],
) -> list[str]:
    commands: list[str] = []
    for value in _metadata_values(metadata, ("verify", "verification", "verification_commands")):
        command = _normalize_verification_command(value, historical_evidence=historical_evidence, warnings=warnings)
        if command is not None:
            commands.append(command)

    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("verify:"):
            value = stripped.removeprefix("verify:").strip()
            if value:
                command = _normalize_verification_command(
                    _strip_quotes(value),
                    historical_evidence=historical_evidence,
                    warnings=warnings,
                )
                if command is not None:
                    commands.append(command)
                index += 1
                continue
            index += 1
            while index < len(lines):
                child = lines[index]
                if child.strip() and not child.startswith((" ", "\t", "-")):
                    break
                command_match = re.search(r"\bcommand:\s*(.+)$", child.strip())
                if command_match:
                    command = _normalize_verification_command(
                        _strip_quotes(command_match.group(1).strip()),
                        historical_evidence=historical_evidence,
                        warnings=warnings,
                    )
                    if command is not None:
                        commands.append(command)
                index += 1
            continue
        command_match = re.match(r"^\s*command:\s*(.+)$", line)
        if command_match and _near_verify(lines, index):
            command = _normalize_verification_command(
                _strip_quotes(command_match.group(1).strip()),
                historical_evidence=historical_evidence,
                warnings=warnings,
            )
            if command is not None:
                commands.append(command)
        index += 1

    return _dedupe(command for command in commands if _looks_like_command(command))


def _allowed_paths_from_markdown(
    root: Path,
    text: str,
    metadata: dict[str, Any],
    verification_commands: list[str],
    warnings: list[str],
) -> list[str]:
    paths: list[str] = []
    for value in _metadata_values(metadata, ("allowed_paths", "write_scope", "paths", "files", "touched_paths")):
        normalized = _normalize_path_candidate(root, value, warnings=warnings)
        if normalized is not None:
            paths.append(normalized)
    paths.extend(_allowed_paths_section(text))
    paths.extend(
        normalized
        for value in re.findall(r"`([^`]+)`", text)
        if (normalized := _normalize_path_candidate(root, value, warnings=None)) is not None
    )
    paths.extend(_paths_from_commands(root, verification_commands, warnings))
    deduped = _dedupe(paths)
    return deduped or ["docs/**"]


def _allowed_paths_section(text: str) -> list[str]:
    match = re.search(r"^##\s+Allowed Paths\s*$", text, flags=re.MULTILINE | re.IGNORECASE)
    if not match:
        return []
    next_match = re.search(r"^##\s+", text[match.end() :], flags=re.MULTILINE)
    section = text[match.end() : match.end() + next_match.start()] if next_match else text[match.end() :]
    return [
        value
        for value in re.findall(r"`([^`]+)`", section)
        if _looks_like_path(value)
    ]


def _paths_from_commands(root: Path, commands: list[str], warnings: list[str]) -> list[str]:
    paths: list[str] = []
    for command in commands:
        if re.search(r"\bdiscover\s+-s\s+tests\b", command):
            paths.append("tests/")
        try:
            parts = shlex.split(command)
        except ValueError:
            parts = command.split()
        for part in parts:
            normalized = _normalize_path_candidate(root, part, warnings=None)
            if normalized is not None:
                paths.append(normalized)
    return _dedupe(paths)


def _context_pack_texts(root: Path) -> dict[str, str]:
    context_dir = root / "agent" / "context-packs"
    if not context_dir.is_dir():
        return {}
    return {
        _relative(root, path): path.read_text(encoding="utf-8")
        for path in sorted(context_dir.glob("T-*.md"))
        if path.is_file()
    }


def _referenced_by(context_pack_texts: dict[str, str], artifact: WorkflowArtifact) -> list[str]:
    referenced: list[str] = []
    for context_pack, text in context_pack_texts.items():
        if any(ref and ref in text for ref in artifact.reference_paths):
            referenced.append(context_pack)
    return referenced


def _broken_links(
    root: Path,
    context_pack_texts: dict[str, str],
    artifacts: list[WorkflowArtifact],
) -> list[dict[str, Any]]:
    broken: list[dict[str, Any]] = []
    artifacts_by_path = {artifact.path: artifact for artifact in artifacts}
    artifact_paths = set(artifacts_by_path)
    context_workflows = {
        context_pack: workflow
        for context_pack, text in context_pack_texts.items()
        if (workflow := _context_pack_workflow(text))
    }

    for context_pack, workflow in context_workflows.items():
        if workflow not in artifact_paths and not (root / workflow).exists():
            broken.append(
                {
                    "type": "missing_workflow",
                    "context_pack": context_pack,
                    "workflow": workflow,
                    "message": f"Task context pack references missing workflow {workflow}.",
                }
            )
            continue
        artifact = artifacts_by_path.get(workflow)
        if artifact is None:
            continue
        if artifact.path.startswith("agent/workflows/") and artifact.task_pack is None:
            broken.append(
                {
                    "type": "missing_workflow_task_pack_reference",
                    "context_pack": context_pack,
                    "workflow": workflow,
                    "message": f"Task context pack references {workflow}, but the workflow does not link back.",
                }
            )
            continue
        if artifact.task_pack and artifact.task_pack != context_pack:
            broken.append(
                {
                    "type": "workflow_task_mismatch",
                    "context_pack": context_pack,
                    "workflow": workflow,
                    "task_pack": artifact.task_pack,
                    "message": f"Task context pack references {workflow}, but the workflow links to {artifact.task_pack}.",
                }
            )

    for artifact in artifacts:
        if not artifact.task_pack:
            continue
        task_path = root / artifact.task_pack
        if not task_path.exists():
            broken.append(
                {
                    "type": "missing_task_pack",
                    "workflow": artifact.path,
                    "task_pack": artifact.task_pack,
                    "message": f"Workflow references missing task context pack {artifact.task_pack}.",
                }
            )
            continue
        if context_workflows.get(artifact.task_pack) != artifact.path:
            broken.append(
                {
                    "type": "missing_task_workflow_reference",
                    "workflow": artifact.path,
                    "task_pack": artifact.task_pack,
                    "message": f"Workflow references {artifact.task_pack}, but the task does not link back.",
                }
            )
    return broken


def _context_pack_workflow(text: str) -> str | None:
    match = re.search(r"^Workflow:\s*`?([^`\n]+)`?\s*$", text, flags=re.MULTILINE)
    if not match:
        return None
    value = _normalize_relative_path_text(match.group(1).strip())
    if value.lower() in {"", "none", "unassigned"}:
        return None
    return value


def _summary(records: list[dict[str, Any]], orphans: list[dict[str, Any]]) -> str:
    if not records:
        return "No workflow artifacts found."
    if not orphans:
        return f"{len(records)} workflow artifact(s) referenced by task packs."
    return f"{len(orphans)}/{len(records)} workflow artifact(s) lack a referencing task context pack."


def _artifact_warning_label(record: dict[str, Any]) -> str:
    path = str(record.get("path") or "")
    kind = str(record.get("kind") or "")
    if kind == "state" or path.startswith(".hotl/"):
        return "Legacy execution state"
    if path.startswith("docs/") and "/plans/" in path:
        return "Legacy execution plan"
    return "Workflow/execution plan"


def _resolve_context_pack(root: Path, selector: str | Path) -> Path:
    value = str(selector).strip()
    if not value:
        raise ValueError("Task selector is required.")
    if re.fullmatch(r"T-\d{3,}", value):
        matches = sorted((root / "agent" / "context-packs").glob(f"{value}-*.md"))
        if not matches:
            raise ValueError(f"Task context pack not found: {value}.")
        if len(matches) > 1:
            raise ValueError(f"Task selector {value} is ambiguous.")
        return matches[0]

    path = Path(value)
    candidate = path if path.is_absolute() else root / path
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Task context pack must be inside the project root: {selector}") from exc
    if not candidate.exists():
        raise ValueError(f"Task context pack not found: {selector}.")
    if not candidate.is_file():
        raise ValueError(f"Task context pack path is not a file: {selector}.")
    return candidate


def _parse_context_pack_for_plan(root: Path, path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    rel = _relative(root, path)
    heading = text.splitlines()[0].strip() if text.splitlines() else f"# {path.stem}"
    match = re.match(r"^#\s+(T-\d{3,}):?\s*(.*)$", heading)
    task_id = match.group(1) if match else path.stem.split("-", 2)[0]
    title = match.group(2).strip() if match and match.group(2).strip() else path.stem
    return {
        "id": task_id,
        "title": truncate_on_word_boundary(title, limit=96),
        "path": rel,
        "type": _context_pack_metadata_value(text, "Type") or "implementation",
        "stream": _context_pack_metadata_value(text, "Stream") or "unassigned",
        "milestone": _context_pack_metadata_value(text, "Milestone") or "unassigned",
        "slice": _context_pack_metadata_value(text, "Slice") or "unassigned",
        "branch": _context_pack_metadata_value(text, "Branch") or "unassigned",
        "workflow": _context_pack_workflow(text),
        "goal": _context_pack_section(text, "Goal").strip() or title,
        "allowed_paths": _allowed_paths_section(text),
        "verification_commands": _context_pack_verification_commands(text),
    }


def _context_pack_metadata_value(text: str, name: str) -> str | None:
    match = re.search(rf"^{re.escape(name)}:\s*`?([^`\n]+)`?\s*$", text, flags=re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    return None if value.lower() in {"", "none", "unassigned"} else value


def _context_pack_section(text: str, heading: str) -> str:
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


def _context_pack_verification_commands(text: str) -> list[str]:
    section = _context_pack_section(text, "Verification Commands")
    commands = re.findall(r"`([^`]+)`", section)
    return _dedupe(command for command in commands if _looks_like_command(command))


def _next_native_workflow_path(root: Path, task: dict[str, Any]) -> tuple[str, Path]:
    workflow_dir = root / "agent" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    preferred = _number_from_task_id(str(task.get("id") or "")) or _next_workflow_number(workflow_dir)
    title_slug = slugify(str(task.get("title") or "workflow"), fallback="workflow")
    number = preferred
    while True:
        workflow_id = f"W-{number:03d}"
        path = workflow_dir / f"{workflow_id}-{title_slug}.md"
        if not path.exists():
            return workflow_id, path
        parsed = parse_workflow_file(root, Path(_relative(root, path)))
        if parsed.get("task_pack") == task.get("path"):
            return workflow_id, path
        number += 1


def _number_from_task_id(task_id: str) -> int | None:
    match = re.fullmatch(r"T-(\d{3,})", task_id)
    return int(match.group(1)) if match else None


def _next_workflow_number(workflow_dir: Path) -> int:
    highest = 0
    for path in workflow_dir.glob("W-*.md"):
        match = re.match(r"W-(\d{3,})", path.stem)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _workflow_id_from_path(path: Path) -> str:
    match = re.match(r"(W-\d{3,})", path.stem)
    return match.group(1) if match else "W-000"


def _write_native_workflow(root: Path, path: Path, task: dict[str, Any], *, workflow_id: str) -> None:
    timestamp = utc_now_iso()
    allowed_paths = _dedupe(task.get("allowed_paths") or [])
    verification_commands = _dedupe(task.get("verification_commands") or [])
    frontmatter = [
        "---",
        f"workflow_id: {workflow_id}",
        "display_name: Execution Plan",
        f"task_pack: {task['path']}",
        "status: planned",
        "current_stage: planning",
        f"stream: {task.get('stream') or 'unassigned'}",
        f"milestone: {task.get('milestone') or 'unassigned'}",
        f"slice: {task.get('slice') or 'unassigned'}",
        f"branch: {task.get('branch') or 'unassigned'}",
        f"created_at: {timestamp}",
        f"updated_at: {timestamp}",
        "allowed_paths:",
    ]
    frontmatter.extend(f"  - {item}" for item in (allowed_paths or ["docs/**"]))
    frontmatter.append("verification_commands:")
    if verification_commands:
        frontmatter.extend(f"  - {command}" for command in verification_commands)
    frontmatter.extend(
        [
            "required_gates:",
            "  - context",
            "  - path",
            "  - verification",
            "  - review",
            "  - writeback",
            "---",
            "",
        ]
    )
    text = "\n".join(
        [
            *frontmatter,
            f"# Workflow {workflow_id}: {task['title']}",
            "",
            "## Linked Task Pack",
            "",
            f"`{task['path']}`",
            "",
            "## Objective",
            "",
            str(task.get("goal") or task["title"]).strip(),
            "",
            "## Plan",
            "",
            "1. Confirm the task context, requirements, and allowed paths.",
            "2. Implement the required change inside the task scope.",
            "3. Run verification and record the result.",
            "4. Complete review and write-back evidence.",
            "",
            "## Implementation Loop",
            "",
            "### Iteration 1",
            "",
            "- Goal: Implement the first scoped change.",
            "- Status: pending",
            "- Notes:",
            "",
            "## Verification Plan",
            "",
            *(_fenced_commands(verification_commands) if verification_commands else ["- Add verification commands before execution if the task does not declare them."]),
            "",
            "## Review Checklist",
            "",
            "- [ ] Path scope respected",
            "- [ ] Verification evidence recorded",
            "- [ ] Review evidence recorded",
            "- [ ] Handoff and roadmap write-back complete",
            "",
            "## Completion Checklist",
            "",
            "- [ ] `agent/handoff.yml` updated",
            "- [ ] `agent/task-ledger.yml` updated",
            "- [ ] `docs/ROADMAP.md` regenerated",
            "- [ ] Final summary written",
            "",
        ]
    )
    path.write_text(text, encoding="utf-8")


def _fenced_commands(commands: list[str]) -> list[str]:
    return ["```bash", *commands, "```"]


def _write_task_workflow_link(task_path: Path, workflow_path: str) -> None:
    text = task_path.read_text(encoding="utf-8")
    replacement = f"Workflow: `{workflow_path}`"
    updated, count = re.subn(r"^Workflow:\s*`?[^`\n]+`?\s*$", replacement, text, count=1, flags=re.MULTILINE)
    if count == 0:
        updated, count = re.subn(r"^(Branch:\s*`?[^`\n]+`?\s*)$", rf"\1\n{replacement}", text, count=1, flags=re.MULTILINE)
    if count == 0:
        lines = text.splitlines()
        lines.insert(1, replacement)
        updated = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    task_path.write_text(updated, encoding="utf-8")


def _plan_result(
    task: dict[str, Any],
    workflow_path: str,
    *,
    created: bool,
    updated_task: bool,
) -> dict[str, Any]:
    return {
        "schema": WORKFLOW_PLAN_RESULT_SCHEMA,
        "task_pack": task["path"],
        "task_id": task["id"],
        "workflow_path": workflow_path,
        "workflow_id": _workflow_id_from_path(Path(workflow_path)),
        "created": created,
        "updated_task": updated_task,
        "status": "planned",
        "next_command": f"aspec run loop {task['path']}",
    }


def _metadata_values(metadata: dict[str, Any], keys: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(item for item in value if isinstance(item, str))
    return values


def _first_string(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return None


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+)$", line.strip())
        if match:
            return match.group(1).strip()
    return None


def _first_json_string(value: Any, keys: tuple[str, ...]) -> str | None:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
            if isinstance(candidate, dict):
                nested = _first_json_string(candidate, keys)
                if nested:
                    return nested
        for item in value.values():
            nested = _first_json_string(item, keys)
            if nested:
                return nested
    if isinstance(value, list):
        for item in value:
            nested = _first_json_string(item, keys)
            if nested:
                return nested
    return None


def _json_values_by_key(value: Any, keys: set[str]) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in keys:
                found.extend(_flatten_strings(item))
            found.extend(_json_values_by_key(item, keys))
    elif isinstance(value, list):
        for item in value:
            found.extend(_json_values_by_key(item, keys))
    return found


def _flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [item for child in value for item in _flatten_strings(child)]
    if isinstance(value, dict):
        return [item for child in value.values() for item in _flatten_strings(child)]
    return []


def _near_verify(lines: list[str], index: int) -> bool:
    for previous in lines[max(0, index - 4) : index]:
        if previous.strip().startswith("verify:"):
            return True
    return False


def _normalize_verification_command(
    value: str,
    *,
    historical_evidence: list[str],
    warnings: list[str],
) -> str | None:
    value = _strip_quotes(value.strip())
    if not value:
        return None
    if _looks_like_historical_output(value):
        historical_evidence.append(value[:1000])
        warnings.append("Ignored historical command output while extracting verification commands.")
        first_line = value.splitlines()[0].strip()
        if (
            first_line != value
            and _looks_like_command(first_line)
            and not _looks_like_historical_output(first_line)
        ):
            return first_line
        return None
    if not _looks_like_command(value):
        return None
    return value


def _looks_like_command(value: str) -> bool:
    return bool(value.strip()) and any(token in value for token in (" ", "-m", "pytest", "unittest", "npm", "pnpm"))


def _normalize_path_candidate(root: Path, value: str, *, warnings: list[str] | None) -> str | None:
    original = value
    value = _strip_quotes(value.strip().strip("`").strip())
    if "::" in value:
        value = value.split("::", 1)[0]

    path = Path(value)
    if path.is_absolute():
        try:
            value = str(path.resolve().relative_to(root.resolve()))
        except ValueError:
            if warnings is not None:
                warnings.append(f"Ignored absolute path outside the repository: {original!r}.")
            return None

    if _invalid_path_reason(value):
        if warnings is not None:
            warnings.append(f"Ignored non-path token from workflow extraction: {original!r}.")
        return None
    if not _looks_like_path(value):
        return None

    normalized = _normalize_relative_path_text(value)
    if _invalid_path_reason(normalized):
        if warnings is not None:
            warnings.append(f"Ignored non-path token from workflow extraction: {original!r}.")
        return None
    if _looks_like_branch_ref(root, normalized):
        if warnings is not None:
            warnings.append(f"Ignored branch-like token from workflow extraction: {original!r}.")
        return None
    return normalized


def _invalid_path_reason(value: str) -> str | None:
    if not value:
        return "empty"
    if "\n" in value or "\r" in value:
        return "multiline"
    if " " in value or value.startswith(("http://", "https://", "$")):
        return "not-path"
    if value.startswith("<") or value.endswith(">"):
        return "placeholder"
    if any(token in value for token in (">", "<", "|")):
        return "shell-token"
    if re.fullmatch(r"\d+(?:\.\d+)?s", value):
        return "elapsed-time"
    lowered = value.lower()
    if "traceback" in lowered or lowered.startswith(("failed", "error", "assertionerror")):
        return "command-output"
    if any(token in lowered for token in ("/pytest-", "pytest-of-")):
        return "temp-path"
    if lowered.startswith(("private/var/", "var/folders/", "tmp/")):
        return "temp-path"
    if lowered.startswith(".hotl/"):
        return "local-evidence"
    return None


def _looks_like_historical_output(value: str) -> bool:
    lowered = value.lower()
    return "\n" in value or "traceback" in lowered or bool(
        re.search(r"(?m)^(failed|error|assertionerror)\b", value, flags=re.IGNORECASE)
    )


def _looks_like_branch_ref(root: Path, value: str) -> bool:
    if (root / value).exists():
        return False
    branch_re = r"(?:codex|feature|feat|fix|bugfix|chore|hotfix|release)/[A-Za-z0-9._/-]+"
    return bool(re.fullmatch(branch_re, value))


def _looks_like_path(value: str) -> bool:
    value = value.strip().strip("`").strip()
    if not value or " " in value or value.startswith(("http://", "https://", "$")):
        return False
    if value.startswith("<") or value.endswith(">"):
        return False
    return "/" in value or bool(re.search(r"\.[A-Za-z0-9]{1,8}$", value)) or any(char in value for char in "*?")


def _normalize_optional_path(root: Path, value: str | None) -> str | None:
    if not value or not _looks_like_path(value):
        return None
    path = Path(value)
    if path.is_absolute():
        try:
            return str(path.resolve().relative_to(root))
        except ValueError:
            return None
    return _normalize_relative_path_text(str(path))


def _resolve_under_root(root: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else root / path
    candidate = candidate.resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Workflow file must be inside the project root: {path}") from exc
    if not candidate.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")
    if not candidate.is_file():
        raise ValueError(f"Workflow path is not a file: {path}")
    return candidate


def _relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")


def _title_from_filename(path: Path) -> str:
    return path.stem.replace("-", " ").replace("_", " ").strip().title()


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _normalize_relative_path_text(value: str) -> str:
    value = value.replace("\\", "/")
    while value.startswith("./"):
        value = value[2:]
    return value


def _dedupe(values: Any) -> list[str]:
    out: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        normalized = _normalize_relative_path_text(value.strip())
        if normalized and normalized not in out:
            out.append(normalized)
    return out
