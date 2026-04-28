import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import write_data
from agentspec.run import step_run


PROMPT = "Want me to proceed with T-020, or pick one of the others?"


class SupervisedRunStepTests(unittest.TestCase):
    def test_step_selects_next_task_starts_run_and_returns_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            result = step_run(root, run_id="step-001")

            self.assertEqual(result["schema"], "agentspec.harness_step.v0")
            self.assertTrue(result["started"])
            self.assertEqual(result["next_action"], "continue_executor")
            self.assertEqual(result["selected_task"]["id"], "T-020")
            self.assertEqual(result["state"]["status"], "started")
            self.assertIsNotNone(result["handoff"])
            self.assertIn("Start the active context pack.", result["prompt"])
            self.assertIn("agent/context-packs/T-020-harness-step-command.md", result["prompt"])

    def test_step_resumes_auto_continue_and_returns_next_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            step_run(root, run_id="step-001")

            result = step_run(root, run_id="step-001", executor_output=PROMPT)

            self.assertFalse(result["started"])
            self.assertEqual(result["next_action"], "continue_executor")
            self.assertEqual(result["review"]["decision"], "auto_continue")
            self.assertEqual(result["state"]["status"], "running")
            self.assertIn("Continue with T-020", result["handoff"]["reviewer_message"])
            self.assertIn("Continue with T-020", result["prompt"])

    def test_step_returns_await_human_without_prompt_for_paused_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            step_run(root, run_id="step-001")

            result = step_run(root, run_id="step-001", executor_output="Should I continue?")

            self.assertEqual(result["next_action"], "await_human")
            self.assertEqual(result["review"]["decision"], "pause_for_human")
            self.assertEqual(result["state"]["status"], "paused")
            self.assertIsNone(result["handoff"])
            self.assertIsNone(result["prompt"])

    def test_step_returns_complete_without_prompt_for_completed_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            step_run(root, run_id="step-001")

            result = step_run(
                root,
                run_id="step-001",
                executor_output="Done. Acceptance criteria are met.",
                touched_paths=["agentspec/run.py"],
                test_status="passed",
            )

            self.assertEqual(result["next_action"], "complete")
            self.assertEqual(result["review"]["decision"], "complete")
            self.assertEqual(result["state"]["status"], "complete")
            self.assertIsNone(result["handoff"])
            self.assertIsNone(result["prompt"])

    def test_cli_step_json_outputs_harness_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "run", "step", "--run-id", "step-cli", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], "agentspec.harness_step.v0")
            self.assertEqual(payload["next_action"], "continue_executor")
            self.assertEqual(payload["selected_task"]["id"], "T-020")
            self.assertIn("prompt", payload)
            self.assertIn("Start the active context pack.", payload["prompt"])


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
    (root / "agent" / "context-packs" / "T-020-harness-step-command.md").write_text(
        """# T-020: Harness Step Command

Type: `implementation`

## Requirements

- `R-007` CLI
- `R-127` Supervised run
- `R-129` Reviewer feedback

## Allowed Paths

- `agentspec/run.py`
- `agentspec/cli.py`
- `tests/test_supervised_run_step.py`
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
