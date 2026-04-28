import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.runner import RUNNER_EXEC_SCHEMA, RUNNER_RESULT_SCHEMA, execute_runner


class RunnerExecTests(unittest.TestCase):
    def test_execute_runner_runs_subprocess_and_updates_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            script = (
                "import os, sys\n"
                "from pathlib import Path\n"
                "prompt = sys.stdin.read()\n"
                "Path('work.txt').write_text(os.environ['AGENTSPEC_RUN_ID'] + '\\n' + str('Start the active context pack.' in prompt), encoding='utf-8')\n"
                "print('Done. Acceptance criteria are met.')\n"
            )
            result = execute_runner(
                root,
                run_id="exec-001",
                runner="generic",
                command=[sys.executable, "-c", script],
                test_status="passed",
            )

            self.assertEqual(result["schema"], RUNNER_EXEC_SCHEMA)
            self.assertEqual(result["run_id"], "exec-001")
            self.assertEqual(result["final_next_action"], "complete")
            self.assertFalse(result["final_should_execute"])
            self.assertEqual(
                [item["kind"] for item in result["transcript"]],
                ["package", "subprocess", "runner_result", "package"],
            )

            subprocess_event = result["transcript"][1]["execution"]
            self.assertEqual(subprocess_event["returncode"], 0)
            self.assertIn("work.txt", subprocess_event["touched_paths"])
            runner_result = result["transcript"][2]["result"]
            self.assertEqual(runner_result["schema"], RUNNER_RESULT_SCHEMA)
            self.assertIn("Done. Acceptance criteria are met.", runner_result["executor_output"])
            self.assertEqual(runner_result["test_status"], "passed")
            self.assertIn("work.txt", runner_result["touched_paths"])

            self.assertEqual((root / "work.txt").read_text(encoding="utf-8"), "exec-001\nTrue")
            ledger = load_data(root / "agent" / "task-ledger.yml")
            entry = ledger["tasks"]["agent/context-packs/T-024-local-subprocess-runner.md"]
            self.assertEqual(entry["status"], "complete")
            self.assertEqual(entry["verification"]["status"], "passed")

    def test_cli_run_exec_json_outputs_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            script = "from pathlib import Path; Path('work.txt').write_text('cli', encoding='utf-8'); print('Done.')"
            command_json = json.dumps([sys.executable, "-c", script])

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "exec",
                        "--run-id",
                        "exec-cli",
                        "--command-json",
                        command_json,
                        "--test-status",
                        "passed",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result["schema"], RUNNER_EXEC_SCHEMA)
            self.assertEqual(result["final_next_action"], "complete")
            self.assertEqual([item["kind"] for item in result["transcript"]], ["package", "subprocess", "runner_result", "package"])

    def test_execute_runner_reports_forbidden_path_halt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            script = (
                "from pathlib import Path\n"
                "Path('docs/source').mkdir(parents=True, exist_ok=True)\n"
                "Path('docs/source/sections.yml').write_text('changed', encoding='utf-8')\n"
                "print('Done. Acceptance criteria are met.')\n"
            )
            result = execute_runner(
                root,
                run_id="exec-policy",
                runner="generic",
                command=[sys.executable, "-c", script],
                test_status="passed",
            )

            self.assertEqual(result["final_next_action"], "stop")
            self.assertEqual(result["final_state"]["status"], "halted")
            review = result["final_package"]["step"]["review"]
            self.assertEqual(review["decision"], "halt")
            self.assertIn("forbidden_path", review["policy_flags"])

    def test_generic_runner_requires_explicit_command_before_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            with self.assertRaisesRegex(ValueError, "no default command"):
                execute_runner(root, run_id="exec-missing", runner="generic")

            self.assertFalse((root / "agent" / "runs" / "exec-missing" / "state.yml").exists())


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
    (root / "agent" / "context-packs" / "T-024-local-subprocess-runner.md").write_text(
        """# T-024: Local Subprocess Runner

Type: `implementation`

## Requirements

- `R-007` CLI
- `R-127` Supervised run
- `R-129` Reviewer feedback

## Allowed Paths

- `agent/context-packs/T-024-local-subprocess-runner.md`
- `agentspec/runner.py`
- `agentspec/cli.py`
- `tests/test_runner_exec.py`
- `work.txt`
- `agent/runs/**`
""",
        encoding="utf-8",
    )
    _git(root, "init")
    _git(root, "add", ".")
    _git(root, "-c", "user.email=test@example.com", "-c", "user.name=AgentSpec Test", "commit", "-m", "seed")


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
