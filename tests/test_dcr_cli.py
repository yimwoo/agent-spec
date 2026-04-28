"""Tests for `agentspec dcr` subcommands.

Covers R-125 (DCR-0002).
"""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import main
from agentspec.dcr import parse_dcr


@contextlib.contextmanager
def pushd(path: Path):
    old = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old)


def _seed_workspace(root: Path) -> None:
    (root / "docs" / "change-requests").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "traceability").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "traceability" / "requirements.yml").write_text(
        json.dumps([]), encoding="utf-8"
    )


def _seed_existing_dcr(root: Path, dcr_id: str, classification: str = "implement-now", status: str = "classified") -> Path:
    path = root / "docs" / "change-requests" / f"{dcr_id}-test.md"
    path.write_text(
        f"""# {dcr_id}: Test DCR

| Field | Value |
|---|---|
| Status | {status} |
| Classification | {classification} |
| Submitted | 2026-04-28 |
| Submitted by | tester |
| Decided by | tester |
| Decided on | 2026-04-28 |
| Confidence | high |

## Summary
Test.
""",
        encoding="utf-8",
    )
    return path


class DCRCLICreateTests(unittest.TestCase):
    def test_create_writes_file_with_valid_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            with pushd(root):
                rc = main(["dcr", "create", "--title", "Test idea", "--classification", "spike"])
            self.assertEqual(rc, 0)
            files = list((root / "docs" / "change-requests").glob("DCR-*.md"))
            self.assertEqual(len(files), 1)
            dcr = parse_dcr(files[0])
            self.assertEqual(dcr["classification"], "spike")
            self.assertEqual(dcr["status"], "classified")

    def test_create_auto_numbers_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _seed_existing_dcr(root, "DCR-0001")
            _seed_existing_dcr(root, "DCR-0002")
            with pushd(root):
                rc = main(["dcr", "create", "--title", "Third idea", "--classification", "defer"])
            self.assertEqual(rc, 0)
            new_files = sorted(
                (root / "docs" / "change-requests").glob("DCR-*.md"),
                key=lambda p: p.name,
            )
            self.assertEqual(len(new_files), 3)
            # The newly created file is DCR-0003.
            new_path = next(p for p in new_files if "third" in p.name.lower())
            self.assertTrue(new_path.name.startswith("DCR-0003-"))
            dcr = parse_dcr(new_path)
            self.assertEqual(dcr["id"], "DCR-0003")

    def test_create_rejects_invalid_classification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            with pushd(root), contextlib.redirect_stderr(io.StringIO()):
                # argparse choices reject this by raising SystemExit(2).
                with self.assertRaises(SystemExit) as ctx:
                    main(["dcr", "create", "--title", "Bad", "--classification", "ship-it"])
                self.assertEqual(ctx.exception.code, 2)


class DCRCLIClassifyTests(unittest.TestCase):
    def test_classify_flips_classification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _seed_existing_dcr(root, "DCR-0001", classification="spike")
            with pushd(root):
                rc = main(["dcr", "classify", "DCR-0001", "--to", "implement-now"])
            self.assertEqual(rc, 0)
            dcr = parse_dcr(root / "docs" / "change-requests" / "DCR-0001-test.md")
            self.assertEqual(dcr["classification"], "implement-now")

    def test_classify_unknown_dcr_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            with pushd(root):
                rc = main(["dcr", "classify", "DCR-9999", "--to", "defer"])
            self.assertEqual(rc, 1)


class DCRCLIAcceptTests(unittest.TestCase):
    def test_accept_flips_only_dcr_status_no_cascade(self) -> None:
        """Per DCR-0004 / R-133: dcr accept must not cascade to requirements."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _seed_existing_dcr(root, "DCR-0001", classification="implement-now")
            (root / "docs" / "traceability" / "requirements.yml").write_text(
                json.dumps(
                    [
                        {
                            "id": "R-200",
                            "title": "DCR-derived",
                            "description": "test.",
                            "source_sections": ["D-03"],
                            "priority": "P0",
                            "status": "proposed-pending-acceptance",
                            "confidence": "high",
                            "originating_dcr": "DCR-0001",
                            "acceptance": ["test"],
                            "code_targets": [],
                            "test_targets": [],
                        },
                        {
                            "id": "R-201",
                            "title": "Unrelated DCR",
                            "description": "test.",
                            "source_sections": ["D-03"],
                            "priority": "P1",
                            "status": "proposed-pending-acceptance",
                            "confidence": "high",
                            "originating_dcr": "DCR-0099",
                            "acceptance": ["test"],
                            "code_targets": [],
                            "test_targets": [],
                        },
                    ]
                ),
                encoding="utf-8",
            )
            with pushd(root):
                rc = main(["dcr", "accept", "DCR-0001"])
            self.assertEqual(rc, 0)

            dcr_text = (root / "docs" / "change-requests" / "DCR-0001-test.md").read_text(encoding="utf-8")
            dcr = parse_dcr(root / "docs" / "change-requests" / "DCR-0001-test.md")
            self.assertEqual(dcr["status"], "accepted")
            # R-133: Decided-on row must reflect today's date.
            from datetime import date
            self.assertIn(f"| Decided on | {date.today().isoformat()} |", dcr_text)

            reqs = json.loads(
                (root / "docs" / "traceability" / "requirements.yml").read_text()
            )
            for r in reqs:
                self.assertEqual(
                    r["status"], "proposed-pending-acceptance",
                    f"dcr accept must not cascade to {r['id']}; use `requirement accept` instead.",
                )

    def test_accept_with_no_associated_requirements_is_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _seed_existing_dcr(root, "DCR-0001", classification="implement-now")
            (root / "docs" / "traceability" / "requirements.yml").write_text(
                json.dumps([]), encoding="utf-8"
            )
            with pushd(root):
                rc = main(["dcr", "accept", "DCR-0001"])
            self.assertEqual(rc, 0)
            dcr = parse_dcr(root / "docs" / "change-requests" / "DCR-0001-test.md")
            self.assertEqual(dcr["status"], "accepted")


class DCRCLIListTests(unittest.TestCase):
    def test_list_prints_one_line_per_dcr(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _seed_existing_dcr(root, "DCR-0001", classification="spike", status="classified")
            _seed_existing_dcr(root, "DCR-0002", classification="implement-now", status="accepted")

            buffer = io.StringIO()
            with pushd(root), contextlib.redirect_stdout(buffer):
                rc = main(["dcr", "list"])
            self.assertEqual(rc, 0)
            output = buffer.getvalue()
            self.assertIn("DCR-0001", output)
            self.assertIn("DCR-0002", output)
            self.assertIn("spike", output)
            self.assertIn("implement-now", output)
            self.assertIn("accepted", output)

    def test_list_on_empty_workspace_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            with pushd(root):
                rc = main(["dcr", "list"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
