from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .connectors import FetchedSource, fetch_source
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
API_CONTRACT_CHANGE_KINDS = (
    "unchanged",
    "endpoint-added",
    "endpoint-removed",
    "path-changed",
    "method-changed",
    "request-schema-changed",
    "response-schema-changed",
    "auth-scope-changed",
    "enum-changed",
)
_HTTP_METHODS = frozenset(
    {"get", "put", "post", "delete", "patch", "options", "head", "trace"}
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
    source_ref = source_path
    snapshot_id = _next_snapshot_id(root)
    candidate_dir = root / "docs" / "source" / "candidates" / snapshot_id
    if kind == "markdown":
        source_path = source_ref.resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source document not found: {source_path}")
        if source_path.suffix.lower() not in {".md", ".markdown", ".txt"}:
            raise ValueError(
                "Markdown candidate import supports .md, .markdown, and .txt files."
            )
        source_text = read_text(source_path)
        document = _markdown_spec_document(
            source_text,
            source_path=source_path,
            source_key=source_key,
            snapshot_id=snapshot_id,
            classification=classification,
            storage_mode=storage_mode,
        )
    elif kind == "openapi":
        source_path = source_ref.resolve()
        if not source_path.exists():
            raise FileNotFoundError(f"Source document not found: {source_path}")
        if source_path.suffix.lower() not in {".json", ".yaml", ".yml"}:
            raise ValueError(
                "OpenAPI candidate import supports JSON-compatible .json, "
                ".yaml, and .yml files."
            )
        source_text = read_text(source_path)
        document = _openapi_spec_document(
            source_text,
            source_path=source_path,
            source_key=source_key,
            snapshot_id=snapshot_id,
            classification=classification,
            storage_mode=storage_mode,
        )
    elif kind == "confluence":
        connector_ref = (
            str(source_ref.resolve()) if source_ref.exists() else str(source_ref)
        )
        fetched = fetch_source(kind, connector_ref)
        source_text = fetched.body
        document = _connector_spec_document(
            fetched,
            source_key=source_key,
            snapshot_id=snapshot_id,
            kind=kind,
            classification=classification,
            storage_mode=storage_mode,
        )
    else:
        raise ValueError(
            "Candidate import currently supports markdown, openapi, and confluence."
        )

    report = validation_report(document)
    write_data(candidate_dir / "validation.yml", report)
    if not report["valid"]:
        raise SpecDocumentValidationError(_issues_from_report(report))

    write_data(candidate_dir / "spec-document.yml", document)
    write_data(candidate_dir / "sections.yml", document["sections"])
    write_text(candidate_dir / "intake-report.md", _intake_report(document))
    if storage_mode == "committed":
        write_text(candidate_dir / "source.md", source_text)

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
    api_contract_changes = _api_contract_changes(
        _baseline_api_contracts(baseline_source),
        candidate.get("api_contracts", []),
    )
    api_contract_summary = {
        kind: sum(1 for change in api_contract_changes if change["kind"] == kind)
        for kind in API_CONTRACT_CHANGE_KINDS
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
        "api_contract_summary": api_contract_summary,
        "api_contract_changes": api_contract_changes,
        "recommendation": _recommendation(summary, api_contract_summary),
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
    api_summary = diff.get("api_contract_summary") or {}
    if any(api_summary.get(kind, 0) for kind in API_CONTRACT_CHANGE_KINDS):
        lines.append("API Contract Changes:")
        for kind in API_CONTRACT_CHANGE_KINDS:
            lines.append(f"- {kind}: {api_summary.get(kind, 0)}")
    if diff.get("api_contract_changes"):
        lines.append("API Contract Details:")
        for change in diff["api_contract_changes"]:
            lines.append(_format_api_contract_change(change))
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


def _openapi_spec_document(
    source_text: str,
    *,
    source_path: Path,
    source_key: str,
    snapshot_id: str,
    classification: str,
    storage_mode: str,
) -> dict[str, Any]:
    raw_document = _load_json_compatible_openapi(source_text, source_path)
    normalized = _normalize_json_data(raw_document)
    body_source = "source.md" if storage_mode == "committed" else "remote_uri"
    line_count = max(1, len(source_text.splitlines()))
    info = raw_document.get("info", {})
    if not isinstance(info, dict):
        info = {}
    title = str(info.get("title") or source_path.stem)
    remote_version = info.get("version")
    section_body = {
        "openapi": raw_document.get("openapi"),
        "info": info,
        "paths": raw_document.get("paths", {}),
    }
    return {
        "schema": SPEC_DOCUMENT_SCHEMA,
        "source_key": source_key,
        "snapshot_id": snapshot_id,
        "kind": "openapi",
        "title": title,
        "remote_uri": str(source_path),
        "api_version": raw_document.get("openapi"),
        "remote_version": str(remote_version) if remote_version is not None else None,
        "content_hash": sha256_text(source_text),
        "normalized_hash": sha256_text(normalized),
        "fetched_at": utc_now_iso(),
        "classification": classification,
        "storage_mode": storage_mode,
        "sections": [
            {
                "local_id": "D-01",
                "stable_key": f"{source_key}/openapi-contract",
                "heading_path": ["OpenAPI Contract"],
                "content_hash": sha256_text(_normalize_json_data(section_body)),
                "body_ref": f"{body_source}#L1-L{line_count}",
            }
        ],
        "requirements": [],
        "api_contracts": _extract_openapi_contracts(raw_document),
        "open_questions": [],
    }


def _connector_spec_document(
    fetched: FetchedSource,
    *,
    source_key: str,
    snapshot_id: str,
    kind: str,
    classification: str,
    storage_mode: str,
) -> dict[str, Any]:
    body = fetched.body
    sections = sectionize_markdown(body, source_id=snapshot_id)
    body_source = "source.md" if storage_mode == "committed" else "remote_uri"
    return {
        "schema": SPEC_DOCUMENT_SCHEMA,
        "source_key": source_key,
        "snapshot_id": snapshot_id,
        "kind": kind,
        "title": fetched.title or document_title(body, source_key),
        "remote_uri": fetched.remote_uri,
        "remote_version": fetched.remote_version,
        "content_hash": sha256_text(body),
        "normalized_hash": sha256_text(_normalize_markdown(body)),
        "fetched_at": fetched.fetched_at or utc_now_iso(),
        "classification": classification,
        "storage_mode": storage_mode,
        "sections": [
            _spec_section(
                source_key,
                section,
                body_source=body_source,
            )
            for section in sections
        ],
        "requirements": [],
        "api_contracts": [],
        "open_questions": [],
    }


def _load_json_compatible_openapi(source_text: str, source_path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(source_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "OpenAPI intake currently accepts YAML-compatible JSON. "
            f"Could not parse {source_path.name}: {exc.msg}."
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError("OpenAPI source must be a JSON/YAML object.")
    if not parsed.get("openapi"):
        raise ValueError("OpenAPI source must include an openapi version field.")
    if not isinstance(parsed.get("paths"), dict):
        raise ValueError("OpenAPI source must include a paths object.")
    return parsed


def _extract_openapi_contracts(document: dict[str, Any]) -> list[dict[str, Any]]:
    info = document.get("info", {})
    version = info.get("version") if isinstance(info, dict) else None
    contracts: list[dict[str, Any]] = []
    paths = document.get("paths", {})
    if not isinstance(paths, dict):
        return contracts

    for path in sorted(paths):
        path_item = paths[path]
        if not isinstance(path_item, dict):
            continue
        for method in sorted(path_item):
            method_lower = method.lower()
            if method_lower not in _HTTP_METHODS:
                continue
            operation = path_item[method]
            if not isinstance(operation, dict):
                continue
            operation_id = str(operation.get("operationId") or f"{method_lower.upper()} {path}")
            request_schema = _operation_request_schema(operation)
            response_schemas = _operation_response_schemas(operation)
            contracts.append(
                {
                    "operation_id": operation_id,
                    "method": method_lower.upper(),
                    "path": path,
                    "version": str(version) if version is not None else None,
                    "request_schema_hash": _hash_json_data(request_schema),
                    "response_schema_hashes": {
                        status: _hash_json_data(schema)
                        for status, schema in response_schemas.items()
                    },
                    "auth_scopes": _operation_auth_scopes(operation, document),
                    "enum_values": {
                        **_schema_enum_values(request_schema, prefix="request"),
                        **{
                            key: value
                            for status, schema in response_schemas.items()
                            for key, value in _schema_enum_values(
                                schema, prefix=f"response.{status}"
                            ).items()
                        },
                    },
                }
            )
    return contracts


def _operation_request_schema(operation: dict[str, Any]) -> Any:
    request_body = operation.get("requestBody")
    if not isinstance(request_body, dict):
        return {}
    return _content_schema(request_body)


def _operation_response_schemas(operation: dict[str, Any]) -> dict[str, Any]:
    responses = operation.get("responses")
    if not isinstance(responses, dict):
        return {}
    return {
        str(status): _content_schema(response)
        for status, response in sorted(responses.items())
        if isinstance(response, dict)
    }


def _content_schema(container: dict[str, Any]) -> Any:
    content = container.get("content")
    if not isinstance(content, dict) or not content:
        return {}
    media = content.get("application/json")
    if not isinstance(media, dict):
        media = next((item for item in content.values() if isinstance(item, dict)), {})
    schema = media.get("schema") if isinstance(media, dict) else None
    return schema if schema is not None else {}


def _operation_auth_scopes(
    operation: dict[str, Any],
    document: dict[str, Any],
) -> list[str]:
    security = operation.get("security", document.get("security", []))
    scopes: list[str] = []
    if not isinstance(security, list):
        return scopes
    for requirement in security:
        if not isinstance(requirement, dict):
            continue
        for scheme, values in requirement.items():
            if isinstance(values, list) and values:
                scopes.extend(f"{scheme}:{value}" for value in values)
            else:
                scopes.append(str(scheme))
    return sorted(str(scope) for scope in scopes)


def _schema_enum_values(schema: Any, *, prefix: str) -> dict[str, list[Any]]:
    values: dict[str, list[Any]] = {}
    if not isinstance(schema, dict):
        return values

    enum = schema.get("enum")
    if isinstance(enum, list):
        values[prefix] = list(enum)

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, child in sorted(properties.items()):
            values.update(_schema_enum_values(child, prefix=f"{prefix}.{name}"))

    items = schema.get("items")
    if isinstance(items, dict):
        values.update(_schema_enum_values(items, prefix=f"{prefix}[]"))

    for combiner in ("allOf", "anyOf", "oneOf"):
        children = schema.get(combiner)
        if isinstance(children, list):
            for index, child in enumerate(children):
                values.update(
                    _schema_enum_values(child, prefix=f"{prefix}.{combiner}[{index}]")
                )
    return values


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

    record = {
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
    if "api_version" in document:
        record["api_version"] = document.get("api_version")
    if "api_contracts" in document:
        record["api_contracts"] = document.get("api_contracts", [])
    return record


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


def _baseline_api_contracts(baseline_source: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not baseline_source:
        return []
    contracts = baseline_source.get("api_contracts", [])
    if not isinstance(contracts, list):
        return []
    return [contract for contract in contracts if isinstance(contract, dict)]


def _api_contract_changes(
    baseline_contracts: Any,
    candidate_contracts: Any,
) -> list[dict[str, Any]]:
    if not isinstance(baseline_contracts, list):
        baseline_contracts = []
    if not isinstance(candidate_contracts, list):
        candidate_contracts = []

    baseline_by_operation = {
        str(contract.get("operation_id")): contract
        for contract in baseline_contracts
        if isinstance(contract, dict) and contract.get("operation_id")
    }
    candidate_by_operation = {
        str(contract.get("operation_id")): contract
        for contract in candidate_contracts
        if isinstance(contract, dict) and contract.get("operation_id")
    }
    changes: list[dict[str, Any]] = []
    matched_candidates: set[str] = set()

    for operation_id in sorted(baseline_by_operation):
        baseline = baseline_by_operation[operation_id]
        candidate = candidate_by_operation.get(operation_id)
        if candidate is None:
            changes.append(_api_contract_change("endpoint-removed", baseline, None))
            continue

        matched_candidates.add(operation_id)
        per_operation_changes: list[dict[str, Any]] = []
        if baseline.get("path") != candidate.get("path"):
            per_operation_changes.append(
                _api_contract_change("path-changed", baseline, candidate)
            )
        if baseline.get("method") != candidate.get("method"):
            per_operation_changes.append(
                _api_contract_change("method-changed", baseline, candidate)
            )
        if baseline.get("request_schema_hash") != candidate.get("request_schema_hash"):
            per_operation_changes.append(
                _api_contract_change("request-schema-changed", baseline, candidate)
            )
        if baseline.get("response_schema_hashes") != candidate.get("response_schema_hashes"):
            per_operation_changes.append(
                _api_contract_change("response-schema-changed", baseline, candidate)
            )
        if baseline.get("auth_scopes", []) != candidate.get("auth_scopes", []):
            per_operation_changes.append(
                _api_contract_change("auth-scope-changed", baseline, candidate)
            )
        if baseline.get("enum_values", {}) != candidate.get("enum_values", {}):
            per_operation_changes.append(_api_contract_change("enum-changed", baseline, candidate))

        if per_operation_changes:
            changes.extend(per_operation_changes)
        else:
            changes.append(_api_contract_change("unchanged", baseline, candidate))

    for operation_id in sorted(candidate_by_operation):
        if operation_id not in baseline_by_operation and operation_id not in matched_candidates:
            changes.append(
                _api_contract_change("endpoint-added", None, candidate_by_operation[operation_id])
            )
    return changes


def _api_contract_change(
    kind: str,
    baseline: dict[str, Any] | None,
    candidate: dict[str, Any] | None,
) -> dict[str, Any]:
    change: dict[str, Any] = {
        "kind": kind,
        "operation_id": (
            (candidate or {}).get("operation_id")
            or (baseline or {}).get("operation_id")
            or "-"
        ),
    }
    if baseline is not None:
        change["baseline"] = _api_contract_ref(baseline)
    if candidate is not None:
        change["candidate"] = _api_contract_ref(candidate)
    return change


def _api_contract_ref(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "operation_id": contract.get("operation_id"),
        "method": contract.get("method"),
        "path": contract.get("path"),
        "version": contract.get("version"),
        "request_schema_hash": contract.get("request_schema_hash"),
        "response_schema_hashes": contract.get("response_schema_hashes", {}),
        "auth_scopes": contract.get("auth_scopes", []),
        "enum_values": contract.get("enum_values", {}),
    }


def _recommendation(
    summary: dict[str, int],
    api_contract_summary: dict[str, int] | None = None,
) -> str:
    changed = sum(
        count for kind, count in summary.items() if kind != "unchanged"
    )
    if api_contract_summary:
        changed += sum(
            count
            for kind, count in api_contract_summary.items()
            if kind != "unchanged"
        )
    return "needs-review" if changed else "doc-only"


def _format_change(change: dict[str, Any]) -> str:
    kind = change["kind"]
    baseline = change.get("baseline") or {}
    candidate = change.get("candidate") or {}
    local_id = candidate.get("local_id") or baseline.get("local_id") or "-"
    stable_key = candidate.get("stable_key") or baseline.get("stable_key") or "-"
    return f"- {kind}: {local_id} {stable_key}"


def _format_api_contract_change(change: dict[str, Any]) -> str:
    kind = change["kind"]
    operation_id = change.get("operation_id") or "-"
    baseline = change.get("baseline") or {}
    candidate = change.get("candidate") or {}
    baseline_route = _api_route_label(baseline)
    candidate_route = _api_route_label(candidate)
    if baseline_route and candidate_route and baseline_route != candidate_route:
        return f"- {kind}: {operation_id} {baseline_route} -> {candidate_route}"
    return f"- {kind}: {operation_id} {candidate_route or baseline_route or '-'}"


def _api_route_label(contract: dict[str, Any]) -> str:
    method = contract.get("method")
    path = contract.get("path")
    if method and path:
        return f"{method} {path}"
    return ""


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


def _normalize_json_data(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash_json_data(data: Any) -> str:
    return sha256_text(_normalize_json_data(data))


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
