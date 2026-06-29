import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.errors import RunnerResultInvalidError
from agentspec.runner import RUNNER_EVIDENCE_SCHEMA, RUNNER_RESULT_SCHEMA, package_run, submit_runner_result
from agentspec.run import start_research_run, start_run


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
            self.assertEqual(package["execution"]["env"]["AGENTSPEC_CONTEXT_PACK"], "agent/context-packs/T-022-runner-result-ingestion.md")
            self.assertEqual(package["report_back"]["argv"][:4], ["aspec", "run", "result", "pkg-001"])
            self.assertEqual(package["report_back"]["result_schema"], RUNNER_RESULT_SCHEMA)
            self.assertEqual(package["report_back"]["result_template"]["schema"], RUNNER_RESULT_SCHEMA)
            self.assertEqual(package["report_back"]["result_template"]["evidence"]["schema"], RUNNER_EVIDENCE_SCHEMA)
            self.assertEqual(package["report_back"]["touched_path_flag"], "--touched-path")
            self.assertEqual(package["session_preflight"]["status"], "satisfied")
            self.assertEqual(package["session_preflight"]["satisfied_by"], "explicit_host_worktree")

    def test_package_blocks_executor_when_session_preflight_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, host_worktree=False)

            package = package_run(root, run_id="pkg-preflight", runner="generic")

            self.assertEqual(package["next_action"], "session_preflight_required")
            self.assertFalse(package["should_execute"])
            self.assertIsNone(package["execution"]["stdin"])
            self.assertEqual(package["execution"]["env"]["AGENTSPEC_NEXT_ACTION"], "session_preflight_required")
            self.assertEqual(package["session_preflight"]["status"], "missing")
            self.assertEqual(package["step"]["session_preflight"]["status"], "missing")
            self.assertIn("session start", package["session_preflight"]["recommended_command"])

    def test_active_session_satisfies_package_execution_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, host_worktree=False)
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--root",
                        str(root),
                        "session",
                        "start",
                        "--task",
                        "T-022",
                        "--owner",
                        "codex",
                        "--branch",
                        "feature/runner-preflight",
                        "--worktree",
                        str(root),
                        "--session-id",
                        "S-runner-preflight",
                        "--json",
                    ]
                )

            package = package_run(root, run_id="pkg-session-preflight", runner="generic")

            self.assertEqual(package["next_action"], "continue_executor")
            self.assertTrue(package["should_execute"])
            self.assertEqual(package["session_preflight"]["status"], "satisfied")
            self.assertEqual(package["session_preflight"]["satisfied_by"], "session_lease")
            self.assertEqual(package["session_preflight"]["active_session"]["session_id"], "S-runner-preflight")

    def test_package_includes_ui_evidence_template(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            package = package_run(root, run_id="pkg-001", runner="generic")

            evidence = package["report_back"]["result_template"]["evidence"]
            self.assertEqual(evidence["schema"], RUNNER_EVIDENCE_SCHEMA)
            self.assertEqual(
                set(evidence["artifact_kinds"]),
                {
                    "console_log",
                    "dom_snapshot",
                    "navigation_trace",
                    "network_log",
                    "screenshot",
                    "trace",
                    "video",
                    "other",
                },
            )
            self.assertIn("artifacts", evidence)
            self.assertIn("verification_commands", evidence)

    def test_codex_package_uses_codex_command_hint(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            package = package_run(root, run_id="pkg-001", runner="codex")

            self.assertEqual(package["runner"], "codex")
            self.assertEqual(package["execution"]["argv"], ["codex", "exec", "--json", "-"])
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

    def test_submit_runner_result_completes_run_and_returns_next_package(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            package_run(root, run_id="pkg-001", runner="generic")

            package = submit_runner_result(
                root,
                "pkg-001",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done. Acceptance criteria are met.",
                    "touched_paths": ["agentspec/runner.py"],
                    "test_status": "passed",
                },
                runner="generic",
            )

            self.assertEqual(package["next_action"], "complete")
            self.assertFalse(package["should_execute"])
            self.assertEqual(package["step"]["state"]["status"], "complete")
            self.assertEqual(package["step"]["review"]["decision"], "complete")

    def test_submit_runner_result_records_valid_evidence_event(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            package_run(root, run_id="pkg-001", runner="generic")
            evidence = {
                "schema": RUNNER_EVIDENCE_SCHEMA,
                "artifacts": [
                    {
                        "kind": "screenshot",
                        "path": "reports/ui/pkg-001/home.png",
                        "description": "Home page after the fix.",
                    },
                    {
                        "kind": "dom_snapshot",
                        "path": "reports/ui/pkg-001/home.dom.json",
                        "description": "DOM snapshot showing the visible submit button.",
                    },
                ],
                "verification_commands": [
                    {"command": "npm run test:e2e", "status": "passed"},
                ],
                "notes": "Browser validation evidence captured by the runner.",
            }

            submit_runner_result(
                root,
                "pkg-001",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done. Acceptance criteria are met.",
                    "touched_paths": ["agentspec/runner.py"],
                    "test_status": "passed",
                    "evidence": evidence,
                },
                runner="generic",
            )

            events = _events(root, "pkg-001")
            executor_event = next(event for event in events if event["kind"] == "executor_output")
            self.assertEqual(executor_event["evidence"], evidence)

    def test_submit_runner_result_uses_controller_observed_paths_when_git_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            (root / ".gitignore").write_text("agent/runs/\n", encoding="utf-8")
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "change-requests" / "README.md").write_text("seed\n", encoding="utf-8")
            _git(root, "init")
            _git(root, "add", ".")
            _git(root, "-c", "user.email=test@example.com", "-c", "user.name=AgentSpec Test", "commit", "-m", "seed")
            package_run(root, run_id="pkg-001", runner="generic")
            (root / "docs" / "source").mkdir(parents=True)
            (root / "docs" / "source" / "sections.yml").write_text("changed", encoding="utf-8")

            package = submit_runner_result(
                root,
                "pkg-001",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done. Acceptance criteria are met.",
                    "touched_paths": ["agentspec/runner.py"],
                    "test_status": "passed",
                },
                runner="generic",
            )

            self.assertEqual(package["next_action"], "stop")
            self.assertEqual(package["step"]["state"]["status"], "halted")
            review = package["step"]["review"]
            self.assertEqual(review["decision"], "halt")
            self.assertIn("forbidden_path", review["policy_flags"])
            events = _events(root, "pkg-001")
            executor_event = next(event for event in events if event["kind"] == "executor_output")
            self.assertEqual(executor_event["reported_touched_paths"], ["agentspec/runner.py"])
            self.assertEqual(executor_event["touched_paths_source"], "controller_observed")
            self.assertIn("docs/source/sections.yml", executor_event["touched_paths"])

    def test_submit_runner_result_ignores_preexisting_dirty_paths_for_supervised_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            (root / ".gitignore").write_text("agent/runs/\n", encoding="utf-8")
            (root / "agentspec").mkdir()
            (root / "agentspec" / "runner.py").write_text("seed\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_runner_package.py").write_text("seed\n", encoding="utf-8")
            _git(root, "init")
            _git(root, "add", ".")
            _git(root, "-c", "user.email=test@example.com", "-c", "user.name=AgentSpec Test", "commit", "-m", "seed")
            (root / "README.md").write_text("dirty before run\n", encoding="utf-8")
            (root / "scratch").mkdir()
            (root / "scratch" / "before.txt").write_text("untracked before run\n", encoding="utf-8")
            start_run(root, Path("agent/context-packs/T-022-runner-result-ingestion.md"), run_id="pkg-supervised-dirty")
            (root / "agentspec" / "runner.py").write_text("changed during run\n", encoding="utf-8")

            package = submit_runner_result(
                root,
                "pkg-supervised-dirty",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done. Acceptance criteria are met.",
                    "touched_paths": ["agentspec/runner.py"],
                    "test_status": "passed",
                },
                runner="generic",
            )

            self.assertEqual(package["next_action"], "complete")
            self.assertEqual(package["step"]["state"]["status"], "complete")
            events = _events(root, "pkg-supervised-dirty")
            executor_event = next(event for event in events if event["kind"] == "executor_output")
            self.assertEqual(executor_event["touched_paths"], ["agentspec/runner.py"])
            self.assertEqual(executor_event["reported_touched_paths"], ["agentspec/runner.py"])
            self.assertEqual(executor_event["touched_paths_source"], "controller_observed")
            self.assertNotIn("README.md", executor_event["touched_paths"])
            self.assertNotIn("scratch/before.txt", executor_event["touched_paths"])

    def test_submit_runner_result_ignores_unchanged_dirty_paths_from_run_start(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            (root / ".gitignore").write_text("agent/runs/\n", encoding="utf-8")
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "change-requests" / "README.md").write_text("seed\n", encoding="utf-8")
            _git(root, "init")
            _git(root, "add", ".")
            _git(root, "-c", "user.email=test@example.com", "-c", "user.name=AgentSpec Test", "commit", "-m", "seed")
            (root / "README.md").write_text("dirty before run\n", encoding="utf-8")
            start_research_run(root, run_id="pkg-research-dirty")
            (root / "docs" / "change-requests").mkdir(parents=True, exist_ok=True)
            research_path = root / "docs" / "change-requests" / "DCR-0099-research.md"
            research_path.write_text("# Research\n", encoding="utf-8")

            package = submit_runner_result(
                root,
                "pkg-research-dirty",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done.",
                    "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                    "test_status": "passed",
                    "acceptance_evidence": _valid_research_evidence(),
                },
                runner="generic",
            )

            self.assertEqual(package["next_action"], "complete")
            self.assertEqual(package["step"]["state"]["status"], "complete")
            events = _events(root, "pkg-research-dirty")
            executor_event = next(event for event in events if event["kind"] == "executor_output")
            self.assertEqual(executor_event["touched_paths"], ["docs/change-requests/DCR-0099-research.md"])
            self.assertEqual(executor_event["reported_touched_paths"], ["docs/change-requests/DCR-0099-research.md"])
            self.assertEqual(executor_event["touched_paths_source"], "controller_observed")

    def test_submit_runner_result_flags_dirty_path_changed_after_run_start(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            (root / ".gitignore").write_text("agent/runs/\n", encoding="utf-8")
            _git(root, "init")
            _git(root, "add", ".")
            _git(root, "-c", "user.email=test@example.com", "-c", "user.name=AgentSpec Test", "commit", "-m", "seed")
            (root / "README.md").write_text("dirty before run\n", encoding="utf-8")
            start_research_run(root, run_id="pkg-research-dirty-changed")
            (root / "README.md").write_text("changed during run\n", encoding="utf-8")
            (root / "docs" / "change-requests").mkdir(parents=True, exist_ok=True)
            research_path = root / "docs" / "change-requests" / "DCR-0099-research.md"
            research_path.write_text("# Research\n", encoding="utf-8")

            package = submit_runner_result(
                root,
                "pkg-research-dirty-changed",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done.",
                    "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                    "test_status": "passed",
                    "acceptance_evidence": _valid_research_evidence(),
                },
                runner="generic",
            )

            self.assertEqual(package["next_action"], "stop")
            self.assertEqual(package["step"]["state"]["status"], "halted")
            review = package["step"]["review"]
            self.assertEqual(review["decision"], "halt")
            self.assertIn("forbidden_path", review["policy_flags"])
            events = _events(root, "pkg-research-dirty-changed")
            executor_event = next(event for event in events if event["kind"] == "executor_output")
            self.assertIn("README.md", executor_event["touched_paths"])

    def test_submit_runner_result_flags_new_file_inside_dirty_untracked_dir_after_run_start(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            (root / ".gitignore").write_text("agent/runs/\n", encoding="utf-8")
            _git(root, "init")
            _git(root, "add", ".")
            _git(root, "-c", "user.email=test@example.com", "-c", "user.name=AgentSpec Test", "commit", "-m", "seed")
            (root / "scratch").mkdir()
            (root / "scratch" / "before.txt").write_text("dirty before run\n", encoding="utf-8")
            start_research_run(root, run_id="pkg-research-dirty-dir")
            (root / "scratch" / "during.txt").write_text("changed during run\n", encoding="utf-8")
            (root / "docs" / "change-requests").mkdir(parents=True, exist_ok=True)
            research_path = root / "docs" / "change-requests" / "DCR-0099-research.md"
            research_path.write_text("# Research\n", encoding="utf-8")

            package = submit_runner_result(
                root,
                "pkg-research-dirty-dir",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done.",
                    "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                    "test_status": "passed",
                    "acceptance_evidence": _valid_research_evidence(),
                },
                runner="generic",
            )

            self.assertEqual(package["next_action"], "stop")
            self.assertEqual(package["step"]["state"]["status"], "halted")
            review = package["step"]["review"]
            self.assertEqual(review["decision"], "halt")
            self.assertIn("forbidden_path", review["policy_flags"])
            events = _events(root, "pkg-research-dirty-dir")
            executor_event = next(event for event in events if event["kind"] == "executor_output")
            self.assertIn("scratch/during.txt", executor_event["touched_paths"])
            self.assertNotIn("scratch/before.txt", executor_event["touched_paths"])

    def test_invalid_runner_result_is_rejected_before_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            with self.assertRaisesRegex(ValueError, "executor_output"):
                submit_runner_result(
                    root,
                    "pkg-001",
                    {"schema": RUNNER_RESULT_SCHEMA, "touched_paths": ["agentspec/runner.py"]},
                    runner="generic",
                )

            self.assertFalse((root / "agent" / "runs" / "pkg-001" / "state.yml").exists())

    def test_invalid_runner_result_for_existing_run_records_rejection_event_without_state_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            package_run(root, run_id="pkg-001", runner="generic")
            state_path = root / "agent" / "runs" / "pkg-001" / "state.yml"
            before = load_data(state_path)

            with self.assertRaisesRegex(RunnerResultInvalidError, "executor_output"):
                submit_runner_result(
                    root,
                    "pkg-001",
                    {"schema": RUNNER_RESULT_SCHEMA, "touched_paths": ["agentspec/runner.py"]},
                    runner="generic",
                )

            self.assertEqual(load_data(state_path), before)
            events = _events(root, "pkg-001")
            rejected = events[-1]
            self.assertEqual(rejected["kind"], "runner_result_rejected")
            self.assertEqual(rejected["mutation"], "none")
            self.assertEqual(rejected["recovery_command"], "aspec run package --runner generic --run-id pkg-001 --json")
            self.assertEqual(rejected["error"]["schema"], "agentspec.error.v1")
            self.assertEqual(rejected["error"]["code"], "ASPEC_RUNNER_RESULT_INVALID")
            self.assertEqual(rejected["error"]["layer"], "execution")
            self.assertEqual(rejected["error"]["operation"], "run.result")
            self.assertEqual(rejected["error"]["details"]["run_id"], "pkg-001")
            self.assertEqual(rejected["error"]["details"]["mutation"], "none")

    def test_submit_runner_result_requires_existing_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            with self.assertRaisesRegex(FileNotFoundError, "Run not found"):
                submit_runner_result(
                    root,
                    "missing-run",
                    {
                        "schema": RUNNER_RESULT_SCHEMA,
                        "executor_output": "Done. Acceptance criteria are met.",
                        "touched_paths": ["agentspec/runner.py"],
                        "test_status": "passed",
                    },
                    runner="generic",
                )

            self.assertFalse((root / "agent" / "runs" / "missing-run" / "state.yml").exists())

    def test_invalid_evidence_is_rejected_before_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            package_run(root, run_id="pkg-001", runner="generic")
            state_path = root / "agent" / "runs" / "pkg-001" / "state.yml"
            before = load_data(state_path)

            with self.assertRaisesRegex(RunnerResultInvalidError, "evidence.artifacts"):
                submit_runner_result(
                    root,
                    "pkg-001",
                    {
                        "schema": RUNNER_RESULT_SCHEMA,
                        "executor_output": "Done. Acceptance criteria are met.",
                        "touched_paths": ["agentspec/runner.py"],
                        "test_status": "passed",
                        "evidence": {
                            "schema": RUNNER_EVIDENCE_SCHEMA,
                            "artifacts": [
                                {
                                    "kind": "unrecognized",
                                    "path": "reports/ui/pkg-001/home.png",
                                    "description": "Invalid kind.",
                                }
                            ],
                        },
                    },
                    runner="generic",
                )

            self.assertEqual(load_data(state_path), before)

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
            self.assertEqual(package["execution"]["argv"], ["claude", "-p", "--output-format", "stream-json", "--verbose"])
            self.assertTrue(package["should_execute"])

    def test_submit_runner_result_requires_session_preflight_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, host_worktree=False)
            package_run(root, run_id="pkg-preflight-result", runner="generic")
            state_path = root / "agent" / "runs" / "pkg-preflight-result" / "state.yml"
            before = load_data(state_path)

            with self.assertRaisesRegex(ValueError, "session preflight"):
                submit_runner_result(
                    root,
                    "pkg-preflight-result",
                    {
                        "schema": RUNNER_RESULT_SCHEMA,
                        "executor_output": "Done. Acceptance criteria are met.",
                        "touched_paths": ["agentspec/runner.py"],
                        "test_status": "passed",
                    },
                    runner="generic",
                )

            self.assertEqual(load_data(state_path), before)
            ledger_path = root / "agent" / "task-ledger.yml"
            ledger = load_data(ledger_path) if ledger_path.exists() else {}
            self.assertNotIn("agent/context-packs/T-022-runner-result-ingestion.md", ledger.get("tasks", {}))

    def test_cli_result_json_outputs_next_runner_package(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            package_run(root, run_id="pkg-cli", runner="generic")
            result = json.dumps(
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done. Acceptance criteria are met.",
                    "touched_paths": ["agentspec/runner.py"],
                    "test_status": "passed",
                }
            )

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "result",
                        "pkg-cli",
                        "--result-json",
                        result,
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            package = json.loads(output.getvalue())
            self.assertEqual(package["schema"], "agentspec.runner_package.v0")
            self.assertEqual(package["next_action"], "complete")
            self.assertFalse(package["should_execute"])

    def test_research_package_includes_acceptance_evidence_template(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_research_run(root, run_id="pkg-research")

            package = package_run(root, run_id="pkg-research", runner="generic")

            template = package["report_back"]["result_template"]
            evidence = template["acceptance_evidence"]
            self.assertEqual(evidence["schema"], "agentspec.research_acceptance_evidence.v0")
            self.assertIn("durable_artifacts", evidence)
            self.assertIn("allowed_path_confirmation", evidence)
            self.assertIn("verification_commands", evidence)
            self.assertIn("no_task_context_pack_reason", evidence)
            self.assertIn("created_task_context_pack", evidence)

    def test_passed_research_result_requires_acceptance_evidence_before_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_research_run(root, run_id="pkg-research")
            state_path = root / "agent" / "runs" / "pkg-research" / "state.yml"
            before = load_data(state_path)

            with self.assertRaisesRegex(RunnerResultInvalidError, "acceptance_evidence"):
                submit_runner_result(
                    root,
                    "pkg-research",
                    {
                        "schema": RUNNER_RESULT_SCHEMA,
                        "executor_output": "Done.",
                        "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                        "test_status": "passed",
                    },
                    runner="generic",
                )

            self.assertEqual(load_data(state_path), before)

    def test_cli_result_rejects_passed_research_result_without_acceptance_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_research_run(root, run_id="pkg-research")
            state_path = root / "agent" / "runs" / "pkg-research" / "state.yml"
            before = load_data(state_path)
            result = json.dumps(
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done.",
                    "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                    "test_status": "passed",
                }
            )

            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "result",
                        "pkg-research",
                        "--result-json",
                        result,
                        "--json",
                    ]
                )

            self.assertEqual(code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], "agentspec.cli_error.v0")
            self.assertEqual(payload["error"]["schema"], "agentspec.error.v1")
            self.assertEqual(payload["error"]["code"], "ASPEC_RUNNER_RESULT_INVALID")
            self.assertEqual(payload["error"]["operation"], "run.result")
            self.assertEqual(
                payload["error"]["recovery_command"],
                "aspec run package --runner generic --run-id pkg-research --json",
            )
            self.assertEqual(payload["error"]["details"]["mutation"], "none")
            self.assertIn("acceptance_evidence", payload["error"]["message"])
            self.assertEqual(load_data(state_path), before)

    def test_invalid_research_acceptance_evidence_is_rejected_before_state_changes(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_research_run(root, run_id="pkg-research")
            state_path = root / "agent" / "runs" / "pkg-research" / "state.yml"
            before = load_data(state_path)

            with self.assertRaisesRegex(RunnerResultInvalidError, "durable_artifacts"):
                submit_runner_result(
                    root,
                    "pkg-research",
                    {
                        "schema": RUNNER_RESULT_SCHEMA,
                        "executor_output": "Done.",
                        "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                        "test_status": "passed",
                        "acceptance_evidence": {
                            "schema": "agentspec.research_acceptance_evidence.v0",
                            "durable_artifacts": [],
                            "allowed_path_confirmation": True,
                            "verification_commands": [{"command": "git diff --check", "status": "passed"}],
                            "covered_requirements": ["R-142"],
                            "no_task_context_pack_reason": "Research-only proposal.",
                        },
                    },
                    runner="generic",
                )

            self.assertEqual(load_data(state_path), before)

    def test_research_result_accepts_artifacts_matching_active_run_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_research_run(root, run_id="pkg-research-tasking")
            state_path = root / "agent" / "runs" / "pkg-research-tasking" / "state.yml"
            state = load_data(state_path)
            state["allowed_paths"] = [
                *state["allowed_paths"],
                "docs/traceability/**",
                "agent/context-packs/**",
            ]
            state["target_write_requirements"] = list(state["allowed_paths"])
            write_data(state_path, state)
            evidence = _valid_research_evidence()
            evidence["durable_artifacts"] = [
                "docs/change-requests/DCR-0099-research.md",
                "docs/traceability/requirements.yml",
                "agent/context-packs/T-099-research-task.md",
            ]

            package = submit_runner_result(
                root,
                "pkg-research-tasking",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done.",
                    "touched_paths": list(evidence["durable_artifacts"]),
                    "test_status": "passed",
                    "acceptance_evidence": evidence,
                    "reviewer_mode": "deterministic",
                },
                runner="generic",
            )

            self.assertEqual(package["next_action"], "complete")
            executor_event = next(
                event for event in _events(root, "pkg-research-tasking") if event["kind"] == "executor_output"
            )
            self.assertEqual(executor_event["acceptance_evidence"]["durable_artifacts"], evidence["durable_artifacts"])

    def test_research_result_accepts_created_task_context_pack_without_prior_tasking_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_research_run(root, run_id="pkg-research-created-task")
            evidence = _valid_research_evidence()
            evidence.pop("no_task_context_pack_reason")
            evidence["durable_artifacts"] = [
                "docs/change-requests/DCR-0099-research.md",
                "docs/traceability/requirements.yml",
                "agent/context-packs/T-099-research-task.md",
            ]
            evidence["created_task_context_pack"] = "agent/context-packs/T-099-research-task.md"

            package = submit_runner_result(
                root,
                "pkg-research-created-task",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done.",
                    "touched_paths": list(evidence["durable_artifacts"]),
                    "test_status": "passed",
                    "acceptance_evidence": evidence,
                    "reviewer_mode": "deterministic",
                },
                runner="generic",
            )

            self.assertEqual(package["next_action"], "complete")
            executor_event = next(
                event for event in _events(root, "pkg-research-created-task") if event["kind"] == "executor_output"
            )
            self.assertEqual(
                executor_event["acceptance_evidence"]["created_task_context_pack"],
                "agent/context-packs/T-099-research-task.md",
            )

    def test_research_result_rejection_names_artifacts_outside_active_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_research_run(root, run_id="pkg-research-disallowed")
            evidence = _valid_research_evidence()
            evidence["durable_artifacts"] = ["docs/spec/disallowed.md"]

            with self.assertRaisesRegex(RunnerResultInvalidError, "docs/spec/disallowed.md"):
                submit_runner_result(
                    root,
                    "pkg-research-disallowed",
                    {
                        "schema": RUNNER_RESULT_SCHEMA,
                        "executor_output": "Done.",
                        "touched_paths": ["docs/spec/disallowed.md"],
                        "test_status": "passed",
                        "acceptance_evidence": evidence,
                    },
                    runner="generic",
                )

    def test_runner_result_recovers_halted_research_run_with_acceptance_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_research_run(root, run_id="pkg-research-recover")

            halted = submit_runner_result(
                root,
                "pkg-research-recover",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done.",
                    "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                    "test_status": "passed",
                    "acceptance_evidence": _valid_research_evidence(),
                    "reviewer_mode": "model",
                },
                runner="generic",
            )
            self.assertEqual(halted["step"]["state"]["status"], "halted")

            recovered = submit_runner_result(
                root,
                "pkg-research-recover",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done. Acceptance criteria are covered by the DCR and verification passed.",
                    "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                    "test_status": "passed",
                    "acceptance_evidence": _valid_research_evidence(),
                    "reviewer_mode": "deterministic",
                },
                runner="generic",
            )

            self.assertEqual(recovered["next_action"], "complete")
            self.assertEqual(recovered["step"]["state"]["status"], "complete")
            self.assertTrue(any(event["kind"] == "halted_run_reopened" for event in _events(root, "pkg-research-recover")))


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
    (root / "agent" / "context-packs" / "T-022-runner-result-ingestion.md").write_text(
        f"""# T-022: Runner Result Ingestion

Type: `implementation`
{host_metadata}

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


def _events(root: Path, run_id: str) -> list[dict]:
    events_path = root / "agent" / "runs" / run_id / "events.jsonl"
    return [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _valid_research_evidence() -> dict:
    return {
        "schema": "agentspec.research_acceptance_evidence.v0",
        "durable_artifacts": ["docs/change-requests/DCR-0099-research.md"],
        "allowed_path_confirmation": True,
        "verification_commands": [{"command": "git diff --check", "status": "passed"}],
        "covered_requirements": ["R-172"],
        "covered_questions": [],
        "source_checks": [],
        "no_task_context_pack_reason": "Research mode intentionally produced proposal artifacts only.",
    }


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, text=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
