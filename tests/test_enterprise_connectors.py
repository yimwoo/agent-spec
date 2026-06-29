"""Tests for enterprise connector adapters over intake (T-052 / R-154)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import CLI_ERROR_SCHEMA, main
from agentspec.io import load_data, write_data
from agentspec.outcome import build_outcome_status, record_outcome_observation


CONFLUENCE_BODY = """# Payments Design

## Overview

The Confluence page describes payment capture behavior.
"""


class EnterpriseConnectorTests(unittest.TestCase):
    def test_external_outcome_adapter_contributes_facts_without_policy_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_data(
                root / "agent" / "outcomes.yml",
                {
                    "schema": "agentspec.outcomes.v0",
                    "outcomes": [
                        {
                            "id": "O-service",
                            "title": "Service is operational",
                            "gates": [
                                {
                                    "id": "G-slo",
                                    "title": "SLO holds",
                                    "checks": [
                                        {"id": "C-slo", "kind": "slo", "max_age_seconds": 3600}
                                    ],
                                }
                            ],
                        }
                    ],
                },
            )

            recorded = record_outcome_observation(
                root,
                {
                    "outcome_id": "O-service",
                    "gate_id": "G-slo",
                    "check_id": "C-slo",
                    "kind": "slo",
                    "observed_at": "2026-06-29T20:00:00Z",
                    "source": {
                        "type": "observability",
                        "adapter": "metrics-connector",
                        "query_id": "availability-30d",
                    },
                    "facts": {"compliant": True},
                },
            )

            self.assertNotIn("status", recorded)
            status = build_outcome_status(root, evaluated_at="2026-06-29T20:30:00Z")
            verdict = status["outcomes"][0]["gates"][0]["verdicts"][0]
            self.assertEqual(verdict["status"], "passed")
            self.assertEqual(verdict["policy_authority"], "agentspec.outcome")
            self.assertEqual(verdict["observation"]["source"]["adapter"], "metrics-connector")

    def test_confluence_fixture_import_writes_candidate_snapshot_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _run(["--root", str(root), "init"])
            fixture = root / "confluence-page.json"
            write_data(
                fixture,
                {
                    "remote_uri": "confluence://PAY/pages/12345",
                    "remote_version": "42",
                    "fetched_at": "2026-05-01T00:00:00Z",
                    "title": "Payments Design",
                    "body": CONFLUENCE_BODY,
                },
            )
            before = _accepted_projection(root)

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "import",
                    str(fixture),
                    "--kind",
                    "confluence",
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

            self.assertEqual(payload["schema"], "agentspec.intake.import.v0")
            self.assertEqual(payload["snapshot_id"], "SRC-0001")
            self.assertEqual(payload["kind"], "confluence")
            candidate_dir = root / payload["candidate_path"]
            spec_document = load_data(candidate_dir / "spec-document.yml")
            self.assertEqual(spec_document["kind"], "confluence")
            self.assertEqual(spec_document["title"], "Payments Design")
            self.assertEqual(spec_document["remote_uri"], "confluence://PAY/pages/12345")
            self.assertEqual(spec_document["remote_version"], "42")
            self.assertEqual(spec_document["fetched_at"], "2026-05-01T00:00:00Z")
            self.assertTrue(spec_document["content_hash"].startswith("sha256:"))
            self.assertTrue(spec_document["normalized_hash"].startswith("sha256:"))
            self.assertEqual(
                [section["local_id"] for section in spec_document["sections"]],
                ["D-01"],
            )
            self.assertEqual((candidate_dir / "source.md").read_text(encoding="utf-8"), CONFLUENCE_BODY)
            self.assertEqual(_accepted_projection(root), before)

    def test_confluence_fixture_pointer_only_records_metadata_without_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fixture = root / "confluence-page.json"
            write_data(
                fixture,
                {
                    "remote_uri": "confluence://PAY/pages/12345",
                    "remote_version": "43",
                    "fetched_at": "2026-05-01T00:00:00Z",
                    "body": CONFLUENCE_BODY,
                },
            )

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "import",
                    str(fixture),
                    "--kind",
                    "confluence",
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

            candidate_dir = root / payload["candidate_path"]
            spec_document = load_data(candidate_dir / "spec-document.yml")
            self.assertFalse((candidate_dir / "source.md").exists())
            self.assertEqual(spec_document["remote_uri"], "confluence://PAY/pages/12345")
            self.assertEqual(spec_document["remote_version"], "43")
            self.assertTrue(
                all(
                    section["body_ref"].startswith("remote_uri#L")
                    for section in spec_document["sections"]
                )
            )

    def test_connector_failure_returns_json_error_without_accepted_updates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _run(["--root", str(root), "init"])
            fixture = root / "confluence-page.json"
            write_data(
                fixture,
                {
                    "remote_uri": "confluence://PAY/pages/12345",
                    "remote_version": "42",
                    "fetched_at": "2026-05-01T00:00:00Z",
                },
            )
            before = _accepted_projection(root)

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "intake",
                    "import",
                    str(fixture),
                    "--kind",
                    "confluence",
                    "--source-key",
                    "payments-design",
                    "--classification",
                    "internal",
                    "--storage-mode",
                    "committed",
                    "--as-candidate",
                    "--json",
                ],
                expected_rc=1,
            )

            self.assertEqual(payload["schema"], CLI_ERROR_SCHEMA)
            self.assertEqual(payload["error"]["type"], "ConnectorFetchError")
            self.assertFalse(payload["error"]["retryable"])
            self.assertEqual(payload["error"]["details"]["connector"], "confluence")
            self.assertEqual(_accepted_projection(root), before)
            self.assertFalse((root / "docs" / "source" / "candidates").exists())


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
