from __future__ import annotations

import io
import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agentspec.cli import CLI_ERROR_SCHEMA, main
from agentspec.io import load_data, write_data
from agentspec.run import abort_run, build_next_executor_prompt, inspect_run, resume_run, start_run
from agentspec.runner import package_run, submit_runner_result


PACK = """# T-057: Redirected Run State

Type: `implementation`

## Allowed Paths

- `agentspec/run.py`
- `agentspec/cli.py`
- `agentspec/runner.py`
- `tests/test_run_dir.py`
"""

PROMPT = "Want me to proceed with T-057, or pick one of the others?"


class RunDirTests(unittest.TestCase):
    def test_default_start_still_writes_under_agent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_pack(root)

            state = start_run(root, Path("agent/context-packs/T-057-test.md"), run_id="run-default")

            self.assertEqual(state["run_state_dir"], str((root / "agent" / "runs").resolve()))
            self.assertTrue((root / "agent" / "runs" / "run-default" / "state.yml").exists())
            self.assertTrue((root / "agent" / "runs" / "run-default" / "events.jsonl").exists())

    def test_start_with_run_dir_writes_redirected_state_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "target"
            run_dir = Path(td) / "run-state"
            _seed_pack(root)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "start",
                        "agent/context-packs/T-057-test.md",
                        "--run-id",
                        "run-redirected",
                        "--run-dir",
                        str(run_dir),
                    ]
                )

            self.assertEqual(code, 0)
            redirected_state = run_dir / "run-redirected" / "state.yml"
            self.assertTrue(redirected_state.exists())
            self.assertTrue((run_dir / "run-redirected" / "events.jsonl").exists())
            self.assertFalse((root / "agent" / "runs" / "run-redirected").exists())
            state = load_data(redirected_state)
            self.assertEqual(state["run_state_dir"], str(run_dir.resolve()))
            self.assertIn("Started run run-redirected", stdout.getvalue())

    def test_resume_prompt_inspect_and_abort_use_redirected_store(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "target"
            run_dir = Path(td) / "run-state"
            _seed_pack(root)

            start_run(
                root,
                Path("agent/context-packs/T-057-test.md"),
                run_id="run-shared",
                run_dir=run_dir,
            )
            handoff = build_next_executor_prompt(root, "run-shared", run_dir=run_dir)
            self.assertIn("Start the active context pack.", handoff["prompt"])

            result = resume_run(
                root,
                "run-shared",
                executor_output=PROMPT,
                run_dir=run_dir,
            )
            self.assertEqual(result["review"]["decision"], "auto_continue")
            self.assertEqual(inspect_run(root, "run-shared", run_dir=run_dir)["status"], "running")

            aborted = abort_run(root, "run-shared", run_dir=run_dir, reason="stop here")
            self.assertEqual(aborted["status"], "aborted")
            events = _events(run_dir / "run-shared" / "events.jsonl")
            self.assertEqual(events[-1]["kind"], "run_aborted")
            self.assertFalse((root / "agent" / "runs" / "run-shared").exists())

    def test_autonomous_research_loop_can_use_redirected_state_with_unwritable_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "target"
            run_dir = Path(td) / "run-state"
            _seed_empty_queue(root)
            os.chmod(root / "agent" / "runs", stat.S_IRUSR | stat.S_IXUSR)

            try:
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    code = main(
                        [
                            "--root",
                            str(root),
                            "run",
                            "loop",
                            "--mode",
                            "autonomous",
                            "--run-id",
                            "research-redirected",
                            "--run-dir",
                            str(run_dir),
                            "--json",
                        ]
                    )
                self.assertEqual(code, 0)
            finally:
                os.chmod(root / "agent" / "runs", stat.S_IRWXU)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["state"]["mode"], "research")
            self.assertTrue((run_dir / "research-redirected" / "state.yml").exists())
            self.assertFalse((root / "agent" / "runs" / "research-redirected").exists())
            self.assertEqual(
                payload["target_write_requirements"],
                [
                    "reports/dogfood/**",
                    "docs/discovery/open-questions.yml",
                    "docs/change-requests/**",
                ],
            )

    def test_human_readable_research_loop_reports_remaining_target_writes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "target"
            run_dir = Path(td) / "run-state"
            _seed_empty_queue(root)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "loop",
                        "--mode",
                        "autonomous",
                        "--run-id",
                        "research-human",
                        "--run-dir",
                        str(run_dir),
                    ]
                )

            self.assertEqual(code, 0)
            text = stdout.getvalue()
            self.assertIn("Research findings may still require target writes", text)
            self.assertIn("reports/dogfood/**", text)
            self.assertIn("docs/discovery/open-questions.yml", text)
            self.assertIn("docs/change-requests/**", text)

    def test_unwritable_explicit_run_dir_emits_json_error_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "target"
            readonly = Path(td) / "readonly"
            _seed_pack(root)
            readonly.mkdir()
            os.chmod(readonly, stat.S_IRUSR | stat.S_IXUSR)

            try:
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main(
                        [
                            "--root",
                            str(root),
                            "run",
                            "loop",
                            "agent/context-packs/T-057-test.md",
                            "--run-id",
                            "run-unwritable",
                            "--run-dir",
                            str(readonly),
                            "--json",
                        ]
                    )
                self.assertEqual(code, 1)
            finally:
                os.chmod(readonly, stat.S_IRWXU)

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema"], CLI_ERROR_SCHEMA)
            self.assertEqual(payload["error"]["type"], "PermissionError")
            self.assertFalse(payload["error"]["retryable"])
            self.assertIn(str(readonly), payload["error"]["message"])
            self.assertEqual(stderr.getvalue(), "")
            self.assertFalse((readonly / "run-unwritable" / "state.yml").exists())

    def test_runner_package_and_result_preserve_redirected_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "target"
            run_dir = Path(td) / "run-state"
            _seed_pack(root)

            package = package_run(
                root,
                Path("agent/context-packs/T-057-test.md"),
                runner="generic",
                run_id="run-runner",
                run_dir=run_dir,
            )

            self.assertIn("--run-dir", package["report_back"]["argv"])
            self.assertIn(str(run_dir.resolve()), package["report_back"]["argv"])
            self.assertIn("--run-dir", package["report_back"]["legacy_step_argv"])

            followup = submit_runner_result(
                root,
                "run-runner",
                {
                    "schema": "agentspec.runner_result.v0",
                    "executor_output": PROMPT,
                    "touched_paths": [],
                    "test_status": "not_run",
                },
                runner="generic",
                run_dir=run_dir,
            )

            self.assertEqual(followup["step"]["review"]["decision"], "auto_continue")
            events = _events(run_dir / "run-runner" / "events.jsonl")
            self.assertIn("reviewer_verdict", [event["kind"] for event in events])
            self.assertFalse((root / "agent" / "runs" / "run-runner").exists())


def _seed_pack(root: Path) -> None:
    _seed_base(root)
    (root / "agent" / "context-packs" / "T-057-test.md").write_text(PACK, encoding="utf-8")


def _seed_empty_queue(root: Path) -> None:
    _seed_base(root)


def _seed_base(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True, exist_ok=True)
    (root / "agent" / "runs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "traceability").mkdir(parents=True, exist_ok=True)
    write_data(root / "docs" / "traceability" / "requirements.yml", [])


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
