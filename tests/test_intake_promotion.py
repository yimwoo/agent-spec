"""Tests for human-gated candidate promotion (T-048 / R-150)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import CLI_ERROR_SCHEMA, main
from agentspec.io import load_data, write_data


ACCEPTED_MARKDOWN = """# Payments Design

## Overview

The accepted design uses the V1 payments API.
"""

CANDIDATE_MARKDOWN = """# Payments Design

## Overview

The accepted design uses the V2 payments API.

## Rollout

The rollout starts with internal merchants.
"""

PAYMENTS_GOALS_MARKDOWN = """# Payments Design

## Goals

The payments API must capture idempotency keys.
"""

AUTH_GOALS_MARKDOWN = """# Auth Design

## Goals

The auth API must reject invalid tokens.
"""


class IntakePromotionTests(unittest.TestCase):
    def test_promote_is_explicit_and_import_diff_do_not_mutate_accepted_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_workspace_with_accepted_source(root)
            candidate = root / "candidate.md"
            candidate.write_text(CANDIDATE_MARKDOWN, encoding="utf-8")
            before = _accepted_projection(root)

            import_payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "import",
                    str(candidate),
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
            self.assertEqual(import_payload["snapshot_id"], "SRC-0002")
            self.assertEqual(_accepted_projection(root), before)

            diff_payload = _run_json(
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
            self.assertEqual(diff_payload["snapshot_id"], "SRC-0002")
            self.assertEqual(_accepted_projection(root), before)

            promote_payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "promote",
                    "SRC-0002",
                    "--decision",
                    "accepted",
                    "--json",
                ]
            )

            self.assertEqual(promote_payload["schema"], "agentspec.intake.promote.v0")
            self.assertEqual(promote_payload["snapshot_id"], "SRC-0002")
            self.assertEqual(promote_payload["decision"], "accepted")
            self.assertEqual(promote_payload["approval"]["mode"], "explicit-command")
            self.assertFalse(promote_payload["compile"]["ran"])
            self.assertEqual(promote_payload["compile"]["command"], "aspec compile")

            sources = load_data(root / "docs" / "source" / "sources.yml")
            self.assertEqual(
                [(source["id"], source.get("state")) for source in sources],
                [("SRC-0001", "superseded"), ("SRC-0002", "accepted")],
            )
            sections = load_data(root / "docs" / "source" / "sections.yml")
            accepted_sections = [
                section for section in sections if section.get("state", "accepted") == "accepted"
            ]
            self.assertEqual({section["source_id"] for section in accepted_sections}, {"SRC-0002"})
            self.assertEqual(
                [section["id"] for section in accepted_sections],
                ["payments-design:D-01", "payments-design:D-02"],
            )

    def test_promote_does_not_accept_or_classify_dcr_governance_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_workspace_with_accepted_source(root)
            _seed_governance_artifacts(root)
            candidate = root / "candidate.md"
            candidate.write_text(CANDIDATE_MARKDOWN, encoding="utf-8")
            _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "import",
                    str(candidate),
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
            before_dcr = (
                root / "docs" / "change-requests" / "DCR-0001-test.md"
            ).read_text(encoding="utf-8")
            before_requirements = load_data(root / "docs" / "traceability" / "requirements.yml")

            promote_payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "promote",
                    "SRC-0002",
                    "--decision",
                    "accepted",
                    "--json",
                ]
            )

            self.assertEqual(promote_payload["decision"], "accepted")
            self.assertEqual(
                (root / "docs" / "change-requests" / "DCR-0001-test.md").read_text(
                    encoding="utf-8"
                ),
                before_dcr,
            )
            self.assertEqual(
                load_data(root / "docs" / "traceability" / "requirements.yml"),
                before_requirements,
            )

    def test_promote_validates_candidate_before_projection_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_workspace_with_accepted_source(root)
            candidate = root / "candidate.md"
            candidate.write_text(CANDIDATE_MARKDOWN, encoding="utf-8")
            _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "import",
                    str(candidate),
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
            spec_path = (
                root
                / "docs"
                / "source"
                / "candidates"
                / "SRC-0002"
                / "spec-document.yml"
            )
            broken = load_data(spec_path)
            broken.pop("normalized_hash")
            spec_path.write_text(json.dumps(broken), encoding="utf-8")
            before = _accepted_projection(root)

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "promote",
                    "SRC-0002",
                    "--decision",
                    "accepted",
                    "--json",
                ],
                expected_rc=1,
            )

            self.assertEqual(payload["schema"], CLI_ERROR_SCHEMA)
            self.assertEqual(payload["error"]["type"], "SpecDocumentValidationError")
            self.assertEqual(_accepted_projection(root), before)

    def test_promote_preflights_section_projection_before_copying_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_workspace_with_accepted_source(root)
            candidate = root / "candidate.md"
            candidate.write_text(CANDIDATE_MARKDOWN, encoding="utf-8")
            _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "import",
                    str(candidate),
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
            spec_path = (
                root
                / "docs"
                / "source"
                / "candidates"
                / "SRC-0002"
                / "spec-document.yml"
            )
            broken = load_data(spec_path)
            broken["sections"][0]["body_ref"] = "source.md"
            write_data(spec_path, broken)
            before = _accepted_projection(root)

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "promote",
                    "SRC-0002",
                    "--decision",
                    "accepted",
                    "--json",
                ],
                expected_rc=1,
            )

            self.assertEqual(payload["schema"], CLI_ERROR_SCHEMA)
            self.assertEqual(payload["error"]["type"], "ValueError")
            self.assertEqual(_accepted_projection(root), before)
            self.assertFalse(
                (root / "docs" / "source" / "src-0002-payments-design.md").exists()
            )

    def test_promote_records_source_and_section_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_workspace_with_accepted_source(root)
            candidate = root / "candidate.md"
            candidate.write_text(CANDIDATE_MARKDOWN, encoding="utf-8")
            _import_candidate(root, candidate, source_key="payments-design")

            promote_payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "promote",
                    "SRC-0002",
                    "--decision",
                    "accepted",
                    "--json",
                ]
            )

            self.assertEqual(promote_payload["accepted_source"]["snapshot_id"], "SRC-0002")
            self.assertEqual(promote_payload["accepted_source"]["source_key"], "payments-design")
            self.assertEqual(promote_payload["accepted_source"]["remote_uri"], str(candidate.resolve()))
            self.assertTrue(
                promote_payload["accepted_source"]["content_hash"].startswith("sha256:")
            )
            self.assertTrue(
                promote_payload["accepted_source"]["normalized_hash"].startswith("sha256:")
            )
            self.assertEqual(promote_payload["accepted_source"]["supersedes"], "SRC-0001")

            sources = {
                source["id"]: source
                for source in load_data(root / "docs" / "source" / "sources.yml")
            }
            self.assertEqual(sources["SRC-0001"]["state"], "superseded")
            self.assertEqual(sources["SRC-0001"]["source_key"], "payments-design")
            self.assertEqual(sources["SRC-0001"]["superseded_by"], "SRC-0002")

            sections = {
                section["id"]: section
                for section in load_data(root / "docs" / "source" / "sections.yml")
            }
            self.assertIn("SRC-0001:D-01", sections)
            self.assertEqual(sections["SRC-0001:D-01"]["state"], "superseded")
            self.assertEqual(sections["SRC-0001:D-01"]["snapshot_section_id"], "SRC-0001:D-01")

            self.assertIn("payments-design:D-01", sections)
            self.assertEqual(sections["payments-design:D-01"]["state"], "accepted")
            self.assertEqual(sections["payments-design:D-01"]["source_key"], "payments-design")
            self.assertEqual(sections["payments-design:D-01"]["snapshot_id"], "SRC-0002")
            self.assertEqual(sections["payments-design:D-01"]["snapshot_section_id"], "SRC-0002:D-01")
            self.assertEqual(sections["payments-design:D-01"]["local_id"], "D-01")

    def test_compile_uses_source_key_qualified_current_sections_after_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _run(["--root", str(root), "init"])
            payments = root / "payments.md"
            payments.write_text(PAYMENTS_GOALS_MARKDOWN, encoding="utf-8")
            auth = root / "auth.md"
            auth.write_text(AUTH_GOALS_MARKDOWN, encoding="utf-8")

            _import_candidate(root, payments, source_key="payments-design")
            _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "promote",
                    "SRC-0001",
                    "--decision",
                    "accepted",
                    "--json",
                ]
            )
            _import_candidate(root, auth, source_key="auth-design")
            _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "promote",
                    "SRC-0002",
                    "--decision",
                    "accepted",
                    "--json",
                ]
            )

            _run(["--root", str(root), "compile"])

            spec_index = load_data(root / "docs" / "spec" / "spec-index.yml")
            cited_sections = {
                section_id
                for shard in spec_index
                for section_id in shard.get("source_sections", [])
            }
            self.assertIn("payments-design:D-01", cited_sections)
            self.assertIn("auth-design:D-01", cited_sections)
            self.assertNotIn("D-01", cited_sections)

            requirements = load_data(root / "docs" / "traceability" / "requirements.yml")
            requirement_sections = {
                section_id
                for requirement in requirements
                for section_id in requirement.get("source_sections", [])
            }
            self.assertIn("payments-design:D-01", requirement_sections)
            self.assertIn("auth-design:D-01", requirement_sections)
            self.assertNotIn("D-01", requirement_sections)


def _seed_workspace_with_accepted_source(root: Path) -> None:
    accepted = root / "accepted.md"
    accepted.write_text(ACCEPTED_MARKDOWN, encoding="utf-8")
    _run(["--root", str(root), "init"])
    _run(["--root", str(root), "ingest", str(accepted)])


def _import_candidate(root: Path, source: Path, *, source_key: str) -> dict[str, object]:
    return _run_json(
        [
            "--root",
            str(root),
            "intake",
            "import",
            str(source),
            "--kind",
            "markdown",
            "--source-key",
            source_key,
            "--classification",
            "internal",
            "--storage-mode",
            "committed",
            "--as-candidate",
            "--json",
        ]
    )


def _seed_governance_artifacts(root: Path) -> None:
    dcr = root / "docs" / "change-requests" / "DCR-0001-test.md"
    dcr.parent.mkdir(parents=True, exist_ok=True)
    dcr.write_text(
        """# DCR-0001: Test

| Field | Value |
|---|---|
| Status | classified |
| Classification | implement-now |
""",
        encoding="utf-8",
    )
    requirements = [
        {
            "id": "R-200",
            "title": "Pending requirement",
            "description": "A pending requirement stays pending.",
            "status": "proposed-pending-acceptance",
            "originating_dcr": "DCR-0001",
        }
    ]
    write_data(root / "docs" / "traceability" / "requirements.yml", requirements)


def _accepted_projection(root: Path) -> dict[str, object]:
    return {
        "sources": load_data(root / "docs" / "source" / "sources.yml"),
        "sections": load_data(root / "docs" / "source" / "sections.yml"),
        "requirements": load_data(root / "docs" / "traceability" / "requirements.yml"),
        "spec_index": (root / "docs" / "spec" / "spec-index.md").read_text(
            encoding="utf-8"
        ),
    }


def _run(args: list[str]) -> str:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = main(args)
    if rc != 0:
        raise AssertionError(f"command failed rc={rc}: {args}\n{stderr.getvalue()}")
    if stderr.getvalue():
        raise AssertionError(stderr.getvalue())
    return stdout.getvalue()


def _run_json(args: list[str], *, expected_rc: int = 0) -> dict[str, object]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = main(args)
    if rc != expected_rc:
        raise AssertionError(
            f"command returned rc={rc}, expected {expected_rc}: {args}\n"
            f"stdout={stdout.getvalue()}\nstderr={stderr.getvalue()}"
        )
    if stderr.getvalue():
        raise AssertionError(stderr.getvalue())
    return json.loads(stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
