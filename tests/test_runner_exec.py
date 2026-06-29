import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.runner import RUNNER_EXEC_SCHEMA, RUNNER_OUTPUT_INLINE_LIMIT, RUNNER_RESULT_SCHEMA, execute_runner


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

    def test_execute_runner_records_timeout_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            result = execute_runner(
                root,
                run_id="exec-timeout",
                runner="generic",
                command=[sys.executable, "-c", "import time; time.sleep(1)"],
                timeout_seconds=0.01,
            )

            self.assertEqual(result["run_id"], "exec-timeout")
            events = _events(root, "exec-timeout")
            self.assertEqual(events[1]["kind"], "runner_invocation_started")
            finished = next(event for event in events if event["kind"] == "runner_invocation_finished")
            self.assertTrue(finished["execution"]["timed_out"])
            self.assertEqual(finished["error"]["schema"], "agentspec.error.v1")
            self.assertEqual(finished["error"]["code"], "ASPEC_RUNNER_TIMEOUT")
            self.assertEqual(finished["error"]["layer"], "execution")
            self.assertTrue(finished["error"]["retryable"])
            self.assertEqual(finished["error"]["operation"], "run.exec")

    def test_execute_runner_records_heartbeat_events_during_long_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            with mock.patch("agentspec.runner.RUNNER_HEARTBEAT_INTERVAL_SECONDS", 0.01):
                execute_runner(
                    root,
                    run_id="exec-heartbeat",
                    runner="generic",
                    command=[
                        sys.executable,
                        "-c",
                        "import time; time.sleep(0.05); print('Done. Acceptance criteria are met.')",
                    ],
                    timeout_seconds=1,
                    test_status="passed",
                )

            heartbeats = [
                event
                for event in _events(root, "exec-heartbeat")
                if event["kind"] == "runner_invocation_heartbeat"
            ]
            self.assertGreaterEqual(len(heartbeats), 1)
            self.assertEqual(heartbeats[0]["runner"], "generic")
            self.assertGreater(heartbeats[0]["elapsed_seconds"], 0)
            self.assertEqual(
                heartbeats[0]["recovery_command"],
                "aspec run package --runner generic --run-id exec-heartbeat --json",
            )

    def test_execute_runner_records_start_failure_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            result = execute_runner(
                root,
                run_id="exec-start-failed",
                runner="generic",
                command=[str(root / "missing-runner-command")],
            )

            self.assertEqual(result["run_id"], "exec-start-failed")
            events = _events(root, "exec-start-failed")
            self.assertEqual(events[1]["kind"], "runner_invocation_started")
            finished = next(event for event in events if event["kind"] == "runner_invocation_finished")
            self.assertFalse(finished["execution"]["timed_out"])
            self.assertEqual(finished["error"]["schema"], "agentspec.error.v1")
            self.assertEqual(finished["error"]["code"], "ASPEC_RUNNER_START_FAILED")
            self.assertEqual(finished["error"]["layer"], "execution")
            self.assertFalse(finished["error"]["retryable"])
            self.assertEqual(finished["error"]["details"]["run_id"], "exec-start-failed")

    def test_execute_runner_redacts_credential_shaped_output_in_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            secret = "sk-proj-AbCdEf123456789012345678"
            script = f"print('leaked {secret}')"

            result = execute_runner(
                root,
                run_id="exec-secret",
                runner="generic",
                command=[sys.executable, "-c", script],
                test_status="failed",
            )

            payload = json.dumps(result)
            self.assertNotIn(secret, payload)
            self.assertIn("[REDACTED_CREDENTIAL]", payload)

    def test_execute_runner_externalizes_large_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            script = (
                "print('Done. Acceptance criteria are met.')\n"
                f"print('x' * {RUNNER_OUTPUT_INLINE_LIMIT + 256})\n"
            )

            result = execute_runner(
                root,
                run_id="exec-large-output",
                runner="generic",
                command=[sys.executable, "-c", script],
                test_status="passed",
            )

            execution = result["transcript"][1]["execution"]
            self.assertIn("output_artifacts", execution)
            stdout_artifact = execution["output_artifacts"]["stdout"]
            self.assertTrue(stdout_artifact["path"].endswith("runner-stdout.txt"))
            artifact_path = root / stdout_artifact["path"]
            self.assertTrue(artifact_path.exists())
            full_stdout = artifact_path.read_text(encoding="utf-8")
            self.assertGreater(len(full_stdout), RUNNER_OUTPUT_INLINE_LIMIT)
            self.assertLess(len(execution["stdout"]), len(full_stdout))
            self.assertIn("full redacted output written", execution["stdout"])

    def test_execute_runner_does_not_invoke_command_when_session_preflight_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, host_worktree=False)
            marker = root / "should-not-run.txt"
            script = f"from pathlib import Path; Path({str(marker)!r}).write_text('ran', encoding='utf-8')"

            result = execute_runner(
                root,
                run_id="exec-preflight",
                runner="generic",
                command=[sys.executable, "-c", script],
            )

            self.assertEqual(result["final_next_action"], "session_preflight_required")
            self.assertFalse(result["final_should_execute"])
            self.assertEqual([item["kind"] for item in result["transcript"]], ["package"])
            self.assertFalse(marker.exists())
            self.assertEqual(result["final_package"]["session_preflight"]["status"], "missing")

    def test_generic_runner_requires_explicit_command_before_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            with self.assertRaisesRegex(ValueError, "no default command"):
                execute_runner(root, run_id="exec-missing", runner="generic")

            self.assertFalse((root / "agent" / "runs" / "exec-missing" / "state.yml").exists())


def _seed(root: Path, *, host_worktree: bool = True) -> None:
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
    host_metadata = "\nHost Worktree Execution: `explicit`\n" if host_worktree else ""
    (root / "agent" / "context-packs" / "T-024-local-subprocess-runner.md").write_text(
        f"""# T-024: Local Subprocess Runner

Type: `implementation`
{host_metadata}

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


def _events(root: Path, run_id: str) -> list[dict]:
    events_path = root / "agent" / "runs" / run_id / "events.jsonl"
    return [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    unittest.main()
