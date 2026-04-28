import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.runner import RUNNER_DEMO_SCHEMA, RUNNER_RESULT_SCHEMA, run_demo


class RunnerDemoTests(unittest.TestCase):
    def test_run_demo_executes_package_result_flow_and_updates_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            demo = run_demo(root, run_id="demo-001", runner="generic")

            self.assertEqual(demo["schema"], RUNNER_DEMO_SCHEMA)
            self.assertEqual(demo["run_id"], "demo-001")
            self.assertEqual(demo["final_next_action"], "complete")
            self.assertFalse(demo["final_should_execute"])
            self.assertEqual([item["kind"] for item in demo["transcript"]], ["package", "runner_result", "package"])

            first_package = demo["transcript"][0]["package"]
            result = demo["transcript"][1]["result"]
            final_package = demo["transcript"][2]["package"]
            self.assertTrue(first_package["should_execute"])
            self.assertEqual(result["schema"], RUNNER_RESULT_SCHEMA)
            self.assertEqual(result["touched_paths"], ["agent/context-packs/T-023-local-runner-demo-e2e.md"])
            self.assertEqual(final_package["next_action"], "complete")
            self.assertIsNone(final_package["execution"]["stdin"])

            state = load_data(root / "agent" / "runs" / "demo-001" / "state.yml")
            self.assertEqual(state["status"], "complete")
            ledger = load_data(root / "agent" / "task-ledger.yml")
            entry = ledger["tasks"]["agent/context-packs/T-023-local-runner-demo-e2e.md"]
            self.assertEqual(entry["status"], "complete")
            self.assertEqual(entry["verification"]["status"], "passed")

    def test_cli_run_demo_json_outputs_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "demo",
                        "--run-id",
                        "demo-cli",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            demo = json.loads(output.getvalue())
            self.assertEqual(demo["schema"], RUNNER_DEMO_SCHEMA)
            self.assertEqual(demo["final_next_action"], "complete")
            self.assertEqual([item["kind"] for item in demo["transcript"]], ["package", "runner_result", "package"])

    def test_run_demo_can_show_policy_stop_in_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            demo = run_demo(
                root,
                run_id="demo-policy",
                runner="generic",
                touched_paths=["docs/source/sections.yml"],
            )

            self.assertEqual(demo["final_next_action"], "stop")
            self.assertEqual(demo["final_state"]["status"], "halted")
            final_review = demo["final_package"]["step"]["review"]
            self.assertEqual(final_review["decision"], "halt")
            self.assertIn("forbidden_path", final_review["policy_flags"])


def _seed(root: Path) -> None:
    (root / ".agentspec").mkdir(parents=True)
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {"id": "R-007", "status": "accepted", "priority": "P1"},
            {"id": "R-127", "status": "proposed-pending-acceptance", "priority": "P2"},
            {"id": "R-129", "status": "proposed-pending-acceptance", "priority": "P2"},
        ],
    )
    (root / ".agentspec" / "config.yml").write_text(
        json.dumps(
            {
                "version": 1,
                "agent_profiles": {
                    "main_executor": {"adapter": "current-host", "model": "host-default"},
                    "continuation_reviewer": {"adapter": "static", "model": "static-reviewer"},
                    "quality_reviewer": {"adapter": "static", "model": "static-quality"},
                },
                "supervised_runs": {
                    "executor_profile": "main_executor",
                    "continuation_reviewer_profile": "continuation_reviewer",
                    "quality_reviewer_profile": "quality_reviewer",
                    "max_iterations": {"implementation": 3},
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "agent" / "context-packs" / "T-023-local-runner-demo-e2e.md").write_text(
        """# T-023: Local Runner Demo E2E

Type: `implementation`

## Requirements

- `R-007` CLI
- `R-127` Supervised run
- `R-129` Reviewer feedback

## Allowed Paths

- `agent/context-packs/T-023-local-runner-demo-e2e.md`
- `agentspec/runner.py`
- `agentspec/cli.py`
- `tests/test_runner_demo.py`
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
