import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import write_data
from agentspec.runner import package_run


class RunnerPackageTests(unittest.TestCase):
    def test_package_starts_next_task_and_returns_generic_execution_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            package = package_run(root, run_id="pkg-001", runner="generic")

            self.assertEqual(package["schema"], "agentspec.runner_package.v0")
            self.assertEqual(package["runner"], "generic")
            self.assertEqual(package["next_action"], "continue_executor")
            self.assertTrue(package["should_execute"])
            self.assertEqual(package["execution"]["argv"], [])
            self.assertIn("Start the active context pack.", package["execution"]["stdin"])
            self.assertEqual(package["execution"]["env"]["AGENTSPEC_RUN_ID"], "pkg-001")
            self.assertEqual(package["execution"]["env"]["AGENTSPEC_NEXT_ACTION"], "continue_executor")
            self.assertEqual(package["execution"]["env"]["AGENTSPEC_CONTEXT_PACK"], "agent/context-packs/T-021-runner-package-adapter.md")
            self.assertEqual(package["report_back"]["argv"][:5], ["aspec", "run", "step", "--run-id", "pkg-001"])
            self.assertEqual(package["report_back"]["touched_path_flag"], "--touched-path")

    def test_codex_package_uses_codex_command_hint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            package = package_run(root, run_id="pkg-001", runner="codex")

            self.assertEqual(package["runner"], "codex")
            self.assertEqual(package["execution"]["argv"], ["codex"])
            self.assertTrue(package["should_execute"])

    def test_completed_step_returns_no_execution_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            package_run(root, run_id="pkg-001", runner="generic")

            package = package_run(
                root,
                run_id="pkg-001",
                runner="generic",
                executor_output="Done. Acceptance criteria are met.",
                touched_paths=["agentspec/runner.py"],
                test_status="passed",
            )

            self.assertEqual(package["next_action"], "complete")
            self.assertFalse(package["should_execute"])
            self.assertIsNone(package["execution"]["stdin"])
            self.assertIsNone(package["step"]["prompt"])

    def test_unknown_runner_is_rejected_before_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            with self.assertRaisesRegex(ValueError, "Unknown runner"):
                package_run(root, run_id="pkg-001", runner="unknown")

            self.assertFalse((root / "agent" / "runs" / "pkg-001" / "state.yml").exists())

    def test_cli_package_json_outputs_runner_package(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "run", "package", "--runner", "claude", "--run-id", "pkg-cli", "--json"])

            self.assertEqual(code, 0)
            package = json.loads(output.getvalue())
            self.assertEqual(package["schema"], "agentspec.runner_package.v0")
            self.assertEqual(package["runner"], "claude")
            self.assertEqual(package["execution"]["argv"], ["claude"])
            self.assertTrue(package["should_execute"])


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
    (root / "agent" / "context-packs" / "T-021-runner-package-adapter.md").write_text(
        """# T-021: Runner Package Adapter

Type: `implementation`

## Requirements

- `R-007` CLI
- `R-127` Supervised run
- `R-129` Reviewer feedback

## Allowed Paths

- `agentspec/runner.py`
- `agentspec/cli.py`
- `tests/test_runner_package.py`
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
