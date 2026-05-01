from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .connectors import ConnectorFetchError, fetch_source
from .intake import import_candidate
from .io import load_data, read_text, sha256_text, utc_now_iso, write_data
from .paths import slugify
from .spec_document import ALLOWED_CLASSIFICATIONS, ALLOWED_KINDS, ALLOWED_STORAGE_MODES


SOURCE_REGISTRY_SCHEMA = "agentspec.source_registry.v0"
SOURCE_REGISTRY_VALIDATION_SCHEMA = "agentspec.source_registry.validation.v0"
SOURCE_ADD_SCHEMA = "agentspec.source.add.v0"
SOURCE_LIST_SCHEMA = "agentspec.source.list.v0"
SOURCE_CHECK_SCHEMA = "agentspec.source.check.v0"

CHECK_STATUSES = ("unchanged", "changed", "failed", "policy-blocked")
_RETRYABLE_EXCEPTIONS: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError)


@dataclass(frozen=True)
class RegistryIssue:
    path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "code": self.code,
            "message": self.message,
        }


class SourceRegistryValidationError(ValueError):
    def __init__(self, issues: list[RegistryIssue]):
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))

    def to_dict(self) -> dict[str, Any]:
        return _validation_report(self.issues)


def add_source_record(
    root: Path,
    *,
    source_key: str,
    remote_uri: str,
    kind: str,
    classification: str,
    storage_mode: str,
    poll_cadence: str | None = None,
) -> dict[str, Any]:
    registry = load_source_registry(root)
    existing_record = _find_registry_record(registry["sources"], source_key)
    accepted_source = _accepted_source_for(root, source_key)
    record: dict[str, Any] = {
        "source_key": source_key,
        "kind": kind,
        "remote_uri": remote_uri,
        "classification": classification,
        "storage_mode": storage_mode,
    }
    if accepted_source:
        record["accepted_snapshot_id"] = accepted_source.get("id")
        if accepted_source.get("remote_version") or accepted_source.get("version"):
            record["last_seen_remote_version"] = (
                accepted_source.get("remote_version") or accepted_source.get("version")
            )
        if accepted_source.get("content_hash"):
            record["last_seen_content_hash"] = accepted_source["content_hash"]
    if poll_cadence:
        record["poll"] = {"enabled": True, "cadence": poll_cadence}
    elif existing_record and existing_record.get("poll"):
        record["poll"] = existing_record["poll"]
    if not accepted_source and existing_record:
        for field in (
            "accepted_snapshot_id",
            "last_seen_remote_version",
            "last_seen_content_hash",
        ):
            if existing_record.get(field) is not None:
                record[field] = existing_record[field]

    _raise_if_invalid(record)
    sources = list(registry["sources"])
    action = "created"
    for index, existing in enumerate(sources):
        if existing.get("source_key") == source_key:
            sources[index] = record
            action = "updated"
            break
    else:
        sources.append(record)

    write_data(_registry_path(root), {"schema": SOURCE_REGISTRY_SCHEMA, "sources": sources})
    return {
        "schema": SOURCE_ADD_SCHEMA,
        "action": action,
        "record": record,
    }


def list_source_records(root: Path) -> dict[str, Any]:
    registry = load_source_registry(root)
    return {
        "schema": SOURCE_LIST_SCHEMA,
        "sources": registry["sources"],
    }


def check_registered_sources(
    root: Path,
    *,
    source_key: str | None = None,
    all_sources: bool = False,
    as_candidate: bool = False,
) -> dict[str, Any]:
    registry = load_source_registry(root)
    if all_sources:
        selected = registry["sources"]
    else:
        if not source_key:
            raise ValueError("source check requires a source key unless --all is set.")
        selected = [
            record
            for record in registry["sources"]
            if record.get("source_key") == source_key
        ]
        if not selected:
            raise ValueError(f"Registered source not found: {source_key}")

    results = [
        _check_one_source(root, record, as_candidate=as_candidate)
        for record in selected
    ]
    summary = {
        status: sum(1 for result in results if result.get("status") == status)
        for status in CHECK_STATUSES
    }
    return {
        "schema": SOURCE_CHECK_SCHEMA,
        "checked_at": utc_now_iso(),
        "summary": summary,
        "results": results,
    }


def source_check_exit_code(result: Mapping[str, Any]) -> int:
    summary = result.get("summary", {})
    if not isinstance(summary, Mapping):
        return 1
    return 1 if summary.get("failed", 0) or summary.get("policy-blocked", 0) else 0


def format_source_list(payload: Mapping[str, Any]) -> str:
    sources = payload.get("sources", [])
    if not sources:
        return "No registered sources."
    lines = ["Registered sources:"]
    for record in sources:
        if not isinstance(record, Mapping):
            continue
        lines.append(
            "- "
            f"{record.get('source_key', '-')} "
            f"{record.get('kind', '-')} "
            f"{record.get('remote_uri', '-')}"
        )
    return "\n".join(lines)


def format_source_check(payload: Mapping[str, Any]) -> str:
    lines = ["Source check:"]
    for result in payload.get("results", []):
        if not isinstance(result, Mapping):
            continue
        line = (
            f"- {result.get('source_key', '-')}: {result.get('status', '-')}"
            f" ({result.get('current_content_hash') or result.get('error', {}).get('message', '-')})"
        )
        lines.append(line)
        next_command = result.get("next_command")
        if next_command:
            lines.append(f"  Next: {next_command}")
    return "\n".join(lines)


def load_source_registry(root: Path) -> dict[str, Any]:
    raw = load_data(_registry_path(root), {"schema": SOURCE_REGISTRY_SCHEMA, "sources": []})
    if raw is None:
        raw = {"schema": SOURCE_REGISTRY_SCHEMA, "sources": []}
    if isinstance(raw, list):
        sources = raw
    elif isinstance(raw, dict):
        if raw.get("schema") not in {None, SOURCE_REGISTRY_SCHEMA}:
            raise SourceRegistryValidationError(
                [
                    RegistryIssue(
                        path="schema",
                        code="invalid_schema",
                        message=f"source registry schema must be {SOURCE_REGISTRY_SCHEMA}.",
                    )
                ]
            )
        sources = raw.get("sources", [])
    else:
        raise SourceRegistryValidationError(
            [
                RegistryIssue(
                    path="$",
                    code="invalid_type",
                    message="source registry must be an object or list.",
                )
            ]
        )

    if not isinstance(sources, list):
        raise SourceRegistryValidationError(
            [
                RegistryIssue(
                    path="sources",
                    code="invalid_type",
                    message="source registry sources must be a list.",
                )
            ]
        )
    normalized: list[dict[str, Any]] = []
    issues: list[RegistryIssue] = []
    seen_keys: dict[str, int] = {}
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            issues.append(
                RegistryIssue(
                    path=f"sources[{index}]",
                    code="invalid_type",
                    message="source registry entry must be an object.",
                )
            )
            continue
        source_key = source.get("source_key")
        if isinstance(source_key, str) and source_key in seen_keys:
            issues.append(
                RegistryIssue(
                    path=f"sources[{index}].source_key",
                    code="duplicate_source_key",
                    message=f"Duplicate source_key: {source_key}.",
                )
            )
        elif isinstance(source_key, str):
            seen_keys[source_key] = index
        normalized.append(source)
    if issues:
        raise SourceRegistryValidationError(issues)
    return {
        "schema": SOURCE_REGISTRY_SCHEMA,
        "sources": normalized,
    }


def _check_one_source(root: Path, record: Mapping[str, Any], *, as_candidate: bool) -> dict[str, Any]:
    source_key = str(record.get("source_key", ""))
    base = {
        "source_key": source_key or "-",
        "kind": record.get("kind"),
        "remote_uri": record.get("remote_uri"),
    }
    policy_errors = _validation_issues(record)
    if policy_errors:
        return {
            **base,
            "status": "policy-blocked",
            "policy_errors": [issue.to_dict() for issue in policy_errors],
        }

    try:
        current = _fetch_current_source(root, record)
    except Exception as exc:
        return {
            **base,
            "status": "failed",
            "error": _error_payload(exc),
        }

    accepted_source = _accepted_source_for(
        root,
        source_key,
        accepted_snapshot_id=record.get("accepted_snapshot_id"),
    )
    baseline_hash = record.get("last_seen_content_hash")
    if not baseline_hash and accepted_source:
        baseline_hash = accepted_source.get("content_hash")
    accepted_snapshot_id = record.get("accepted_snapshot_id")
    if not accepted_snapshot_id and accepted_source:
        accepted_snapshot_id = accepted_source.get("id")

    status = (
        "unchanged"
        if baseline_hash and baseline_hash == current["content_hash"]
        else "changed"
    )
    result: dict[str, Any] = {
        **base,
        "status": status,
        "accepted_snapshot_id": accepted_snapshot_id,
        "baseline_content_hash": baseline_hash,
        "current_content_hash": current["content_hash"],
        "current_remote_version": current.get("remote_version"),
    }

    if status == "changed":
        result["next_command"] = f"aspec source check {source_key} --as-candidate --json"
        if as_candidate:
            try:
                candidate = import_candidate(
                    root,
                    _source_input_path(root, str(record["remote_uri"])),
                    kind=str(record["kind"]),
                    source_key=source_key,
                    classification=str(record["classification"]),
                    storage_mode=str(record["storage_mode"]),
                )
            except Exception as exc:
                return {
                    **base,
                    "status": "failed",
                    "accepted_snapshot_id": accepted_snapshot_id,
                    "baseline_content_hash": baseline_hash,
                    "current_content_hash": current["content_hash"],
                    "error": _error_payload(exc),
                }
            result["candidate_snapshot_id"] = candidate["snapshot_id"]
            result["candidate_path"] = candidate["candidate_path"]
            result["next_command"] = (
                f"aspec intake diff {candidate['snapshot_id']} --baseline accepted --json"
            )
    return result


def _fetch_current_source(root: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    kind = str(record["kind"])
    remote_uri = str(record["remote_uri"])
    if kind in {"markdown", "openapi", "yaml", "html"}:
        source_path = _source_input_path(root, remote_uri)
        if not source_path.exists():
            raise FileNotFoundError(f"Source document not found: {source_path}")
        text = read_text(source_path)
        return {
            "content_hash": sha256_text(text),
            "remote_version": _openapi_version(text) if kind == "openapi" else None,
        }
    if kind == "pdf":
        source_path = _source_input_path(root, remote_uri)
        if not source_path.exists():
            raise FileNotFoundError(f"Source document not found: {source_path}")
        return {
            "content_hash": _sha256_bytes(source_path.read_bytes()),
            "remote_version": None,
        }
    if kind == "confluence":
        fetched = fetch_source(kind, _connector_uri(root, remote_uri))
        return {
            "content_hash": sha256_text(fetched.body),
            "remote_version": fetched.remote_version,
        }
    raise ValueError(f"source check currently supports supported registry kinds only; got {kind!r}.")


def _source_input_path(root: Path, remote_uri: str) -> Path:
    path = Path(remote_uri)
    return path if path.is_absolute() else root / path


def _connector_uri(root: Path, remote_uri: str) -> str:
    if "://" in remote_uri:
        return remote_uri
    return str(_source_input_path(root, remote_uri))


def _find_registry_record(
    sources: list[dict[str, Any]],
    source_key: str,
) -> dict[str, Any] | None:
    for record in sources:
        if record.get("source_key") == source_key:
            return record
    return None


def _accepted_source_for(
    root: Path,
    source_key: str,
    *,
    accepted_snapshot_id: Any | None = None,
) -> dict[str, Any] | None:
    sources = load_data(root / "docs" / "source" / "sources.yml", []) or []
    for source in sources:
        if not isinstance(source, dict):
            continue
        if source.get("state", "accepted") != "accepted":
            continue
        if accepted_snapshot_id and source.get("id") == accepted_snapshot_id:
            return source
    for source in sources:
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


def _validation_issues(record: Mapping[str, Any]) -> list[RegistryIssue]:
    issues: list[RegistryIssue] = []
    required = ("source_key", "kind", "remote_uri", "classification", "storage_mode")
    for field in required:
        if not record.get(field):
            issues.append(_issue(field, "required", f"Missing required field: {field}."))

    source_key = record.get("source_key")
    if source_key is not None and (not isinstance(source_key, str) or not source_key.strip()):
        issues.append(_issue("source_key", "invalid_source_key", "source_key must be a non-empty string."))
    remote_uri = record.get("remote_uri")
    if remote_uri is not None and (not isinstance(remote_uri, str) or not remote_uri.strip()):
        issues.append(_issue("remote_uri", "invalid_remote_uri", "remote_uri must be a non-empty string."))

    _validate_enum(record, "kind", ALLOWED_KINDS, "invalid_kind", issues)
    _validate_enum(record, "classification", ALLOWED_CLASSIFICATIONS, "invalid_classification", issues)
    _validate_enum(record, "storage_mode", ALLOWED_STORAGE_MODES, "invalid_storage_mode", issues)
    _validate_storage_policy(record, issues)
    return issues


def _raise_if_invalid(record: Mapping[str, Any]) -> None:
    issues = _validation_issues(record)
    if issues:
        raise SourceRegistryValidationError(issues)


def _validate_enum(
    record: Mapping[str, Any],
    field: str,
    allowed: frozenset[str],
    code: str,
    issues: list[RegistryIssue],
) -> None:
    value = record.get(field)
    if value is None:
        return
    if value not in allowed:
        issues.append(_issue(field, code, f"{field} must be one of {sorted(allowed)}."))


def _validate_storage_policy(record: Mapping[str, Any], issues: list[RegistryIssue]) -> None:
    classification = record.get("classification")
    storage_mode = record.get("storage_mode")
    if classification not in ALLOWED_CLASSIFICATIONS or storage_mode not in ALLOWED_STORAGE_MODES:
        return
    allowed = _allowed_storage_modes(str(classification))
    if storage_mode not in allowed:
        issues.append(
            _issue(
                "storage_mode",
                "storage_policy",
                f"storage_mode {storage_mode!r} is not allowed for classification {classification!r}.",
            )
        )


def _allowed_storage_modes(classification: str) -> frozenset[str]:
    if classification == "public":
        return frozenset({"committed", "pointer-only", "enterprise-object-store"})
    if classification == "internal":
        return frozenset(
            {"committed", "pointer-only", "local-secure-cache", "enterprise-object-store"}
        )
    if classification == "confidential":
        return frozenset({"pointer-only", "local-secure-cache", "enterprise-object-store"})
    return frozenset({"pointer-only", "enterprise-object-store"})


def _validation_report(issues: list[RegistryIssue]) -> dict[str, Any]:
    return {
        "schema": SOURCE_REGISTRY_VALIDATION_SCHEMA,
        "valid": not issues,
        "errors": [issue.to_dict() for issue in issues],
    }


def _issue(path: str, code: str, message: str) -> RegistryIssue:
    return RegistryIssue(path=path, code=code, message=message)


def _error_payload(exc: BaseException) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": type(exc).__name__,
        "message": str(exc),
        "retryable": isinstance(exc, _RETRYABLE_EXCEPTIONS),
    }
    to_dict = getattr(exc, "to_dict", None)
    if callable(to_dict):
        payload["details"] = to_dict()
    if isinstance(exc, ConnectorFetchError):
        payload["retryable"] = False
    return payload


def _openapi_version(text: str) -> str | None:
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(document, dict):
        return None
    info = document.get("info", {})
    if isinstance(info, dict) and info.get("version") is not None:
        return str(info["version"])
    return None


def _sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _registry_path(root: Path) -> Path:
    return root / "docs" / "source" / "source-registry.yml"
