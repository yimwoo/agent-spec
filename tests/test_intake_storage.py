"""Tests for intake storage-mode enforcement (T-050 / R-152)."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data


RESTRICTED_MARKDOWN = """# Restricted Launch Design

## Security

The launch code is swordfish and must never appear in prompts.
"""


class IntakeStorageModeTests(unittest.TestCase):
    def test_restricted_pointer_only_promotion_stores_uri_and_hashes_without_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_restricted_source(root)
            _run(["--root", str(root), "init"])

            import_payload = _import_restricted_pointer_only(root, source)
            candidate_dir = root / import_payload["candidate_path"]
            self.assertFalse((candidate_dir / "source.md").exists())

            promote_payload = _run_json(
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

            accepted_source = promote_payload["accepted_source"]
            self.assertEqual(accepted_source["classification"], "restricted")
            self.assertEqual(accepted_source["storage_mode"], "pointer-only")
            self.assertEqual(accepted_source["uri"], str(source.resolve()))
            self.assertEqual(accepted_source["remote_uri"], str(source.resolve()))
            self.assertTrue(accepted_source["content_hash"].startswith("sha256:"))
            self.assertTrue(accepted_source["normalized_hash"].startswith("sha256:"))
            self.assertFalse(
                (root / "docs" / "source" / "src-0001-restricted-launch.md").exists()
            )

            accepted_sections = load_data(root / "docs" / "source" / "sections.yml")
            self.assertEqual(accepted_sections[0]["id"], "restricted-launch:D-01")
            self.assertEqual(accepted_sections[0]["source_key"], "restricted-launch")
            self.assertTrue(accepted_sections[0]["content_hash"].startswith("sha256:"))

    def test_compile_redacts_restricted_pointer_only_source_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_restricted_source(root)
            _run(["--root", str(root), "init"])
            _import_restricted_pointer_only(root, source)
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

            _run(["--root", str(root), "compile"])

            spec_text = "\n".join(
                path.read_text(encoding="utf-8")
                for path in (root / "docs" / "spec").glob("*.md")
            )
            self.assertNotIn("swordfish", spec_text)
            self.assertIn("Source content withheld", spec_text)
            self.assertIn("classification=restricted", spec_text)
            self.assertIn("storage_mode=pointer-only", spec_text)

    def test_task_context_pack_redacts_restricted_pointer_only_source_body(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = _write_restricted_source(root)
            _run(["--root", str(root), "init"])
            _import_restricted_pointer_only(root, source)
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
            _seed_requirement_for_restricted_section(root)

            _run(
                [
                    "--root",
                    str(root),
                    "task",
                    "create",
                    "--requirement",
                    "R-900",
                    "--title",
                    "Implement restricted launch handling",
                ]
            )

            pack_text = next((root / "agent" / "context-packs").glob("T-*.md")).read_text(
                encoding="utf-8"
            )
            self.assertNotIn("swordfish", pack_text)
            self.assertIn("Source content withheld", pack_text)
            self.assertIn("classification=restricted", pack_text)
            self.assertIn("storage_mode=pointer-only", pack_text)


def _write_restricted_source(root: Path) -> Path:
    source = root / "restricted-launch.md"
    source.write_text(RESTRICTED_MARKDOWN, encoding="utf-8")
    return source


def _import_restricted_pointer_only(root: Path, source: Path) -> dict[str, object]:
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
            "restricted-launch",
            "--classification",
            "restricted",
            "--storage-mode",
            "pointer-only",
            "--as-candidate",
            "--json",
        ]
    )


def _seed_requirement_for_restricted_section(root: Path) -> None:
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {
                "id": "R-900",
                "title": "Restricted launch handling",
                "description": "Implementation handles restricted launch data.",
                "source_sections": ["restricted-launch:D-01"],
                "priority": "P0",
                "status": "accepted",
                "confidence": "high",
                "acceptance": [
                    "Task context can cite restricted source metadata without source body text."
                ],
                "code_targets": ["agentspec/intake.py"],
                "test_targets": ["tests/test_intake_storage.py"],
            }
        ],
    )
    write_data(
        root / "docs" / "discovery" / "readiness.yml",
        {"score": 100, "mode": "normal-implementation", "summary": "Ready."},
    )


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


def _run_json(args: list[str]) -> dict[str, object]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        rc = main(args)
    if rc != 0:
        raise AssertionError(
            f"command returned rc={rc}: {args}\n"
            f"stdout={stdout.getvalue()}\nstderr={stderr.getvalue()}"
        )
    if stderr.getvalue():
        raise AssertionError(stderr.getvalue())
    return json.loads(stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
