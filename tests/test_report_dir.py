"""Tests for DCR-0020 / T-037: --report-dir on aspec doctor + drift.

The acceptance contract is symmetric for both commands:

- Default behavior unchanged.
- --report-dir <path> writes under <path>/<command>/, never inside the
  target's reports/ tree.
- A read-only destination raises a clear error before analysis runs.
"""

from __future__ import annotations

import os
import stat
import tempfile
import unittest
from pathlib import Path

from agentspec.doctor import run_doctor
from agentspec.drift import run_drift


def _make_target(root: Path) -> None:
    """Minimal AgentSpec-shaped fixture so doctor and drift can run."""
    (root / "agentspec").mkdir(parents=True, exist_ok=True)
    (root / "agentspec" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "README.md").write_text("# fixture\n", encoding="utf-8")
    (root / "docs" / "traceability").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "traceability" / "requirements.yml").write_text("[]\n", encoding="utf-8")
    (root / "docs" / "source").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "source" / "sections.yml").write_text("[]\n", encoding="utf-8")
    (root / "agent" / "context-packs").mkdir(parents=True, exist_ok=True)


class DoctorReportDirTests(unittest.TestCase):
    def test_default_writes_under_root_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_target(root)

            run_doctor(root)

            self.assertTrue((root / "reports" / "doctor" / "repo-scan.yml").exists())
            self.assertTrue((root / "reports" / "doctor" / "agent-readiness.md").exists())

    def test_report_dir_redirects_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "target"
            external = Path(tmp) / "external-reports"
            _make_target(root)

            run_doctor(root, report_dir=external)

            self.assertTrue((external / "doctor" / "repo-scan.yml").exists())
            self.assertTrue((external / "doctor" / "agent-readiness.md").exists())
            # Target's own reports/ is not created.
            self.assertFalse((root / "reports" / "doctor").exists())

    def test_readonly_destination_raises_before_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "target"
            readonly = Path(tmp) / "readonly"
            _make_target(root)
            readonly.mkdir()
            os.chmod(readonly, stat.S_IRUSR | stat.S_IXUSR)

            try:
                with self.assertRaises(PermissionError) as caught:
                    run_doctor(root, report_dir=readonly)
                self.assertIn(str(readonly / "doctor"), str(caught.exception))
                # Analysis must not have produced output anywhere.
                self.assertFalse((root / "reports" / "doctor").exists())
            finally:
                os.chmod(readonly, stat.S_IRWXU)


class DriftReportDirTests(unittest.TestCase):
    def test_default_writes_under_root_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_target(root)

            path = run_drift(root)

            self.assertEqual(path, root / "reports" / "drift" / "latest.md")
            self.assertTrue(path.exists())

    def test_report_dir_redirects_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "target"
            external = Path(tmp) / "external-reports"
            _make_target(root)

            path = run_drift(root, report_dir=external)

            self.assertEqual(path, external / "drift" / "latest.md")
            self.assertTrue(path.exists())
            self.assertFalse((root / "reports" / "drift").exists())

    def test_readonly_destination_raises_before_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "target"
            readonly = Path(tmp) / "readonly"
            _make_target(root)
            readonly.mkdir()
            os.chmod(readonly, stat.S_IRUSR | stat.S_IXUSR)

            try:
                with self.assertRaises(PermissionError) as caught:
                    run_drift(root, report_dir=readonly)
                self.assertIn(str(readonly / "drift"), str(caught.exception))
                self.assertFalse((root / "reports" / "drift").exists())
            finally:
                os.chmod(readonly, stat.S_IRWXU)


if __name__ == "__main__":
    unittest.main()
