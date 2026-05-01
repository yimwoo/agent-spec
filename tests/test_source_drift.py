"""Tests for registered source drift checks (T-055 / R-156, R-157, R-158)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data


ACCEPTED_MARKDOWN = """# Payments Design

## Overview

The accepted design uses the V1 payments API.
"""

CHANGED_MARKDOWN = """# Payments Design

## Overview

The accepted design uses the V2 payments API.
"""

AUTH_MARKDOWN = """# Auth Design

## Overview

Auth tokens are validated before use.
"""


class SourceDriftTests(unittest.TestCase):
    def test_source_check_unchanged_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _seed_accepted_markdown(root, "payments-design", ACCEPTED_MARKDOWN)
            _add_source(root, "payments-design", source)
            before_projection = _accepted_projection(root)
            before_candidates = _candidate_ids(root)

            payload = _run_json(
                ["--root", str(root), "source", "check", "payments-design", "--json"]
            )

            self.assertEqual(payload["schema"], "agentspec.source.check.v0")
            self.assertEqual(payload["summary"]["unchanged"], 1)
            result = payload["results"][0]
            self.assertEqual(result["status"], "unchanged")
            self.assertIsNone(result.get("candidate_snapshot_id"))
            self.assertEqual(_accepted_projection(root), before_projection)
            self.assertEqual(_candidate_ids(root), before_candidates)

    def test_changed_source_check_reports_next_command_without_writing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _seed_accepted_markdown(root, "payments-design", ACCEPTED_MARKDOWN)
            _add_source(root, "payments-design", source)
            source.write_text(CHANGED_MARKDOWN, encoding="utf-8")
            before_projection = _accepted_projection(root)
            before_candidates = _candidate_ids(root)

            payload = _run_json(
                ["--root", str(root), "source", "check", "payments-design", "--json"]
            )

            result = payload["results"][0]
            self.assertEqual(result["status"], "changed")
            self.assertTrue(result["baseline_content_hash"].startswith("sha256:"))
            self.assertTrue(result["current_content_hash"].startswith("sha256:"))
            self.assertNotEqual(result["baseline_content_hash"], result["current_content_hash"])
            self.assertIn("--as-candidate", result["next_command"])
            self.assertNotIn("candidate_snapshot_id", result)
            self.assertEqual(_accepted_projection(root), before_projection)
            self.assertEqual(_candidate_ids(root), before_candidates)

    def test_changed_source_check_as_candidate_writes_candidate_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _seed_accepted_markdown(root, "payments-design", ACCEPTED_MARKDOWN)
            _add_source(root, "payments-design", source)
            source.write_text(CHANGED_MARKDOWN, encoding="utf-8")
            before_projection = _accepted_projection(root)

            payload = _run_json(
                [
                    "--root",
                    str(root),
                    "source",
                    "check",
                    "payments-design",
                    "--as-candidate",
                    "--json",
                ]
            )

            result = payload["results"][0]
            self.assertEqual(result["status"], "changed")
            self.assertEqual(result["candidate_snapshot_id"], "SRC-0002")
            candidate_dir = root / result["candidate_path"]
            self.assertTrue((candidate_dir / "spec-document.yml").exists())
            self.assertEqual(_accepted_projection(root), before_projection)

    def test_source_check_all_reports_changed_unchanged_failed_and_policy_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payments = _seed_accepted_markdown(root, "payments-design", ACCEPTED_MARKDOWN)
            auth = root / "auth.md"
            auth.write_text(AUTH_MARKDOWN, encoding="utf-8")
            _write_mixed_registry(root, payments, auth)
            before_projection = _accepted_projection(root)

            payload = _run_json(
                ["--root", str(root), "source", "check", "--all", "--json"],
                expected_rc=1,
            )

            self.assertEqual(payload["schema"], "agentspec.source.check.v0")
            self.assertEqual(
                payload["summary"],
                {
                    "unchanged": 1,
                    "changed": 1,
                    "failed": 1,
                    "policy-blocked": 1,
                },
            )
            by_key = {result["source_key"]: result for result in payload["results"]}
            self.assertEqual(by_key["payments-design"]["status"], "unchanged")
            self.assertEqual(by_key["auth-design"]["status"], "changed")
            self.assertEqual(by_key["missing-design"]["status"], "failed")
            self.assertIn("retryable", by_key["missing-design"]["error"])
            self.assertEqual(by_key["restricted-design"]["status"], "policy-blocked")
            self.assertIn("storage_policy", by_key["restricted-design"]["policy_errors"][0]["code"])
            self.assertEqual(_accepted_projection(root), before_projection)

    def test_confluence_fixture_check_resolves_relative_uri_against_root(self) -> None:
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
                    "body": ACCEPTED_MARKDOWN,
                },
            )
            _run_json(
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
                    "confluence-page.json",
                    "--kind",
                    "confluence",
                    "--classification",
                    "internal",
                    "--storage-mode",
                    "committed",
                ]
            )

            payload = _run_json(
                ["--root", str(root), "source", "check", "payments-design", "--json"]
            )

            self.assertEqual(payload["results"][0]["status"], "unchanged")


def _seed_accepted_markdown(root: Path, source_key: str, markdown: str) -> Path:
    _run(["--root", str(root), "init"])
    source = root / f"{source_key}.md"
    source.write_text(markdown, encoding="utf-8")
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
            source_key,
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
    return source


def _add_source(root: Path, source_key: str, remote_uri: Path) -> None:
    _run(
        [
            "--root",
            str(root),
            "source",
            "add",
            source_key,
            str(remote_uri),
            "--kind",
            "markdown",
            "--classification",
            "internal",
            "--storage-mode",
            "committed",
        ]
    )


def _write_mixed_registry(root: Path, payments: Path, auth: Path) -> None:
    accepted = load_data(root / "docs" / "source" / "sources.yml")[0]
    write_data(
        root / "docs" / "source" / "source-registry.yml",
        {
            "schema": "agentspec.source_registry.v0",
            "sources": [
                {
                    "source_key": "payments-design",
                    "kind": "markdown",
                    "remote_uri": str(payments),
                    "classification": "internal",
                    "storage_mode": "committed",
                    "accepted_snapshot_id": accepted["id"],
                    "last_seen_content_hash": accepted["content_hash"],
                },
                {
                    "source_key": "auth-design",
                    "kind": "markdown",
                    "remote_uri": str(auth),
                    "classification": "internal",
                    "storage_mode": "committed",
                },
                {
                    "source_key": "missing-design",
                    "kind": "markdown",
                    "remote_uri": str(root / "missing.md"),
                    "classification": "internal",
                    "storage_mode": "committed",
                },
                {
                    "source_key": "restricted-design",
                    "kind": "markdown",
                    "remote_uri": str(root / "restricted.md"),
                    "classification": "restricted",
                    "storage_mode": "committed",
                },
            ],
        },
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


def _candidate_ids(root: Path) -> list[str]:
    candidates = root / "docs" / "source" / "candidates"
    if not candidates.exists():
        return []
    return sorted(path.name for path in candidates.iterdir() if path.is_dir())


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
