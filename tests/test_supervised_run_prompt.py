import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.run import build_next_executor_prompt, resume_run, start_run


PACK = """# T-019: Prompt Handoff

Type: `implementation`

## Allowed Paths

- `agentspec/run.py`
- `agentspec/cli.py`
- `tests/test_supervised_run_prompt.py`
"""


class SupervisedRunPromptTests(unittest.TestCase):
    def test_prompt_for_started_run_points_to_active_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_run(root, Path("agent/context-packs/T-019-test.md"), run_id="run-001")

            handoff = build_next_executor_prompt(root, "run-001")

            self.assertEqual(handoff["status"], "started")
            self.assertEqual(handoff["context_pack"], "agent/context-packs/T-019-test.md")
            self.assertEqual(handoff["allowed_paths"], ["agentspec/run.py", "agentspec/cli.py", "tests/test_supervised_run_prompt.py"])
            self.assertIn("Start the active context pack.", handoff["prompt"])
            self.assertIn("agent/context-packs/T-019-test.md", handoff["prompt"])
            self.assertIn("`agentspec/run.py`", handoff["prompt"])
            self.assertEqual(handoff["session_preflight"]["status"], "missing")
            self.assertIn("Branch/session preflight", handoff["prompt"])

    def test_prompt_active_session_satisfies_branch_session_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--root",
                        str(root),
                        "session",
                        "start",
                        "--task",
                        "T-019",
                        "--owner",
                        "codex",
                        "--branch",
                        "feature/prompt-preflight",
                        "--worktree",
                        str(root),
                        "--session-id",
                        "S-prompt-preflight",
                        "--json",
                    ]
                )
            start_run(root, Path("agent/context-packs/T-019-test.md"), run_id="run-001")

            handoff = build_next_executor_prompt(root, "run-001")

            self.assertEqual(handoff["session_preflight"]["status"], "satisfied")
            self.assertEqual(handoff["session_preflight"]["active_session"]["session_id"], "S-prompt-preflight")
            self.assertIn("Active session lease: S-prompt-preflight", handoff["prompt"])

    def test_prompt_surfaces_explicit_host_worktree_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            host_pack = root / "agent" / "context-packs" / "T-020-host-worktree.md"
            host_pack.write_text(
                """# T-020: Host Worktree Prompt

Type: `implementation`
Host Worktree Execution: `explicit`

## Allowed Paths

- `agentspec/run.py`
""",
                encoding="utf-8",
            )
            start_run(root, Path("agent/context-packs/T-020-host-worktree.md"), run_id="run-host")

            handoff = build_next_executor_prompt(root, "run-host")

            self.assertEqual(handoff["session_preflight"]["status"], "satisfied")
            self.assertEqual(handoff["session_preflight"]["satisfied_by"], "explicit_host_worktree")
            self.assertIn("Explicit host-worktree execution", handoff["prompt"])

    def test_prompt_after_auto_continue_includes_reviewer_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--root",
                        str(root),
                        "session",
                        "start",
                        "--task",
                        "T-019",
                        "--owner",
                        "codex",
                        "--branch",
                        "feature/prompt-preflight",
                        "--worktree",
                        str(root),
                        "--session-id",
                        "S-prompt-resume",
                        "--json",
                    ]
                )
            start_run(root, Path("agent/context-packs/T-019-test.md"), run_id="run-001")
            resume_run(
                root,
                "run-001",
                executor_output="Want me to proceed with T-019, or pick one of the others?",
            )

            handoff = build_next_executor_prompt(root, "run-001")

            self.assertEqual(handoff["status"], "running")
            self.assertEqual(handoff["last_decision"], "auto_continue")
            self.assertIn("Continue with T-019", handoff["reviewer_message"])
            self.assertIn("Continue with T-019", handoff["prompt"])
            self.assertEqual(handoff["last_review"]["decision"], "auto_continue")

    def test_cli_prompt_json_outputs_handoff_payload(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(
                    main(["--root", str(root), "run", "start", "agent/context-packs/T-019-test.md", "--run-id", "run-001"]),
                    0,
                )

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "run", "prompt", "run-001", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["run_id"], "run-001")
            self.assertEqual(payload["status"], "started")
            self.assertIn("prompt", payload)
            self.assertIn("Start the active context pack.", payload["prompt"])

    def test_terminal_run_refuses_continuation_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--root",
                        str(root),
                        "session",
                        "start",
                        "--task",
                        "T-019",
                        "--owner",
                        "codex",
                        "--branch",
                        "feature/prompt-terminal",
                        "--worktree",
                        str(root),
                        "--session-id",
                        "S-prompt-terminal",
                        "--json",
                    ]
                )
            start_run(root, Path("agent/context-packs/T-019-test.md"), run_id="run-001")
            resume_run(
                root,
                "run-001",
                executor_output="Done. Acceptance criteria are met.",
                touched_paths=["agentspec/run.py"],
                test_status="passed",
            )

            with self.assertRaisesRegex(ValueError, "no continuation prompt"):
                build_next_executor_prompt(root, "run-001")


def _seed(root: Path) -> None:
    (root / ".agentspec").mkdir(parents=True)
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs").mkdir(parents=True)
    (root / "agent" / "context-packs" / "T-019-test.md").write_text(PACK, encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
