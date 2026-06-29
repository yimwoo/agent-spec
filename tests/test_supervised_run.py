import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data
from agentspec.run import abort_run, inspect_run, resume_run, start_run


PACK = """# T-008: DCR Accept Cascade Fix

Type: `implementation`
Host Worktree Execution: `explicit`

## Goal

Fix DCR acceptance behavior.

## Allowed Paths

- `agentspec/dcr.py`
- `agentspec/cli.py`
- `tests/test_dcr_cli.py`
"""


OTHER_PACK = """# T-011: Other Task

Type: `implementation`
Host Worktree Execution: `explicit`

## Allowed Paths

- `agentspec/config.py`
"""


class SupervisedRunTests(unittest.TestCase):
    def test_start_creates_state_and_events_with_configured_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, PACK)

            state = start_run(root, Path("agent/context-packs/T-008-test.md"), run_id="run-001")

            self.assertEqual(state["run_id"], "run-001")
            self.assertEqual(state["status"], "started")
            self.assertEqual(state["profiles"]["executor"]["adapter"], "current-host")
            self.assertEqual(state["profiles"]["executor"]["model"], "host-default")
            self.assertEqual(state["profiles"]["continuation_reviewer"]["model"], "oca/gpt-5.4-mini")
            self.assertEqual(state["allowed_paths"], ["agentspec/dcr.py", "agentspec/cli.py", "tests/test_dcr_cli.py"])

            state_path = root / "agent" / "runs" / "run-001" / "state.yml"
            events_path = root / "agent" / "runs" / "run-001" / "events.jsonl"
            summary_path = root / "agent" / "runs" / "run-001" / "summary.yml"
            self.assertTrue(state_path.exists())
            self.assertTrue(events_path.exists())
            self.assertFalse(summary_path.exists())
            self.assertEqual(_events(events_path)[0]["kind"], "run_started")

    def test_resume_auto_continues_for_active_context_pack_choice(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, PACK)
            start_run(root, Path("agent/context-packs/T-008-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="Want me to proceed with T-008, or pick one of the others?",
            )

            review = result["review"]
            self.assertEqual(review["decision"], "auto_continue")
            self.assertIn("Continue with T-008", review["message_to_executor"])

            state = load_data(root / "agent" / "runs" / "run-001" / "state.yml")
            self.assertEqual(state["status"], "running")
            self.assertEqual(state["last_decision"], "auto_continue")

            events = _events(root / "agent" / "runs" / "run-001" / "events.jsonl")
            self.assertEqual([event["kind"] for event in events], ["run_started", "executor_output", "reviewer_verdict", "controller_response"])

    def test_resume_pauses_when_task_choice_does_not_match_active_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, OTHER_PACK, pack_name="T-011-test.md")
            start_run(root, Path("agent/context-packs/T-011-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="Want me to proceed with T-008, or pick one of the others?",
            )

            self.assertEqual(result["review"]["decision"], "pause_for_human")
            self.assertTrue(result["review"]["requires_human"])
            self.assertEqual(result["state"]["status"], "paused")

    def test_resume_halts_when_touched_path_is_outside_allowed_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, PACK)
            start_run(root, Path("agent/context-packs/T-008-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="I edited the files.",
                touched_paths=["docs/source/sections.yml"],
            )

            self.assertEqual(result["review"]["decision"], "halt")
            self.assertIn("forbidden_path", result["review"]["policy_flags"])
            self.assertEqual(result["state"]["status"], "halted")

    def test_resume_halts_when_max_iterations_is_exceeded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, PACK)
            start_run(root, Path("agent/context-packs/T-008-test.md"), run_id="run-001", max_iterations=1)

            first = resume_run(
                root,
                "run-001",
                executor_output="Want me to proceed with T-008, or pick one of the others?",
            )
            self.assertEqual(first["review"]["decision"], "auto_continue")

            second = resume_run(
                root,
                "run-001",
                executor_output="Want me to proceed with T-008, or pick one of the others?",
            )
            self.assertEqual(second["review"]["decision"], "halt")
            self.assertIn("max_iterations_exceeded", second["review"]["policy_flags"])
            self.assertEqual(second["state"]["status"], "halted")

    def test_resume_can_complete_paused_run_after_iteration_cap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, PACK)
            start_run(root, Path("agent/context-packs/T-008-test.md"), run_id="run-001", max_iterations=1)

            first = resume_run(
                root,
                "run-001",
                executor_output="Implemented the scoped change. Verification passed.",
                touched_paths=["agentspec/dcr.py"],
                test_status="passed",
            )
            self.assertEqual(first["review"]["decision"], "pause_for_human")
            self.assertEqual(first["state"]["status"], "paused")

            second = resume_run(
                root,
                "run-001",
                executor_output="T-008 complete. Acceptance criteria satisfied. Verification passed.",
                touched_paths=["agentspec/dcr.py"],
                test_status="passed",
            )
            self.assertEqual(second["review"]["decision"], "complete")
            self.assertNotIn("max_iterations_exceeded", second["review"]["policy_flags"])
            self.assertEqual(second["state"]["status"], "complete")

    def test_resume_completes_when_executor_reports_done_and_tests_pass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, PACK)
            start_run(root, Path("agent/context-packs/T-008-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="Done. Acceptance criteria are met.",
                touched_paths=["agentspec/dcr.py"],
                test_status="passed",
            )

            self.assertEqual(result["review"]["decision"], "complete")
            self.assertEqual(result["state"]["status"], "complete")
            self.assertEqual(result["state"]["profiles"]["quality_reviewer"]["model"], "oca/gpt-5.5")

    def test_inspect_and_abort_report_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, PACK)
            start_run(root, Path("agent/context-packs/T-008-test.md"), run_id="run-001")

            info = inspect_run(root, "run-001")
            self.assertEqual(info["status"], "started")

            aborted = abort_run(root, "run-001", reason="test abort")
            self.assertEqual(aborted["status"], "aborted")
            self.assertEqual(inspect_run(root, "run-001")["status"], "aborted")

            events = _events(root / "agent" / "runs" / "run-001" / "events.jsonl")
            self.assertEqual(events[-1]["kind"], "run_aborted")

    def test_cli_run_start_resume_inspect_abort(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, PACK)

            self.assertEqual(
                main(["--root", str(root), "run", "start", "agent/context-packs/T-008-test.md", "--run-id", "run-001"]),
                0,
            )

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "resume",
                        "run-001",
                        "--executor-output",
                        "Want me to proceed with T-008, or pick one of the others?",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertIn("auto_continue", output.getvalue())
            self.assertIn("Continue with T-008", output.getvalue())

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "run", "inspect", "run-001"])
            self.assertEqual(code, 0)
            self.assertIn('"status": "running"', output.getvalue())

            self.assertEqual(main(["--root", str(root), "run", "abort", "run-001"]), 0)


def _seed(root: Path, pack_text: str, pack_name: str = "T-008-test.md") -> None:
    (root / ".agentspec").mkdir(parents=True)
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs").mkdir(parents=True)
    (root / ".agentspec" / "config.yml").write_text(
        json.dumps(
            {
                "version": 1,
                "agent_profiles": {
                    "main_executor": {"adapter": "current-host", "model": "host-default"},
                    "continuation_reviewer": {
                        "adapter": "codex",
                        "credential_source": "codex-auth",
                        "config_source": "codex-config",
                        "model": "oca/gpt-5.4-mini",
                        "reasoning": "low",
                    },
                    "quality_reviewer": {
                        "adapter": "codex",
                        "credential_source": "codex-auth",
                        "config_source": "codex-config",
                        "model": "oca/gpt-5.5",
                        "reasoning": "high",
                    },
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
    (root / "agent" / "context-packs" / pack_name).write_text(pack_text, encoding="utf-8")


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
