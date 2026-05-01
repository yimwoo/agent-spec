"""Tests for candidate-to-baseline intake diff (T-047 / R-149)."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import CLI_ERROR_SCHEMA, main
from agentspec.io import load_data, write_data
from agentspec.spec_document import SPEC_DOCUMENT_SCHEMA


def _hash(label: str) -> str:
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


class IntakeDiffTests(unittest.TestCase):
    def test_candidate_diff_reports_all_section_change_types_as_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_baseline_and_candidate(root)
            dcr_path = _seed_dcr(root)
            original_dcr = dcr_path.read_text(encoding="utf-8")
            original_requirements = load_data(
                root / "docs" / "traceability" / "requirements.yml"
            )
            spec_path = root / "docs" / "spec" / "spec-index.md"
            original_spec = spec_path.read_text(encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = main(
                    [
                        "--root",
                        str(root),
                        "intake",
                        "diff",
                        "SRC-0002",
                        "--baseline",
                        "accepted",
                        "--json",
                    ]
                )

            self.assertEqual(rc, 0)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema"], "agentspec.intake.diff.v0")
            self.assertEqual(payload["snapshot_id"], "SRC-0002")
            self.assertEqual(payload["baseline"]["source_id"], "SRC-0001")
            self.assertEqual(payload["recommendation"], "needs-review")
            self.assertEqual(
                payload["summary"],
                {
                    "unchanged": 1,
                    "added": 1,
                    "removed": 1,
                    "renamed": 1,
                    "moved": 1,
                    "body-changed": 1,
                },
            )
            self.assertEqual(
                {change["kind"] for change in payload["changes"]},
                {
                    "unchanged",
                    "added",
                    "removed",
                    "renamed",
                    "moved",
                    "body-changed",
                },
            )
            diff_path = root / "docs" / "source" / "candidates" / "SRC-0002" / "diff.yml"
            self.assertEqual(load_data(diff_path), payload)
            self.assertEqual(dcr_path.read_text(encoding="utf-8"), original_dcr)
            self.assertEqual(
                load_data(root / "docs" / "traceability" / "requirements.yml"),
                original_requirements,
            )
            self.assertEqual(spec_path.read_text(encoding="utf-8"), original_spec)

    def test_candidate_diff_has_human_readable_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_baseline_and_candidate(root)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                rc = main(
                    [
                        "--root",
                        str(root),
                        "intake",
                        "diff",
                        "SRC-0002",
                        "--baseline",
                        "accepted",
                    ]
                )

            self.assertEqual(rc, 0)
            output = stdout.getvalue()
            self.assertIn("Candidate SRC-0002 vs accepted SRC-0001", output)
            self.assertIn("Recommendation: needs-review", output)
            self.assertIn("added: 1", output)
            self.assertIn("body-changed: 1", output)

    def test_candidate_diff_validates_spec_document_before_writing_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_baseline_and_candidate(root)
            spec_path = (
                root
                / "docs"
                / "source"
                / "candidates"
                / "SRC-0002"
                / "spec-document.yml"
            )
            broken = load_data(spec_path)
            broken.pop("content_hash")
            write_data(spec_path, broken)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                rc = main(
                    [
                        "--root",
                        str(root),
                        "intake",
                        "diff",
                        "SRC-0002",
                        "--baseline",
                        "accepted",
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
                "content_hash",
                {error["path"] for error in payload["error"]["details"]["errors"]},
            )
            candidate_dir = root / "docs" / "source" / "candidates" / "SRC-0002"
            self.assertFalse((candidate_dir / "diff.yml").exists())
            self.assertFalse(load_data(candidate_dir / "validation.yml")["valid"])


def _seed_baseline_and_candidate(root: Path) -> None:
    write_data(
        root / "docs" / "source" / "sources.yml",
        [
            {
                "id": "SRC-0001",
                "source_key": "payments-design",
                "kind": "markdown",
                "uri": "docs/source/src-0001-payments.md",
                "state": "accepted",
            }
        ],
    )
    write_data(
        root / "docs" / "source" / "sections.yml",
        [
            _accepted_section("D-01", "payments-design/overview", ["Overview"], _hash("a")),
            _accepted_section("D-02", "payments-design/billing", ["Billing"], _hash("b")),
            _accepted_section("D-03", "payments-design/errors", ["Errors"], _hash("c")),
            _accepted_section("D-04", "payments-design/auth", ["Auth"], _hash("d")),
            _accepted_section("D-05", "payments-design/removal", ["Removal"], _hash("e")),
        ],
    )
    write_data(root / "docs" / "traceability" / "requirements.yml", [])
    spec_path = root / "docs" / "spec" / "spec-index.md"
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text("# Spec Index\n\nDo not change during diff.\n", encoding="utf-8")
    write_data(
        root / "docs" / "source" / "candidates" / "SRC-0002" / "spec-document.yml",
        {
            "schema": SPEC_DOCUMENT_SCHEMA,
            "source_key": "payments-design",
            "snapshot_id": "SRC-0002",
            "kind": "markdown",
            "content_hash": _hash("f"),
            "normalized_hash": _hash("f"),
            "fetched_at": "2026-05-01T00:00:00Z",
            "classification": "internal",
            "storage_mode": "committed",
            "sections": [
                _candidate_section("D-01", "payments-design/overview", ["Overview"], _hash("a")),
                _candidate_section("D-02", "payments-design/invoices", ["Invoices"], _hash("b")),
                _candidate_section("D-03", "payments-design/errors", ["Errors"], _hash("z")),
                _candidate_section("D-02.1", "payments-design/auth", ["Auth"], _hash("d")),
                _candidate_section("D-06", "payments-design/new-section", ["New Section"], _hash("g")),
            ],
        },
    )


def _accepted_section(
    local_id: str,
    stable_key: str,
    heading_path: list[str],
    content_hash: str,
) -> dict[str, object]:
    return {
        "id": local_id,
        "source_id": "SRC-0001",
        "stable_key": stable_key,
        "heading_path": heading_path,
        "content_hash": content_hash,
        "start_line": 1,
        "end_line": 2,
    }


def _candidate_section(
    local_id: str,
    stable_key: str,
    heading_path: list[str],
    content_hash: str,
) -> dict[str, object]:
    return {
        "local_id": local_id,
        "stable_key": stable_key,
        "heading_path": heading_path,
        "content_hash": content_hash,
        "body_ref": f"source.md#{local_id}",
    }


def _seed_dcr(root: Path) -> Path:
    path = root / "docs" / "change-requests" / "DCR-0001-test.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# DCR-0001: Test

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
""",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
