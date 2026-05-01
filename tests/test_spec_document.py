"""Tests for the SpecDocument schema and validator (T-045 / R-148)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from agentspec.spec_document import (
    SPEC_DOCUMENT_SCHEMA,
    SPEC_DOCUMENT_VALIDATION_SCHEMA,
    SpecDocumentValidationError,
    validate_spec_document,
    validation_report,
)


FIXTURE = Path(__file__).parent / "fixtures" / "intake" / "valid_spec_document.json"


def valid_document() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class SpecDocumentValidationTests(unittest.TestCase):
    def test_valid_document_returns_structured_success_report(self) -> None:
        report = validate_spec_document(valid_document())

        self.assertEqual(report["schema"], SPEC_DOCUMENT_VALIDATION_SCHEMA)
        self.assertTrue(report["valid"])
        self.assertEqual(report["errors"], [])

    def test_requires_top_level_schema_fields(self) -> None:
        doc = valid_document()
        for field in [
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
        ]:
            broken = dict(doc)
            broken.pop(field)
            with self.subTest(field=field):
                report = validation_report(broken)
                self.assertFalse(report["valid"])
                self.assertIn(field, {error["path"] for error in report["errors"]})

    def test_requires_valid_hash_format(self) -> None:
        doc = valid_document()
        doc["content_hash"] = "sha256:not-a-real-digest"

        with self.assertRaises(SpecDocumentValidationError) as ctx:
            validate_spec_document(doc)

        payload = ctx.exception.to_dict()
        self.assertEqual(payload["schema"], SPEC_DOCUMENT_VALIDATION_SCHEMA)
        self.assertFalse(payload["valid"])
        self.assertEqual(payload["errors"][0]["path"], "content_hash")
        self.assertEqual(payload["errors"][0]["code"], "invalid_hash")

    def test_requires_section_records(self) -> None:
        doc = valid_document()
        doc["sections"] = []

        report = validation_report(doc)

        self.assertFalse(report["valid"])
        self.assertIn("sections", {error["path"] for error in report["errors"]})

    def test_validates_required_section_fields(self) -> None:
        doc = valid_document()
        section = dict(doc["sections"][0])  # type: ignore[index]
        section.pop("body_ref")
        doc["sections"] = [section]

        report = validation_report(doc)

        self.assertFalse(report["valid"])
        self.assertIn("sections[0].body_ref", {error["path"] for error in report["errors"]})

    def test_rejects_duplicate_section_ids(self) -> None:
        doc = valid_document()
        first = dict(doc["sections"][0])  # type: ignore[index]
        second = dict(first)
        second["stable_key"] = "payments-api-v2/duplicate"
        doc["sections"] = [first, second]

        report = validation_report(doc)

        self.assertFalse(report["valid"])
        self.assertIn("duplicate_section_id", {error["code"] for error in report["errors"]})

    def test_rejects_unknown_kind_classification_and_storage_mode(self) -> None:
        doc = valid_document()
        doc["kind"] = "spreadsheet"
        doc["classification"] = "secret-ish"
        doc["storage_mode"] = "clipboard"

        report = validation_report(doc)

        self.assertFalse(report["valid"])
        codes = {error["code"] for error in report["errors"]}
        self.assertIn("invalid_kind", codes)
        self.assertIn("invalid_classification", codes)
        self.assertIn("invalid_storage_mode", codes)

    def test_storage_policy_disallows_committed_confidential_content(self) -> None:
        doc = valid_document()
        doc["classification"] = "confidential"
        doc["storage_mode"] = "committed"

        report = validation_report(doc)

        self.assertFalse(report["valid"])
        self.assertIn("storage_policy", {error["code"] for error in report["errors"]})

    def test_storage_policy_allows_pointer_only_restricted_content(self) -> None:
        doc = valid_document()
        doc["classification"] = "restricted"
        doc["storage_mode"] = "pointer-only"

        report = validate_spec_document(doc)

        self.assertTrue(report["valid"])

    def test_optional_collections_must_be_lists_when_present(self) -> None:
        doc = valid_document()
        doc["api_contracts"] = {"path": "/v2/payments"}

        report = validation_report(doc)

        self.assertFalse(report["valid"])
        self.assertIn("api_contracts", {error["path"] for error in report["errors"]})

    def test_schema_constant_matches_fixture(self) -> None:
        self.assertEqual(valid_document()["schema"], SPEC_DOCUMENT_SCHEMA)


if __name__ == "__main__":
    unittest.main()
