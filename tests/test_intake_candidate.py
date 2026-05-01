"""Tests for external SpecDocument candidate intake (T-046 / R-148)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import CLI_ERROR_SCHEMA, main
from agentspec.io import load_data
from agentspec.spec_document import (
    SPEC_DOCUMENT_SCHEMA,
    SPEC_DOCUMENT_VALIDATION_SCHEMA,
)


MARKDOWN = """# Payments API V2 Design

Introductory context that should not become a design section.

## Overview

The API accepts idempotency keys.

### Error Handling

The API returns structured errors.
"""


class IntakeCandidateImportTests(unittest.TestCase):
    def test_markdown_candidate_import_writes_spec_document_only_under_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "payments-design.md"
            source.write_text(MARKDOWN, encoding="utf-8")

            self.assertEqual(main(["--root", str(root), "init"]), 0)
            accepted_sources = load_data(root / "docs" / "source" / "sources.yml")
            accepted_sections = load_data(root / "docs" / "source" / "sections.yml")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = main(
                    [
                        "--root",
                        str(root),
                        "intake",
                        "import",
                        str(source),
                        "--kind",
                        "markdown",
                        "--source-key",
                        "payments-design",
                        "--classification",
                        "internal",
                        "--storage-mode",
                        "committed",
                        "--as-candidate",
                        "--json",
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema"], "agentspec.intake.import.v0")
            self.assertEqual(payload["snapshot_id"], "SRC-0001")

            candidate_dir = root / payload["candidate_path"]
            spec_document = load_data(candidate_dir / "spec-document.yml")
            self.assertEqual(spec_document["schema"], SPEC_DOCUMENT_SCHEMA)
            self.assertEqual(spec_document["source_key"], "payments-design")
            self.assertEqual(spec_document["kind"], "markdown")
            self.assertEqual(spec_document["classification"], "internal")
            self.assertEqual(spec_document["storage_mode"], "committed")
            self.assertEqual(
                [section["local_id"] for section in spec_document["sections"]],
                ["D-01", "D-01.1"],
            )
            self.assertEqual(
                [section["stable_key"] for section in spec_document["sections"]],
                ["payments-design/overview", "payments-design/overview/error-handling"],
            )
            self.assertTrue(
                all(
                    section["content_hash"].startswith("sha256:")
                    for section in spec_document["sections"]
                )
            )
            self.assertTrue(
                all(
                    section["body_ref"].startswith("source.md#L")
                    for section in spec_document["sections"]
                )
            )

            validation = load_data(candidate_dir / "validation.yml")
            self.assertEqual(validation["schema"], SPEC_DOCUMENT_VALIDATION_SCHEMA)
            self.assertTrue(validation["valid"])
            self.assertEqual(load_data(candidate_dir / "sections.yml"), spec_document["sections"])
            self.assertEqual((candidate_dir / "source.md").read_text(encoding="utf-8"), MARKDOWN)

            self.assertEqual(load_data(root / "docs" / "source" / "sources.yml"), accepted_sources)
            self.assertEqual(load_data(root / "docs" / "source" / "sections.yml"), accepted_sections)

    def test_invalid_candidate_import_returns_structured_error_without_accepted_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "payments-design.md"
            source.write_text(MARKDOWN, encoding="utf-8")

            self.assertEqual(main(["--root", str(root), "init"]), 0)
            accepted_sources = load_data(root / "docs" / "source" / "sources.yml")
            accepted_sections = load_data(root / "docs" / "source" / "sections.yml")

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = main(
                    [
                        "--root",
                        str(root),
                        "intake",
                        "import",
                        str(source),
                        "--kind",
                        "markdown",
                        "--source-key",
                        "payments-design",
                        "--classification",
                        "confidential",
                        "--storage-mode",
                        "committed",
                        "--as-candidate",
                        "--json",
                    ]
                )

            self.assertEqual(rc, 1)
            self.assertEqual(stderr.getvalue(), "")
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema"], CLI_ERROR_SCHEMA)
            self.assertEqual(payload["error"]["type"], "SpecDocumentValidationError")
            self.assertFalse(payload["error"]["details"]["valid"])
            self.assertIn(
                "storage_policy",
                {error["code"] for error in payload["error"]["details"]["errors"]},
            )

            validation = load_data(
                root
                / "docs"
                / "source"
                / "candidates"
                / "SRC-0001"
                / "validation.yml"
            )
            self.assertFalse(validation["valid"])
            self.assertFalse(
                (
                    root
                    / "docs"
                    / "source"
                    / "candidates"
                    / "SRC-0001"
                    / "source.md"
                ).exists()
            )
            self.assertEqual(load_data(root / "docs" / "source" / "sources.yml"), accepted_sources)
            self.assertEqual(load_data(root / "docs" / "source" / "sections.yml"), accepted_sections)

    def test_pointer_only_candidate_uses_remote_body_refs_without_copying_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "payments-design.md"
            source.write_text(MARKDOWN, encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = main(
                    [
                        "--root",
                        str(root),
                        "intake",
                        "import",
                        str(source),
                        "--kind",
                        "markdown",
                        "--source-key",
                        "payments-design",
                        "--classification",
                        "restricted",
                        "--storage-mode",
                        "pointer-only",
                        "--as-candidate",
                        "--json",
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(stdout.getvalue())
            candidate_dir = root / payload["candidate_path"]
            spec_document = load_data(candidate_dir / "spec-document.yml")

            self.assertFalse((candidate_dir / "source.md").exists())
            self.assertTrue(
                all(
                    section["body_ref"].startswith("remote_uri#L")
                    for section in spec_document["sections"]
                )
            )


if __name__ == "__main__":
    unittest.main()
