import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import write_data
from agentspec.outcome import OUTCOME_STATUS_SCHEMA, build_outcome_status, format_outcome_status
from agentspec.status import build_project_status


class OutcomeCliTests(unittest.TestCase):
    def test_outcome_status_reports_blocked_gates_and_next_actions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_blocked_outcomes(root)

            status = build_outcome_status(root)

            self.assertEqual(status["schema"], OUTCOME_STATUS_SCHEMA)
            self.assertEqual(status["readiness"], "blocked")
            self.assertEqual(status["score"], 50)
            self.assertEqual(status["counts"]["outcomes"], 1)
            self.assertEqual(status["counts"]["required_gates"], 2)
            self.assertEqual(status["counts"]["ready_required_gates"], 1)
            self.assertEqual(status["counts"]["blocked_required_gates"], 1)
            self.assertEqual(status["blockers"][0]["gate_id"], "G-002")
            self.assertIn("Wire real Run Detail to SSE", status["next_actions"])

            text = format_outcome_status(status)
            self.assertIn("Readiness: blocked", text)
            self.assertIn("O-001/G-002", text)
            self.assertIn("Wire real Run Detail to SSE", text)

    def test_outcome_cli_json_and_human_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_blocked_outcomes(root)

            json_output = io.StringIO()
            with redirect_stdout(json_output):
                code = main(["--root", str(root), "outcome", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(json_output.getvalue())
            self.assertEqual(payload["schema"], OUTCOME_STATUS_SCHEMA)
            self.assertEqual(payload["readiness"], "blocked")

            human_output = io.StringIO()
            with redirect_stdout(human_output):
                code = main(["--root", str(root), "outcome"])

            self.assertEqual(code, 0)
            self.assertIn("AgentSpec Product Outcomes", human_output.getvalue())
            self.assertIn("required gates 1/2", human_output.getvalue())

    def test_status_includes_outcome_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_blocked_outcomes(root)
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            write_data(root / "docs" / "discovery" / "readiness.yml", {"score": 100, "mode": "normal-implementation"})

            status = build_project_status(root)

            self.assertIn("outcomes", status)
            self.assertEqual(status["outcomes"]["schema"], OUTCOME_STATUS_SCHEMA)
            self.assertEqual(status["outcomes"]["readiness"], "blocked")


def _write_blocked_outcomes(root: Path) -> None:
    write_data(
        root / "agent" / "outcomes.yml",
        {
            "schema": "agentspec.outcomes.v0",
            "outcomes": [
                {
                    "id": "O-001",
                    "title": "Run existing YAML testcase E2E",
                    "gates": [
                        {
                            "id": "G-001",
                            "title": "Backend run API works",
                            "status": "passed",
                            "required": True,
                            "evidence": [{"kind": "pytest", "path": "tests/test_run.py"}],
                        },
                        {
                            "id": "G-002",
                            "title": "Live per-step UI status works",
                            "status": "blocked",
                            "required": True,
                            "next_action": "Wire real Run Detail to SSE",
                        },
                    ],
                }
            ],
        },
    )


if __name__ == "__main__":
    unittest.main()
