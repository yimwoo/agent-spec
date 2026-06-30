"""Integrity checks for public controlled-evaluation assets."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from agentspec.eval import load_evaluation_manifest
from agentspec.io import load_data


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "benchmarks" / "controlled-evals" / "EXP-lifecycle-pilot"


class EvaluationAssetTests(unittest.TestCase):
    def test_pilot_manifest_pins_public_task_and_hidden_oracle_digests(self) -> None:
        manifest = load_evaluation_manifest(PILOT / "manifest.yml")
        task = manifest["tasks"][0]

        self.assertEqual(manifest["id"], "EXP-lifecycle-pilot")
        self.assertEqual({provider["id"] for provider in manifest["providers"]}, {"codex", "claude"})
        self.assertEqual({condition["agentspec"] for condition in manifest["conditions"]}, {True, False})
        self.assertEqual(task["revision"], _sha256(ROOT / task["source"]))
        self.assertEqual(task["oracle"]["revision"], _sha256(PILOT / "oracle" / "identifier_oracle.py"))

    def test_fixture_starts_with_passing_public_tests_and_failing_hidden_oracle(self) -> None:
        fixture = PILOT / "fixture"
        public = subprocess.run(
            ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=fixture,
            check=False,
            text=True,
            capture_output=True,
        )
        environment = {**os.environ, "PYTHONPATH": str(fixture / "src")}
        oracle = subprocess.run(
            ["python", str(PILOT / "oracle" / "identifier_oracle.py")],
            cwd=fixture,
            env=environment,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(public.returncode, 0, public.stdout + public.stderr)
        self.assertNotEqual(oracle.returncode, 0, oracle.stdout + oracle.stderr)
        self.assertIn("creme-brulee", oracle.stdout + oracle.stderr)

    def test_workspace_preparer_isolates_agentspec_treatment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            control = base / "control"
            treatment = base / "with-agentspec"
            environment = {**os.environ, "PYTHONPATH": str(ROOT)}
            for destination, condition in [
                (control, "control"),
                (treatment, "with-agentspec"),
            ]:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(PILOT / "prepare_workspace.py"),
                        str(destination),
                        "--condition",
                        condition,
                    ],
                    cwd=ROOT,
                    env=environment,
                    check=False,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue((destination / ".git").is_dir())

            self.assertFalse((control / ".agentspec").exists())
            self.assertFalse((control / "agent").exists())
            self.assertTrue((treatment / ".agentspec" / "config.yml").is_file())
            self.assertTrue(
                (treatment / "agent" / "context-packs" / "T-001-normalize-identifiers.md").is_file()
            )
            self.assertEqual(
                load_data(treatment / "docs" / "discovery" / "readiness.yml")["score"],
                100,
            )

    def test_public_pilot_report_does_not_claim_results_without_cells(self) -> None:
        report = (ROOT / "docs" / "evaluations" / "EXP-lifecycle-pilot.md").read_text(encoding="utf-8")

        self.assertIn("execution blocked; no provider cells recorded", report)
        self.assertIn("Expected cells: 4", report)
        self.assertIn("Recorded cells: 0", report)
        self.assertIn("no AgentSpec-versus-control conclusion", report)


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


if __name__ == "__main__":
    unittest.main()
