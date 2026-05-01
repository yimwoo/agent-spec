from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from .io import load_data, read_text, sha256_text, utc_now_iso, write_data, write_text
from .markdown import document_title, sectionize_markdown
from .paths import ensure_dirs, slugify
from .spec_document import (
    SPEC_DOCUMENT_SCHEMA,
    SpecDocumentValidationError,
    ValidationIssue,
    validation_report,
)


INTAKE_IMPORT_SCHEMA = "agentspec.intake.import.v0"
INTAKE_DIFF_SCHEMA = "agentspec.intake.diff.v0"
INTAKE_PROMOTE_SCHEMA = "agentspec.intake.promote.v0"
SECTION_CHANGE_KINDS = (
    "unchanged",
    "added",
    "removed",
    "renamed",
    "moved",
    "body-changed",
)


def import_candidate(
    root: Path,
    source_path: Path,
    *,
    kind: str,
    source_key: str,
    classification: str,
    storage_mode: str,
) -> dict[str, Any]:
    """Import an external source as a candidate snapshot only."""

    ensure_dirs(root)
    source_path = source_path.resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source document not found: {source_path}")
    if kind != "markdown":
        raise ValueError("Candidate import currently supports markdown only.")
    if source_path.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise ValueError(
            "Markdown candidate import supports .md, .markdown, and .txt files."
        )

    markdown = read_text(source_path)
    snapshot_id = _next_snapshot_id(root)
    candidate_dir = root / "docs" / "source" / "candidates" / snapshot_id
    document = _markdown_spec_document(
        markdown,
        source_path=source_path,
        source_key=source_key,
        snapshot_id=snapshot_id,
        classification=classification,
        storage_mode=storage_mode,
    )
    report = validation_report(document)
    write_data(candidate_dir / "validation.yml", report)
    if not report["valid"]:
        raise SpecDocumentValidationError(_issues_from_report(report))

    write_data(candidate_dir / "spec-document.yml", document)
    write_data(candidate_dir / "sections.yml", document["sections"])
    write_text(candidate_dir / "intake-report.md", _intake_report(document))
    if storage_mode == "committed":
        write_text(candidate_dir / "source.md", markdown)

    return {
        "schema": INTAKE_IMPORT_SCHEMA,
        "snapshot_id": snapshot_id,
        "source_key": source_key,
        "kind": kind,
        "candidate_path": str(candidate_dir.relative_to(root)),
        "validation": report,
    }


def diff_candidate(
    root: Path,
    snapshot_id: str,
    *,
    baseline: str = "accepted",
) -> dict[str, Any]:
    """Diff a candidate snapshot against the accepted baseline."""

    if baseline != "accepted":
        raise ValueError("intake diff currently supports --baseline accepted only.")

    candidate_dir = root / "docs" / "source" / "candidates" / snapshot_id
    candidate = load_data(candidate_dir / "spec-document.yml")
    if not isinstance(candidate, dict):
        raise FileNotFoundError(f"Candidate SpecDocument not found: {snapshot_id}")

    report = validation_report(candidate)
    write_data(candidate_dir / "validation.yml", report)
    if not report["valid"]:
        raise SpecDocumentValidationError(_issues_from_report(report))

    source_key = str(candidate.get("source_key", ""))
    baseline_source = _accepted_source_for(root, source_key)
    baseline_sections = _baseline_sections(root, baseline_source, source_key)
    candidate_sections = [
        _candidate_diff_section(section)
        for section in candidate.get("sections", [])
        if isinstance(section, dict)
    ]
    changes = _section_changes(baseline_sections, candidate_sections)
    summary = {
        kind: sum(1 for change in changes if change["kind"] == kind)
        for kind in SECTION_CHANGE_KINDS
    }
    result = {
        "schema": INTAKE_DIFF_SCHEMA,
        "snapshot_id": snapshot_id,
        "source_key": source_key,
        "baseline": {
            "mode": "accepted",
            "source_id": baseline_source.get("id") if baseline_source else None,
        },
        "summary": summary,
        "changes": changes,
        "recommendation": _recommendation(summary),
    }
    write_data(candidate_dir / "diff.yml", result)
    return result


def promote_candidate(
    root: Path,
    snapshot_id: str,
    *,
    decision: str,
    run_compile: bool = False,
) -> dict[str, Any]:
    """Promote a validated candidate snapshot into accepted source projection."""

    if decision != "accepted":
        raise ValueError("intake promote currently accepts --decision accepted only.")

    candidate_dir = root / "docs" / "source" / "candidates" / snapshot_id
    candidate = load_data(candidate_dir / "spec-document.yml")
    if not isinstance(candidate, dict):
        raise FileNotFoundError(f"Candidate SpecDocument not found: {snapshot_id}")

    report = validation_report(candidate)
    write_data(candidate_dir / "validation.yml", report)
    if not report["valid"]:
        raise SpecDocumentValidationError(_issues_from_report(report))

    source_key = str(candidate["source_key"])
    prior_source = _accepted_source_for(root, source_key)
    promoted_sections = _accepted_sections(candidate)
    source_record = _accepted_source_record(
        root,
        candidate_dir,
        candidate,
        prior_source=prior_source,
    )

    sources_path = root / "docs" / "source" / "sources.yml"
    sources = load_data(sources_path, []) or []
    updated_sources: list[dict[str, Any]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        if source.get("id") == snapshot_id:
            continue
        if prior_source and source.get("id") == prior_source.get("id"):
            superseded = dict(source)
            superseded["source_key"] = source_key
            superseded["state"] = "superseded"
            superseded["superseded_by"] = snapshot_id
            updated_sources.append(superseded)
            continue
        updated_sources.append(source)
    updated_sources.append(source_record)
    write_data(sources_path, updated_sources)

    sections_path = root / "docs" / "source" / "sections.yml"
    existing_sections = load_data(sections_path, []) or []
    retained_sections: list[dict[str, Any]] = []
    superseded_sections: list[dict[str, Any]] = []
    prior_source_id = str(prior_source["id"]) if prior_source and prior_source.get("id") else None
    for section in existing_sections:
        if not isinstance(section, dict):
            continue
        source_id = str(section.get("source_id", ""))
        if source_id == snapshot_id:
            continue
        if (
            prior_source_id
            and source_id == prior_source_id
            and section.get("state", "accepted") == "accepted"
        ):
            superseded_sections.append(
                _superseded_section(
                    section,
                    source_key=source_key,
                    superseded_by_snapshot=snapshot_id,
                )
            )
            continue
        retained_sections.append(section)
    write_data(sections_path, retained_sections + superseded_sections + promoted_sections)

    result = {
        "schema": INTAKE_PROMOTE_SCHEMA,
        "snapshot_id": snapshot_id,
        "source_key": source_key,
        "decision": decision,
        "approval": {
            "mode": "explicit-command",
        },
        "accepted_source": source_record,
        "sections_promoted": len(promoted_sections),
    }
    if run_compile:
        from .compile import compile_project

        compile_result = compile_project(root)
        result["compile"] = {
            "ran": True,
            "spec_shards": len(compile_result["spec_shards"]),
            "requirements": len(compile_result["requirements"]),
            "open_questions": len(compile_result["open_questions"]),
        }
    else:
        result["compile"] = {
            "ran": False,
            "command": "aspec compile",
        }
    return result


def format_diff_report(diff: dict[str, Any]) -> str:
    baseline = diff.get("baseline", {})
    lines = [
        f"Candidate {diff['snapshot_id']} vs accepted {baseline.get('source_id') or '-'}",
        f"Recommendation: {diff['recommendation']}",
        "Summary:",
    ]
    summary = diff.get("summary", {})
    for kind in SECTION_CHANGE_KINDS:
        lines.append(f"- {kind}: {summary.get(kind, 0)}")
    if diff.get("changes"):
        lines.append("Changes:")
        for change in diff["changes"]:
            lines.append(_format_change(change))
    return "\n".join(lines)


def _markdown_spec_document(
    markdown: str,
    *,
    source_path: Path,
    source_key: str,
    snapshot_id: str,
    classification: str,
    storage_mode: str,
) -> dict[str, Any]:
    sections = sectionize_markdown(markdown, source_id=snapshot_id)
    return {
        "schema": SPEC_DOCUMENT_SCHEMA,
        "source_key": source_key,
        "snapshot_id": snapshot_id,
        "kind": "markdown",
        "title": document_title(markdown, source_path.stem),
        "remote_uri": str(source_path),
        "remote_version": None,
        "content_hash": sha256_text(markdown),
        "normalized_hash": sha256_text(_normalize_markdown(markdown)),
        "fetched_at": utc_now_iso(),
        "classification": classification,
        "storage_mode": storage_mode,
        "sections": [
            _spec_section(
                source_key,
                section,
                body_source="source.md"
                if storage_mode == "committed"
                else "remote_uri",
            )
            for section in sections
        ],
        "requirements": [],
        "api_contracts": [],
        "open_questions": [],
    }


def _accepted_source_for(root: Path, source_key: str) -> dict[str, Any] | None:
    for source in load_data(root / "docs" / "source" / "sources.yml", []):
        if not isinstance(source, dict):
            continue
        if source.get("state", "accepted") != "accepted":
            continue
        legacy_title_key = slugify(str(source.get("title", "")), "source")
        if (
            source.get("source_key") == source_key
            or source.get("id") == source_key
            or legacy_title_key == source_key
        ):
            return source
    return None


def _baseline_sections(
    root: Path,
    baseline_source: dict[str, Any] | None,
    source_key: str,
) -> list[dict[str, Any]]:
    if not baseline_source:
        return []
    source_id = baseline_source.get("id")
    sections = []
    for section in load_data(root / "docs" / "source" / "sections.yml", []):
        if not isinstance(section, dict) or section.get("source_id") != source_id:
            continue
        sections.append(_baseline_diff_section(section, source_key))
    return sections


def _accepted_source_record(
    root: Path,
    candidate_dir: Path,
    document: dict[str, Any],
    *,
    prior_source: dict[str, Any] | None,
) -> dict[str, Any]:
    storage_mode = str(document["storage_mode"])
    uri = str(document.get("remote_uri", ""))
    if storage_mode == "committed":
        candidate_source = candidate_dir / "source.md"
        if not candidate_source.exists():
            raise FileNotFoundError(
                f"Committed candidate source body not found: {candidate_source}"
            )
        destination = (
            root
            / "docs"
            / "source"
            / f"{str(document['snapshot_id']).lower()}-{slugify(str(document['source_key']), 'source')}.md"
        )
        write_text(destination, read_text(candidate_source))
        uri = str(destination.relative_to(root))

    return {
        "id": document["snapshot_id"],
        "snapshot_id": document["snapshot_id"],
        "source_key": document["source_key"],
        "kind": document["kind"],
        "uri": uri,
        "remote_uri": document.get("remote_uri"),
        "original_uri": document.get("remote_uri"),
        "title": document.get("title") or document["source_key"],
        "version": document.get("remote_version"),
        "remote_version": document.get("remote_version"),
        "content_hash": document["content_hash"],
        "normalized_hash": document["normalized_hash"],
        "fetched_at": document["fetched_at"],
        "classification": document["classification"],
        "storage_mode": storage_mode,
        "state": "accepted",
        "supersedes": prior_source.get("id") if prior_source else None,
        "candidate_path": str(candidate_dir.relative_to(root)),
    }


def _accepted_sections(document: dict[str, Any]) -> list[dict[str, Any]]:
    source_id = str(document["snapshot_id"])
    source_key = str(document["source_key"])
    sections: list[dict[str, Any]] = []
    for section in document.get("sections", []):
        heading_path = list(section.get("heading_path", []))
        start_line, end_line = _line_range_from_body_ref(str(section.get("body_ref", "")))
        local_id = str(section["local_id"])
        section_id = _source_key_section_id(source_key, local_id)
        parent_local_id = _parent_section_id(local_id)
        sections.append(
            {
                "id": section_id,
                "local_id": local_id,
                "source_id": source_id,
                "source_key": source_key,
                "snapshot_id": source_id,
                "snapshot_section_id": _snapshot_section_id(source_id, local_id),
                "stable_key": section.get("stable_key"),
                "title": heading_path[-1] if heading_path else local_id,
                "heading_path": heading_path,
                "start_line": start_line,
                "end_line": end_line,
                "content_hash": section["content_hash"],
                "parent": _source_key_section_id(source_key, parent_local_id)
                if parent_local_id
                else None,
                "children": [],
                "state": "accepted",
            }
        )

    by_id = {section["id"]: section for section in sections}
    for section in sections:
        parent = section["parent"]
        if parent in by_id:
            by_id[parent]["children"].append(section["id"])
    return sections


def _superseded_section(
    section: dict[str, Any],
    *,
    source_key: str,
    superseded_by_snapshot: str,
) -> dict[str, Any]:
    source_id = str(section.get("source_id", ""))
    local_id = _local_section_id(section)
    snapshot_id = str(section.get("snapshot_id") or source_id)
    snapshot_section_id = str(
        section.get("snapshot_section_id") or _snapshot_section_id(snapshot_id, local_id)
    )
    parent_local_id = _local_section_id({"id": section.get("parent")}) if section.get("parent") else None
    children = [
        _snapshot_section_id(snapshot_id, _local_section_id({"id": child}))
        for child in section.get("children", [])
    ]
    superseded = dict(section)
    superseded.update(
        {
            "id": snapshot_section_id,
            "local_id": local_id,
            "source_key": section.get("source_key") or source_key,
            "snapshot_id": snapshot_id,
            "snapshot_section_id": snapshot_section_id,
            "parent": _snapshot_section_id(snapshot_id, parent_local_id)
            if parent_local_id
            else None,
            "children": children,
            "state": "superseded",
            "superseded_by": _source_key_section_id(source_key, local_id),
            "superseded_by_snapshot": superseded_by_snapshot,
        }
    )
    return superseded


def _source_key_section_id(source_key: str, local_id: str) -> str:
    return f"{source_key}:{local_id}"


def _snapshot_section_id(snapshot_id: str, local_id: str) -> str:
    return f"{snapshot_id}:{local_id}"


def _local_section_id(section: dict[str, Any]) -> str:
    local_id = section.get("local_id")
    if isinstance(local_id, str) and local_id:
        return local_id
    section_id = str(section.get("id", ""))
    return section_id.split(":", 1)[1] if ":" in section_id else section_id


def _line_range_from_body_ref(body_ref: str) -> tuple[int, int]:
    match = re.search(r"#L(\d+)-L(\d+)$", body_ref)
    if not match:
        raise ValueError(f"Cannot promote section without line range body_ref: {body_ref}")
    return int(match.group(1)), int(match.group(2))


def _parent_section_id(local_id: str) -> str | None:
    if "." not in local_id:
        return None
    return local_id.rsplit(".", 1)[0]


def _baseline_diff_section(
    section: dict[str, Any],
    source_key: str,
) -> dict[str, Any]:
    local_id = str(section.get("local_id") or section.get("id"))
    heading_path = list(section.get("heading_path", []))
    return {
        "local_id": local_id,
        "stable_key": str(
            section.get("stable_key") or _stable_section_key(source_key, heading_path)
        ),
        "heading_path": heading_path,
        "content_hash": str(section.get("content_hash", "")),
        "body_ref": str(section.get("body_ref", "")),
    }


def _candidate_diff_section(section: dict[str, Any]) -> dict[str, Any]:
    return {
        "local_id": str(section.get("local_id", "")),
        "stable_key": str(section.get("stable_key", "")),
        "heading_path": list(section.get("heading_path", [])),
        "content_hash": str(section.get("content_hash", "")),
        "body_ref": str(section.get("body_ref", "")),
    }


def _section_changes(
    baseline_sections: list[dict[str, Any]],
    candidate_sections: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    baseline_by_stable = {
        section["stable_key"]: (index, section)
        for index, section in enumerate(baseline_sections)
    }
    baseline_by_local = {
        section["local_id"]: (index, section)
        for index, section in enumerate(baseline_sections)
    }
    matched: set[int] = set()
    changes: list[dict[str, Any]] = []

    for candidate in candidate_sections:
        stable_key = candidate["stable_key"]
        local_id = candidate["local_id"]
        if stable_key in baseline_by_stable:
            index, baseline = baseline_by_stable[stable_key]
            matched.add(index)
            if baseline["local_id"] != local_id:
                changes.append(_change("moved", baseline, candidate))
            elif baseline["content_hash"] != candidate["content_hash"]:
                changes.append(_change("body-changed", baseline, candidate))
            else:
                changes.append(_change("unchanged", baseline, candidate))
            continue

        if local_id in baseline_by_local:
            index, baseline = baseline_by_local[local_id]
            matched.add(index)
            changes.append(_change("renamed", baseline, candidate))
            continue

        changes.append(_change("added", None, candidate))

    for index, baseline in enumerate(baseline_sections):
        if index not in matched:
            changes.append(_change("removed", baseline, None))
    return changes


def _change(
    kind: str,
    baseline: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    change: dict[str, Any] = {"kind": kind}
    if baseline is not None:
        change["baseline"] = baseline
    if candidate is not None:
        change["candidate"] = candidate
    return change


def _recommendation(summary: dict[str, int]) -> str:
    changed = sum(
        count for kind, count in summary.items() if kind != "unchanged"
    )
    return "needs-review" if changed else "doc-only"


def _format_change(change: dict[str, Any]) -> str:
    kind = change["kind"]
    baseline = change.get("baseline") or {}
    candidate = change.get("candidate") or {}
    local_id = candidate.get("local_id") or baseline.get("local_id") or "-"
    stable_key = candidate.get("stable_key") or baseline.get("stable_key") or "-"
    return f"- {kind}: {local_id} {stable_key}"


def _spec_section(
    source_key: str,
    section: dict[str, Any],
    *,
    body_source: str,
) -> dict[str, Any]:
    start_line = int(section["start_line"])
    end_line = int(section["end_line"])
    return {
        "local_id": section["id"],
        "stable_key": _stable_section_key(source_key, section["heading_path"]),
        "heading_path": section["heading_path"],
        "content_hash": section["content_hash"],
        "body_ref": f"{body_source}#L{start_line}-L{end_line}",
    }


def _stable_section_key(source_key: str, heading_path: list[str]) -> str:
    parts = [slugify(part, "section") for part in heading_path]
    return f"{source_key}/{'/'.join(parts)}"


def _normalize_markdown(markdown: str) -> str:
    normalized = "\n".join(line.rstrip() for line in markdown.splitlines()).strip()
    return normalized + "\n" if normalized else ""


def _next_snapshot_id(root: Path) -> str:
    existing_ids: list[str] = []
    for source in load_data(root / "docs" / "source" / "sources.yml", []):
        source_id = source.get("id")
        if isinstance(source_id, str):
            existing_ids.append(source_id)
    candidates_dir = root / "docs" / "source" / "candidates"
    if candidates_dir.exists():
        existing_ids.extend(
            path.name for path in candidates_dir.iterdir() if path.is_dir()
        )

    highest = 0
    for existing_id in existing_ids:
        if existing_id.startswith("SRC-") and existing_id[4:].isdigit():
            highest = max(highest, int(existing_id[4:]))
    return f"SRC-{highest + 1:04d}"


def _intake_report(document: dict[str, Any]) -> str:
    return (
        f"# Intake Report: {document['snapshot_id']}\n\n"
        f"- Source key: `{document['source_key']}`\n"
        f"- Kind: `{document['kind']}`\n"
        f"- Sections: {len(document['sections'])}\n"
        f"- Classification: `{document['classification']}`\n"
        f"- Storage mode: `{document['storage_mode']}`\n"
    )


def _issues_from_report(report: dict[str, Any]) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            path=str(error.get("path", "")),
            code=str(error.get("code", "")),
            message=str(error.get("message", "")),
        )
        for error in report.get("errors", [])
        if isinstance(error, dict)
    ]
