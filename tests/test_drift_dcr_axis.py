"""Tests for R-126: drift report surfaces the originating DCR per file."""

import json
import tempfile
import unittest
from pathlib import Path

from agentspec.drift import run_drift


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_pack(root: Path, filename: str, body: str) -> None:
    pack_dir = root / "agent" / "context-packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / filename).write_text(body, encoding="utf-8")


def _write_min_workspace(root: Path) -> None:
    """A minimal workspace seed: one accepted requirement so the drift
    report has something to assess against."""
    _write_json(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {
                "id": "R-200",
                "title": "Touch the fixture target",
                "description": "Tests for the drift DCR axis fixture target.",
                "source_sections": ["D-03"],
                "priority": "P0",
                "status": "accepted",
                "confidence": "medium",
                "acceptance": [],
                "code_targets": ["agentspec/fixture_target.py"],
                "test_targets": ["tests/test_cli_workflow.py"],
            }
        ],
    )
    _write_json(
        root / "docs" / "source" / "sections.yml",
        [{"id": "D-03", "heading_path": ["3. Goals"]}],
    )


class DriftReportDCRColumnTests(unittest.TestCase):
    def test_drift_report_includes_dcr_column_for_single_dcr_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_min_workspace(root)
            _write_pack(
                root,
                "T-201-fixture.md",
                "# T-201: Fixture Pack\n\nType: `implementation`\n"
                "Originating DCR: `DCR-0099-fixture`\n\n"
                "## Requirements\n\n- `R-200` Touch the fixture target\n\n"
                "## Allowed Paths\n\n- `agentspec/fixture_target.py`\n",
            )
            (root / "drift.patch").write_text(
                "diff --git a/agentspec/fixture_target.py b/agentspec/fixture_target.py\n"
                "--- a/agentspec/fixture_target.py\n"
                "+++ b/agentspec/fixture_target.py\n"
                "@@ -0,0 +1,1 @@\n"
                "+def fixture(): pass\n",
                encoding="utf-8",
            )

            run_drift(root, diff_ref="drift.patch")
            report = (root / "reports" / "drift" / "latest.md").read_text(encoding="utf-8")

            self.assertIn("| File | Verdict | Requirements | Context Packs | DCRs | Evidence |", report)
            self.assertIn("`DCR-0099`", report)

    def test_drift_report_includes_multiple_dcrs_for_multi_dcr_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_min_workspace(root)
            _write_pack(
                root,
                "T-202-fixture.md",
                "# T-202: Multi-DCR Pack\n\nType: `implementation`\n"
                "Originating DCRs: `DCR-0098-first`, `DCR-0099-second`\n\n"
                "## Requirements\n\n- `R-200` Touch the fixture target\n\n"
                "## Allowed Paths\n\n- `agentspec/fixture_target.py`\n",
            )
            (root / "drift.patch").write_text(
                "diff --git a/agentspec/fixture_target.py b/agentspec/fixture_target.py\n"
                "--- a/agentspec/fixture_target.py\n"
                "+++ b/agentspec/fixture_target.py\n"
                "@@ -0,0 +1,1 @@\n"
                "+def fixture(): pass\n",
                encoding="utf-8",
            )

            run_drift(root, diff_ref="drift.patch")
            report = (root / "reports" / "drift" / "latest.md").read_text(encoding="utf-8")

            self.assertIn("`DCR-0098`", report)
            self.assertIn("`DCR-0099`", report)

    def test_drift_report_dcr_column_empty_for_pack_without_originating_dcr(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_min_workspace(root)
            # Pack with no Originating DCR line — early-style pack.
            _write_pack(
                root,
                "T-203-no-dcr.md",
                "# T-203: No-DCR Pack\n\nType: `implementation`\n\n"
                "## Requirements\n\n- `R-200` Touch the fixture target\n\n"
                "## Allowed Paths\n\n- `agentspec/fixture_target.py`\n",
            )
            (root / "drift.patch").write_text(
                "diff --git a/agentspec/fixture_target.py b/agentspec/fixture_target.py\n"
                "--- a/agentspec/fixture_target.py\n"
                "+++ b/agentspec/fixture_target.py\n"
                "@@ -0,0 +1,1 @@\n"
                "+def fixture(): pass\n",
                encoding="utf-8",
            )

            run_drift(root, diff_ref="drift.patch")
            report = (root / "reports" / "drift" / "latest.md").read_text(encoding="utf-8")

            # Find the file's row and confirm the DCR cell is the empty marker.
            row = next(
                line for line in report.splitlines()
                if line.startswith("| ") and "`agentspec/fixture_target.py`" in line
            )
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            # File | Verdict | Requirements | Context Packs | DCRs | Evidence
            self.assertEqual(cells[4], "-", f"expected empty DCR cell; row was: {row}")

    def test_drift_report_dcr_column_empty_for_unrelated_file(self) -> None:
        """A file that doesn't match any pack's Allowed Paths produces no
        context-pack mapping and therefore no DCR mapping."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_min_workspace(root)
            _write_pack(
                root,
                "T-204-fixture.md",
                "# T-204: DCR Pack\n\nType: `implementation`\n"
                "Originating DCR: `DCR-0099-fixture`\n\n"
                "## Allowed Paths\n\n- `agentspec/fixture_target.py`\n",
            )
            # Diff touches a file that is NOT in the pack's Allowed Paths.
            (root / "drift.patch").write_text(
                "diff --git a/agentspec/unrelated.py b/agentspec/unrelated.py\n"
                "--- a/agentspec/unrelated.py\n"
                "+++ b/agentspec/unrelated.py\n"
                "@@ -0,0 +1,1 @@\n"
                "+def unrelated(): pass\n",
                encoding="utf-8",
            )

            run_drift(root, diff_ref="drift.patch")
            report = (root / "reports" / "drift" / "latest.md").read_text(encoding="utf-8")

            row = next(
                line for line in report.splitlines()
                if line.startswith("| ") and "`agentspec/unrelated.py`" in line
            )
            cells = [cell.strip() for cell in row.strip("|").split("|")]
            self.assertEqual(cells[4], "-", f"expected empty DCR cell; row was: {row}")


if __name__ == "__main__":
    unittest.main()
