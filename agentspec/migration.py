"""Plan and apply migration of legacy execution artifacts into task packs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .task import create_task_context_pack_from_workflow
from .workflow import build_workflow_contract_status


LEGACY_EXECUTION_MIGRATION_SCHEMA = "agentspec.legacy_execution_migration.v0"


def migrate_legacy_execution(
    root: Path,
    *,
    from_path: str | Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Build or apply a migration plan for legacy execution artifacts."""

    root = root.resolve()
    selected = _selected_legacy_artifacts(root, from_path)
    artifacts: list[dict[str, Any]] = []

    for record in selected:
        artifact = _artifact_plan(record, write=write)
        if write and artifact["action"] == "create_task_pack":
            created = create_task_context_pack_from_workflow(
                root,
                Path(str(record["path"])),
                task_type="migration",
            )
            created_rel = _relative(root, created)
            artifact["action"] = "created_task_pack"
            artifact["created_task_pack"] = created_rel
            artifact["rollback"] = _created_rollback(created_rel, str(record["path"]))
        artifacts.append(artifact)

    return {
        "schema": LEGACY_EXECUTION_MIGRATION_SCHEMA,
        "mode": "write" if write else "dry-run",
        "write": write,
        "from": _normalize_from_path(root, from_path) if from_path else None,
        "summary": _summary(artifacts),
        "artifacts": artifacts,
    }


def format_legacy_execution_migration(result: dict[str, Any]) -> str:
    """Format a legacy execution migration result for terminal output."""

    mode = str(result.get("mode") or "dry-run")
    raw_summary = result.get("summary")
    summary: dict[str, Any] = raw_summary if isinstance(raw_summary, dict) else {}
    raw_artifacts = result.get("artifacts")
    artifacts = [artifact for artifact in raw_artifacts if isinstance(artifact, dict)] if isinstance(raw_artifacts, list) else []
    lines = [
        f"Legacy execution migration plan ({mode})",
        (
            "Artifacts: "
            f"{summary.get('total', 0)} total, "
            f"{summary.get('to_create', 0)} to create, "
            f"{summary.get('created', 0)} created, "
            f"{summary.get('skipped', 0)} skipped."
        ),
    ]

    if not artifacts:
        lines.append("No scanner-recognized legacy execution artifacts found.")

    for artifact in artifacts:
        path = artifact.get("path")
        action = artifact.get("action")
        if action == "create_task_pack":
            lines.append(f"- Would create task pack for {path}.")
            lines.append(f"  Command: {artifact.get('command')}")
            lines.append(f"  Rollback: {artifact.get('rollback')}")
            continue
        if action == "created_task_pack":
            lines.append(f"- Created task pack: {artifact.get('created_task_pack')} from {path}.")
            lines.append(f"  Rollback: {artifact.get('rollback')}")
            continue
        reason = artifact.get("reason") or "already referenced"
        referenced_by = artifact.get("referenced_by") or []
        suffix = f" by {', '.join(referenced_by)}" if referenced_by else ""
        lines.append(f"- Skipped {path}: {reason}{suffix}.")

    if mode == "dry-run" and int(summary.get("to_create", 0) or 0):
        lines.append("Run with --write to apply.")

    return "\n".join(lines)


def _selected_legacy_artifacts(root: Path, from_path: str | Path | None) -> list[dict[str, Any]]:
    status = build_workflow_contract_status(root)
    records = [
        record
        for record in _list(status.get("artifacts"))
        if isinstance(record, dict) and _is_legacy_execution_artifact(record)
    ]

    if from_path is None:
        return records

    target = _normalize_from_path(root, from_path)
    selected = [
        record
        for record in records
        if record.get("path") == target or target in _list(record.get("reference_paths"))
    ]
    if not selected:
        raise ValueError(
            f"{target} is not a scanner-recognized legacy execution artifact. "
            "Supported inputs are docs/**/plans/**workflow.md and .hotl/state/**/*.json."
        )
    return selected


def _artifact_plan(record: dict[str, Any], *, write: bool) -> dict[str, Any]:
    path = str(record.get("path") or "")
    referenced_by = [str(value) for value in _list(record.get("referenced_by")) if value]
    base = {
        "kind": record.get("kind"),
        "path": path,
        "title": record.get("title"),
        "status": record.get("status"),
        "referenced_by": referenced_by,
        "command": record.get("backfill_command") or f"aspec task create --from-workflow {path}",
        "created_task_pack": None,
    }

    if referenced_by or record.get("status") != "orphan":
        return {
            **base,
            "action": "skip",
            "reason": "already referenced",
            "rollback": "No rollback needed; migration did not create or modify artifacts.",
        }

    return {
        **base,
        "action": "create_task_pack",
        "reason": "orphan legacy execution artifact",
        "rollback": _dry_run_rollback(path) if not write else _pending_write_rollback(path),
    }


def _summary(artifacts: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(artifacts),
        "to_create": sum(1 for artifact in artifacts if artifact.get("action") == "create_task_pack"),
        "created": sum(1 for artifact in artifacts if artifact.get("action") == "created_task_pack"),
        "skipped": sum(1 for artifact in artifacts if artifact.get("action") == "skip"),
    }


def _is_legacy_execution_artifact(record: dict[str, Any]) -> bool:
    path = str(record.get("path") or "")
    kind = str(record.get("kind") or "")
    if kind == "state" or path.startswith(".hotl/"):
        return True
    return path.startswith("docs/") and "/plans/" in path and path.endswith("workflow.md")


def _normalize_from_path(root: Path, value: str | Path | None) -> str | None:
    if value is None:
        return None
    path = Path(str(value).strip())
    if not str(path):
        raise ValueError("--from requires a path.")
    candidate = path if path.is_absolute() else root / path
    try:
        rel = candidate.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Migration path must be inside the project root: {value}") from exc
    return str(rel).replace("\\", "/")


def _relative(root: Path, path: Path) -> str:
    return str(path.resolve().relative_to(root)).replace("\\", "/")


def _dry_run_rollback(path: str) -> str:
    return (
        "Remove created task context pack reported by write mode. "
        f"Source workflow {path} is not modified by this migration."
    )


def _pending_write_rollback(path: str) -> str:
    return (
        "Remove the created task context pack if this migration is applied incorrectly. "
        f"Source workflow {path} will not be modified."
    )


def _created_rollback(created_task_pack: str, path: str) -> str:
    return (
        f"Remove created task context pack {created_task_pack}. "
        f"Source workflow {path} was not modified."
    )


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
