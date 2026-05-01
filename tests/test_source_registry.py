"""Tests for source registry schema and CLI (T-055 / R-155, R-158)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import CLI_ERROR_SCHEMA, main
from agentspec.io import load_data, write_data


class SourceRegistryTests(unittest.TestCase):
    def test_source_add_writes_registry_without_mutating_accepted_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _run(["--root", str(root), "init"])
            before = _accepted_projection(root)

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "source",
                    "add",
                    "payments-design",
                    "./payments-design.md",
                    "--kind",
                    "markdown",
                    "--classification",
                    "internal",
                    "--storage-mode",
                    "committed",
                    "--poll-cadence",
                    "daily",
                    "--json",
                ]
            )

            self.assertEqual(payload["schema"], "agentspec.source.add.v0")
            self.assertEqual(payload["record"]["source_key"], "payments-design")
            self.assertEqual(payload["record"]["poll"], {"enabled": True, "cadence": "daily"})

            registry = load_data(root / "docs" / "source" / "source-registry.yml")
            self.assertEqual(registry["schema"], "agentspec.source_registry.v0")
            self.assertEqual(len(registry["sources"]), 1)
            self.assertEqual(registry["sources"][0]["remote_uri"], "./payments-design.md")
            self.assertEqual(_accepted_projection(root), before)

            list_payload = _run_json(
                ["--root", str(root), "source", "list", "--json"]
            )
            self.assertEqual(list_payload["schema"], "agentspec.source.list.v0")
            self.assertEqual(list_payload["sources"], registry["sources"])

    def test_source_add_updates_existing_logical_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "payments-v1.md"
            source.write_text("# Payments\n\n## Overview\n\nV1\n", encoding="utf-8")
            _run(["--root", str(root), "init"])
            _run_json(
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
            _run(
                [
                    "--root",
                    str(root),
                    "source",
                    "add",
                    "payments-design",
                    "./payments-v1.md",
                    "--kind",
                    "markdown",
                    "--classification",
                    "internal",
                    "--storage-mode",
                    "committed",
                ]
            )

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "source",
                    "add",
                    "payments-design",
                    "./payments-v2.md",
                    "--kind",
                    "markdown",
                    "--classification",
                    "internal",
                    "--storage-mode",
                    "committed",
                    "--json",
                ]
            )

            registry = load_data(root / "docs" / "source" / "source-registry.yml")
            self.assertEqual(payload["action"], "updated")
            self.assertEqual(len(registry["sources"]), 1)
            self.assertEqual(registry["sources"][0]["remote_uri"], "./payments-v2.md")
            self.assertEqual(registry["sources"][0]["accepted_snapshot_id"], "SRC-0001")
            self.assertTrue(registry["sources"][0]["last_seen_content_hash"].startswith("sha256:"))

    def test_source_add_rejects_invalid_storage_policy_with_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "source",
                    "add",
                    "payroll-design",
                    "./payroll.md",
                    "--kind",
                    "markdown",
                    "--classification",
                    "restricted",
                    "--storage-mode",
                    "committed",
                    "--json",
                ],
                expected_rc=1,
            )

            self.assertEqual(payload["schema"], CLI_ERROR_SCHEMA)
            self.assertEqual(payload["error"]["type"], "SourceRegistryValidationError")
            self.assertIn(
                "storage_policy",
                {error["code"] for error in payload["error"]["details"]["errors"]},
            )
            self.assertFalse((root / "docs" / "source" / "source-registry.yml").exists())

    def test_source_list_rejects_duplicate_registry_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_data(
                root / "docs" / "source" / "source-registry.yml",
                {
                    "schema": "agentspec.source_registry.v0",
                    "sources": [
                        {
                            "source_key": "payments-design",
                            "kind": "markdown",
                            "remote_uri": "./payments-v1.md",
                            "classification": "internal",
                            "storage_mode": "committed",
                        },
                        {
                            "source_key": "payments-design",
                            "kind": "markdown",
                            "remote_uri": "./payments-v2.md",
                            "classification": "internal",
                            "storage_mode": "committed",
                        },
                    ],
                },
            )

            payload = _run_json(
                ["--root", str(root), "source", "list", "--json"],
                expected_rc=1,
            )

            self.assertEqual(payload["schema"], CLI_ERROR_SCHEMA)
            self.assertIn(
                "duplicate_source_key",
                {error["code"] for error in payload["error"]["details"]["errors"]},
            )


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
