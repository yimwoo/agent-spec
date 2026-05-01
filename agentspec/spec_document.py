from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
import re


SPEC_DOCUMENT_SCHEMA = "agentspec.spec_document.v0"
SPEC_DOCUMENT_VALIDATION_SCHEMA = "agentspec.spec_document.validation.v0"

ALLOWED_KINDS = frozenset(
    {"markdown", "html", "pdf", "yaml", "openapi", "confluence"}
)
ALLOWED_CLASSIFICATIONS = frozenset(
    {"public", "internal", "confidential", "restricted"}
)
ALLOWED_STORAGE_MODES = frozenset(
    {"committed", "pointer-only", "local-secure-cache", "enterprise-object-store"}
)

_HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
_SNAPSHOT_ID_RE = re.compile(r"^SRC-\d{4,}$")
_SECTION_ID_RE = re.compile(r"^D-\d{2}(?:\.\d+)*$")
_SOURCE_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*$")

_REQUIRED_TOP_LEVEL = (
    "schema",
    "source_key",
    "snapshot_id",
    "kind",
    "content_hash",
    "normalized_hash",
    "fetched_at",
    "classification",
    "storage_mode",
    "sections",
)

_REQUIRED_SECTION_FIELDS = (
    "local_id",
    "stable_key",
    "heading_path",
    "content_hash",
    "body_ref",
)

_OPTIONAL_LIST_FIELDS = ("requirements", "api_contracts", "open_questions")


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "path": self.path,
            "code": self.code,
            "message": self.message,
        }


class SpecDocumentValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]):
        self.issues = issues
        super().__init__("; ".join(issue.message for issue in issues))

    def to_dict(self) -> dict[str, Any]:
        return _report(self.issues)


def validate_spec_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a SpecDocument, raising with a structured report on failure."""

    report = validation_report(document)
    if not report["valid"]:
        raise SpecDocumentValidationError(_issues_from_report(report))
    return report


def validation_report(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a structured validation report without mutating the document."""

    issues: list[ValidationIssue] = []
    if not isinstance(document, Mapping):
        return _report(
            [
                ValidationIssue(
                    path="$",
                    code="invalid_type",
                    message="SpecDocument must be a JSON/YAML object.",
                )
            ]
        )

    _validate_top_level(document, issues)
    _validate_sections(document.get("sections"), issues)
    _validate_optional_lists(document, issues)
    return _report(issues)


def _validate_top_level(document: Mapping[str, Any], issues: list[ValidationIssue]) -> None:
    for field in _REQUIRED_TOP_LEVEL:
        if field not in document:
            issues.append(_issue(field, "required", f"Missing required field: {field}."))

    schema = document.get("schema")
    if schema is not None and schema != SPEC_DOCUMENT_SCHEMA:
        issues.append(
            _issue(
                "schema",
                "invalid_schema",
                f"SpecDocument schema must be {SPEC_DOCUMENT_SCHEMA}.",
            )
        )

    _validate_pattern(document, "source_key", _SOURCE_KEY_RE, "invalid_source_key", issues)
    _validate_pattern(document, "snapshot_id", _SNAPSHOT_ID_RE, "invalid_snapshot_id", issues)
    _validate_enum(document, "kind", ALLOWED_KINDS, "invalid_kind", issues)
    _validate_hash(document, "content_hash", issues)
    _validate_hash(document, "normalized_hash", issues)
    _validate_fetched_at(document.get("fetched_at"), issues)
    _validate_enum(
        document,
        "classification",
        ALLOWED_CLASSIFICATIONS,
        "invalid_classification",
        issues,
    )
    _validate_enum(
        document,
        "storage_mode",
        ALLOWED_STORAGE_MODES,
        "invalid_storage_mode",
        issues,
    )
    _validate_storage_policy(document, issues)


def _validate_sections(value: Any, issues: list[ValidationIssue]) -> None:
    if "sections" in {issue.path for issue in issues if issue.code == "required"}:
        return
    if not isinstance(value, list):
        issues.append(_issue("sections", "invalid_type", "sections must be a list."))
        return
    if not value:
        issues.append(
            _issue("sections", "empty_sections", "sections must contain at least one section.")
        )
        return

    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    for index, section in enumerate(value):
        path = f"sections[{index}]"
        if not isinstance(section, Mapping):
            issues.append(_issue(path, "invalid_type", "section must be an object."))
            continue
        for field in _REQUIRED_SECTION_FIELDS:
            if field not in section:
                issues.append(
                    _issue(f"{path}.{field}", "required", f"Missing required field: {field}.")
                )

        local_id = section.get("local_id")
        if local_id is not None:
            if not _is_nonempty_string(local_id) or not _SECTION_ID_RE.match(local_id):
                issues.append(
                    _issue(
                        f"{path}.local_id",
                        "invalid_section_id",
                        "section local_id must look like D-01 or D-01.2.",
                    )
                )
            elif local_id in seen_ids:
                issues.append(
                    _issue(
                        f"{path}.local_id",
                        "duplicate_section_id",
                        f"Duplicate section local_id: {local_id}.",
                    )
                )
            else:
                seen_ids.add(local_id)

        stable_key = section.get("stable_key")
        if stable_key is not None:
            if not _is_nonempty_string(stable_key):
                issues.append(
                    _issue(
                        f"{path}.stable_key",
                        "invalid_stable_key",
                        "section stable_key must be a non-empty string.",
                    )
                )
            elif stable_key in seen_keys:
                issues.append(
                    _issue(
                        f"{path}.stable_key",
                        "duplicate_stable_key",
                        f"Duplicate section stable_key: {stable_key}.",
                    )
                )
            else:
                seen_keys.add(stable_key)

        heading_path = section.get("heading_path")
        if heading_path is not None and not _is_nonempty_string_list(heading_path):
            issues.append(
                _issue(
                    f"{path}.heading_path",
                    "invalid_heading_path",
                    "section heading_path must be a non-empty list of strings.",
                )
            )

        if "content_hash" in section:
            _validate_hash(section, "content_hash", issues, path=f"{path}.content_hash")

        body_ref = section.get("body_ref")
        if body_ref is not None and not _is_nonempty_string(body_ref):
            issues.append(
                _issue(
                    f"{path}.body_ref",
                    "invalid_body_ref",
                    "section body_ref must be a non-empty string.",
                )
            )


def _validate_optional_lists(document: Mapping[str, Any], issues: list[ValidationIssue]) -> None:
    for field in _OPTIONAL_LIST_FIELDS:
        if field in document and not isinstance(document[field], list):
            issues.append(_issue(field, "invalid_type", f"{field} must be a list."))


def _validate_pattern(
    document: Mapping[str, Any],
    field: str,
    pattern: re.Pattern[str],
    code: str,
    issues: list[ValidationIssue],
) -> None:
    value = document.get(field)
    if value is None:
        return
    if not _is_nonempty_string(value) or not pattern.match(value):
        issues.append(_issue(field, code, f"{field} has invalid format."))


def _validate_enum(
    document: Mapping[str, Any],
    field: str,
    allowed: frozenset[str],
    code: str,
    issues: list[ValidationIssue],
) -> None:
    value = document.get(field)
    if value is None:
        return
    if value not in allowed:
        issues.append(_issue(field, code, f"{field} must be one of {sorted(allowed)}."))


def _validate_hash(
    document: Mapping[str, Any],
    field: str,
    issues: list[ValidationIssue],
    *,
    path: str | None = None,
) -> None:
    value = document.get(field)
    if value is None:
        return
    if not isinstance(value, str) or not _HASH_RE.match(value):
        issues.append(
            _issue(path or field, "invalid_hash", f"{path or field} must be a sha256 digest.")
        )


def _validate_fetched_at(value: Any, issues: list[ValidationIssue]) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.endswith("Z"):
        issues.append(
            _issue("fetched_at", "invalid_timestamp", "fetched_at must be a UTC ISO timestamp ending in Z.")
        )
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        issues.append(
            _issue("fetched_at", "invalid_timestamp", "fetched_at must be a valid ISO timestamp.")
        )


def _validate_storage_policy(document: Mapping[str, Any], issues: list[ValidationIssue]) -> None:
    classification = document.get("classification")
    storage_mode = document.get("storage_mode")
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


def _issue(path: str, code: str, message: str) -> ValidationIssue:
    return ValidationIssue(path=path, code=code, message=message)


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_nonempty_string_list(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(_is_nonempty_string(item) for item in value)


def _report(issues: list[ValidationIssue]) -> dict[str, Any]:
    return {
        "schema": SPEC_DOCUMENT_VALIDATION_SCHEMA,
        "valid": not issues,
        "errors": [issue.to_dict() for issue in issues],
    }


def _issues_from_report(report: Mapping[str, Any]) -> list[ValidationIssue]:
    return [
        ValidationIssue(
            path=str(error.get("path", "")),
            code=str(error.get("code", "")),
            message=str(error.get("message", "")),
        )
        for error in report.get("errors", [])
        if isinstance(error, Mapping)
    ]

