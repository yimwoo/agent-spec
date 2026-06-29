import io
import json
import shutil
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.run import abort_run
from agentspec.status import PROJECT_STATUS_SCHEMA, build_lifecycle_summary, build_project_status, format_project_status


class StatusCLITests(unittest.TestCase):
    def test_build_project_status_summarizes_queue_runs_and_dcrs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            status = build_project_status(root, recent_limit=2)

            self.assertEqual(status["schema"], PROJECT_STATUS_SCHEMA)
            self.assertEqual(status["overall"], "attention_needed")
            self.assertEqual(status["readiness"]["score"], 88)
            self.assertEqual(status["requirements"]["by_status"], {"accepted": 1, "proposed-pending-acceptance": 1})
            self.assertEqual(status["dcrs"]["by_status"], {"accepted": 1})
            self.assertEqual(status["tasks"]["by_status"], {"complete": 1, "halted": 1, "ready": 1})
            self.assertEqual(status["tasks"]["next"]["id"], "T-003")
            self.assertEqual(status["runs"]["by_status"], {"complete": 1, "halted": 1, "running": 1})
            self.assertEqual(status["runs"]["attention"][0]["run_id"], "run-halted")
            self.assertEqual(status["runs"]["active"][0]["run_id"], "run-active")
            self.assertEqual(len(status["runs"]["recent"]), 2)
            self.assertIn("run inspect run-halted", status["recommendation"])

            halted = status["runs"]["attention"][0]
            self.assertEqual(halted["last_review_reason"], "Touched forbidden path.")
            self.assertEqual(halted["policy_flags"], ["forbidden_path"])
            self.assertEqual(halted["test_status"], "failed")
            self.assertEqual(halted["last_event_ref"], "agent/runs/run-halted/events.jsonl:2")
            self.assertEqual(halted["recovery_command"], "aspec run inspect run-halted")

            active = status["runs"]["active"][0]
            self.assertEqual(active["last_review_reason"], "Continue scoped work.")
            self.assertEqual(active["test_status"], "passed")
            self.assertEqual(active["recovery_command"], "aspec run prompt run-active")

    def test_cli_status_json_outputs_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "status", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], PROJECT_STATUS_SCHEMA)
            self.assertEqual(payload["overall"], "attention_needed")

    def test_status_json_includes_active_agent_profile_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            (root / ".agentspec").mkdir()
            write_data(
                root / ".agentspec" / "config.yml",
                {
                    "version": 1,
                    "agent_profiles": {
                        "main_executor": {"adapter": "current-host", "model": "host-default"},
                        "continuation_reviewer": {
                            "adapter": "codex",
                            "credential_source": "codex-auth",
                            "config_source": "codex-config",
                            "model": None,
                        },
                        "test_eval_reviewer": {
                            "adapter": "codex",
                            "credential_source": "codex-auth",
                            "config_source": "codex-config",
                            "model": "oca/gpt5.3-codex",
                        },
                    },
                    "supervised_runs": {
                        "executor_profile": "main_executor",
                        "continuation_reviewer_profile": "continuation_reviewer",
                        "quality_reviewer_profile": "test_eval_reviewer",
                    },
                },
            )

            status = build_project_status(root)

            profiles = status["agent_profiles"]
            self.assertEqual(profiles["bindings"]["executor"], "main_executor")
            self.assertEqual(profiles["bindings"]["continuation_reviewer"], "continuation_reviewer")
            self.assertEqual(profiles["bindings"]["quality_reviewer"], "test_eval_reviewer")
            self.assertEqual(profiles["profiles"]["test_eval_reviewer"]["configured_model"], "oca/gpt5.3-codex")
            self.assertEqual(profiles["profiles"]["test_eval_reviewer"]["model_source"], "profile")

            text = format_project_status(status)
            self.assertIn("Agent Profiles:", text)

    def test_human_status_mentions_next_and_attention_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            text = format_project_status(build_project_status(root))

            self.assertIn("AgentSpec Status", text)
            self.assertIn("Main point:", text)
            self.assertIn("Lifecycle state:", text)
            self.assertIn("Recommended next action:", text)
            self.assertIn("Overall: attention_needed", text)
            self.assertIn("Next: T-003", text)
            self.assertIn("Attention Runs:", text)
            self.assertIn("run-halted", text)

    def test_status_lifecycle_summary_explains_no_ready_task(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 45, "mode": "discovery+spike", "summary": "Readiness is 45/100."},
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [])

            status = build_project_status(root)

            summary = status["lifecycle_summary"]
            self.assertEqual(summary["schema"], "agentspec.lifecycle_summary.v0")
            self.assertEqual(summary["current_stage"], "source_or_requirements_needed")
            self.assertIn("No implementation task is ready", summary["main_point"])
            self.assertTrue(summary["recommended_next_action"]["human_decision_required"])
            self.assertIn("aspec status --json", summary["recommended_next_action"]["commands"])
            agent_display = summary["recommended_next_action"]["agent_display"]
            self.assertFalse(agent_display["show_terminal_commands"])
            self.assertNotIn("aspec", json.dumps(agent_display).lower())
            self.assertIn("SRC-*", summary["terms"])
            self.assertEqual(summary["readiness"]["implementation_gate"], 60)

            text = format_project_status(status)
            self.assertIn("Implementation gate: readiness 45/100 is below 60/100", text)
            self.assertIn("Mode: discovery+spike", text)

    def test_status_no_ready_task_gives_concrete_human_options(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {
                        "id": "R-209",
                        "status": "accepted",
                        "priority": "P1",
                        "title": "AgentSpec explains lifecycle summaries and next actions",
                    }
                ],
            )
            (root / "agent" / "context-packs" / "T-001-complete.md").write_text(
                "# T-001: Complete\n\nType: `implementation`\n",
                encoding="utf-8",
            )
            (root / "agent" / "reviews").mkdir()
            write_data(
                root / "agent" / "reviews" / "REVIEW-0001.yml",
                {
                    "schema": "agentspec.code_review.v0",
                    "id": "REVIEW-0001",
                    "task": {
                        "selector": "T-001",
                        "context_pack": "agent/context-packs/T-001-complete.md",
                    },
                    "verdict": "ready",
                },
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-complete.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "updated_at": "2026-05-01T00:00:00Z",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001"},
                        }
                    },
                },
            )
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-01T00:00:00Z",
                    "last_completed_task": {
                        "id": "T-001",
                        "context_pack": "agent/context-packs/T-001-complete.md",
                        "run_id": "run-001",
                    },
                    "code_review": {"id": "REVIEW-0001"},
                    "current_state": {
                        "requirements": {"total": 1},
                        "dcrs": {"total": 0},
                        "tasks": {"total": 1},
                    },
                    "next_action": {"kind": "idle", "command": "aspec status --json"},
                },
            )

            status = build_project_status(root)
            action = status["lifecycle_summary"]["recommended_next_action"]

            self.assertEqual(status["lifecycle_summary"]["current_stage"], "idle_no_ready_task")
            self.assertTrue(action["options"])
            self.assertIn("R-209", action["commands"][0])
            self.assertNotIn("<title>", "\n".join(action["commands"]))
            self.assertFalse(action["agent_display"]["show_terminal_commands"])
            self.assertIn("Create a follow-up task for R-209", json.dumps(action["agent_display"]))
            self.assertNotIn("aspec", json.dumps(action["agent_display"]).lower())

            text = format_project_status(status)
            self.assertIn("Terminal next commands:", text)
            self.assertIn("Next options:", text)
            self.assertIn("Create a follow-up task for R-209", text)
            self.assertIn('aspec task create --requirement R-209 --type implementation', text)
            self.assertNotIn("<title>", text)

    def test_status_no_ready_task_does_not_recommend_duplicate_covered_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "agent" / "reviews").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {
                        "id": "R-209",
                        "status": "accepted",
                        "priority": "P1",
                        "title": "AgentSpec explains lifecycle summaries and next actions",
                    }
                ],
            )
            (root / "agent" / "context-packs" / "T-001-complete.md").write_text(
                """# T-001: Complete

Type: `implementation`

## Requirements

- `R-209` AgentSpec explains lifecycle summaries and next actions
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "reviews" / "REVIEW-0001.yml",
                {
                    "schema": "agentspec.code_review.v0",
                    "id": "REVIEW-0001",
                    "task": {
                        "selector": "T-001",
                        "context_pack": "agent/context-packs/T-001-complete.md",
                    },
                    "verdict": "ready",
                },
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-complete.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "updated_at": "2026-05-01T00:00:00Z",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001"},
                        }
                    },
                },
            )
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-01T00:00:00Z",
                    "last_completed_task": {
                        "id": "T-001",
                        "context_pack": "agent/context-packs/T-001-complete.md",
                        "run_id": "run-001",
                    },
                    "current_state": {
                        "requirements": {"total": 1},
                        "dcrs": {"total": 0},
                        "tasks": {"total": 1},
                    },
                    "next_action": {"kind": "idle", "command": "aspec status --json"},
                },
            )

            status = build_project_status(root)
            action = status["lifecycle_summary"]["recommended_next_action"]
            commands = "\n".join(action["commands"])

            self.assertEqual(status["requirements"]["uncovered_accepted_examples"], [])
            self.assertEqual(status["lifecycle_summary"]["current_stage"], "idle_no_ready_task")
            self.assertIn("already represented by task context packs", action["reason"])
            self.assertNotIn("aspec task create --requirement R-209", commands)
            self.assertNotIn("Create a follow-up task for R-209", json.dumps(action["agent_display"]))

            text = format_project_status(status)
            self.assertNotIn("aspec task create --requirement R-209", text)

    def test_status_no_ready_task_excludes_dcrs_with_task_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "agent" / "reviews").mkdir(parents=True)
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {"id": "R-201", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0001"},
                    {"id": "R-202", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0002"},
                    {"id": "R-203", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0003"},
                ],
            )
            _write_dcr(root, "DCR-0001", status="accepted")
            _write_dcr(root, "DCR-0002", status="classified")
            _write_dcr(root, "DCR-0003", status="accepted")
            (root / "agent" / "context-packs" / "T-001-complete-first-dcr.md").write_text(
                """# T-001: Complete first DCR

Type: `implementation`
Originating DCR: `DCR-0001`

## Requirements

- `R-201` Complete
""",
                encoding="utf-8",
            )
            (root / "agent" / "context-packs" / "T-002-complete-second-dcr.md").write_text(
                """# T-002: Complete second DCR

Type: `implementation`
Originating DCR: `DCR-0002`

## Requirements

- `R-202` Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "reviews" / "REVIEW-0001.yml",
                {
                    "schema": "agentspec.code_review.v0",
                    "id": "REVIEW-0001",
                    "task": {"context_pack": "agent/context-packs/T-001-complete-first-dcr.md"},
                    "verdict": "ready",
                },
            )
            write_data(
                root / "agent" / "reviews" / "REVIEW-0002.yml",
                {
                    "schema": "agentspec.code_review.v0",
                    "id": "REVIEW-0002",
                    "task": {"context_pack": "agent/context-packs/T-002-complete-second-dcr.md"},
                    "verdict": "ready",
                },
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-complete-first-dcr.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001"},
                        },
                        "agent/context-packs/T-002-complete-second-dcr.md": {
                            "status": "complete",
                            "run_id": "run-002",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0002"},
                        },
                    },
                },
            )

            status = build_project_status(root)
            blocker = status["lifecycle_summary"]["blocked_by"][0]

            self.assertEqual(status["dcrs"]["by_status"], {"accepted": 2, "classified": 1})
            self.assertEqual(status["dcrs"]["covered_by_task"], 2)
            self.assertEqual(status["dcrs"]["ready_for_tasking"], 1)
            self.assertEqual(
                status["dcrs"]["ready_for_tasking_items"],
                [
                    {
                        "id": "DCR-0003",
                        "path": str((root / "docs" / "change-requests" / "DCR-0003-test.md").resolve()),
                        "status": "accepted",
                        "classification": "implement-now",
                        "reason": (
                            "DCR is implementation-ready and is not covered by any "
                            "task context pack."
                        ),
                    }
                ],
            )
            self.assertEqual(blocker["dcrs_covered_by_task"], 2)
            self.assertEqual(blocker["dcrs_ready_for_tasking"], 1)
            self.assertEqual(
                blocker["dcrs_ready_for_tasking_items"],
                status["dcrs"]["ready_for_tasking_items"],
            )
            self.assertIn("ready_for_tasking=DCR-0003", format_project_status(status))

    def test_status_ignores_untracked_gitignored_agent_artifact_residue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text(
                "\n".join(
                    [
                        "/docs/change-requests/",
                        "/agent/context-packs/",
                        "/agent/runs/",
                        "/agent/task-ledger.yml",
                        "/agent/handoff.yml",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "agent" / "runs" / "local-residue").mkdir(parents=True)
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [{"id": "R-201", "status": "accepted", "priority": "P1"}],
            )
            tracked_pack = root / "agent" / "context-packs" / "T-001-tracked.md"
            tracked_pack.write_text(
                """# T-001: Tracked

Type: `implementation`

## Requirements

- `R-201` Tracked source
""",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "-f", "agent/context-packs/T-001-tracked.md"], cwd=root, check=True)
            _write_dcr(root, "DCR-9999", status="accepted")
            (root / "agent" / "context-packs" / "T-999-ignored.md").write_text(
                "# T-999: Ignored residue\n\nType: `implementation`\n",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "runs" / "local-residue" / "state.yml",
                {
                    "run_id": "local-residue",
                    "status": "halted",
                    "mode": "supervised",
                    "context_pack": "agent/context-packs/T-999-ignored.md",
                    "updated_at": "2026-05-18T00:00:00Z",
                },
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-999-ignored.md": {
                            "status": "complete",
                            "run_id": "local-residue",
                        }
                    },
                },
            )
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "current_state": {"dcrs": {"total": 64}, "tasks": {"total": 43}},
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["dcrs"]["total"], 0)
            self.assertEqual(status["tasks"]["total"], 1)
            self.assertEqual(status["tasks"]["ready"][0]["id"], "T-001")
            self.assertEqual(status["runs"]["total"], 0)
            self.assertNotIn("handoff", status)
            self.assertFalse(
                any(
                    warning.get("context_pack") == "agent/context-packs/T-999-ignored.md"
                    for warning in status["lifecycle"]["warnings"]
                )
            )

    def test_status_ignores_tracked_ledger_entries_for_ignored_missing_context_packs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("/agent/\n", encoding="utf-8")
            (root / "agent").mkdir()
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-999-ignored.md": {
                            "status": "complete",
                            "verification": {"status": "passed"},
                            "code_review": {
                                "id": "REVIEW-9999",
                                "path": "agent/reviews/REVIEW-9999.yml",
                            },
                        }
                    },
                },
            )
            subprocess.run(["git", "add", "-f", "agent/task-ledger.yml"], cwd=root, check=True)

            status = build_project_status(root)

            self.assertFalse(
                any(
                    warning.get("context_pack") == "agent/context-packs/T-999-ignored.md"
                    for warning in status["lifecycle"]["warnings"]
                )
            )

    def test_status_counts_completed_tracked_ledger_requirement_from_ignored_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("/agent/\n", encoding="utf-8")
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {
                    "score": 100,
                    "mode": "normal-implementation",
                    "summary": "DCR-0001 is accepted, implementation-ready, and taskable.",
                },
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {
                        "id": "R-201",
                        "status": "accepted",
                        "priority": "P1",
                        "originating_dcr": "DCR-0001",
                    },
                ],
            )
            _write_dcr(root, "DCR-0001", status="accepted")
            (root / "agent" / "context-packs" / "T-001-force-add-pending.md").write_text(
                """# T-001: Force Add Pending

Type: `implementation`
Originating DCR: `DCR-0001`

## Requirements

- `R-201` Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-force-add-pending.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "verification": {"status": "passed"},
                        },
                    },
                },
            )
            subprocess.run(["git", "add", "-f", "agent/task-ledger.yml"], cwd=root, check=True)

            status = build_project_status(root)

            self.assertEqual(status["tasks"]["total"], 1)
            self.assertEqual(status["tasks"]["by_status"], {"complete": 1})
            self.assertEqual(status["requirements"]["uncovered_accepted_examples"], [])
            self.assertEqual(status["dcrs"]["covered_by_task"], 1)
            self.assertEqual(status["dcrs"]["ready_for_tasking"], 0)

    def test_status_counts_public_completion_without_private_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("/agent/\n", encoding="utf-8")
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Ready."},
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [{"id": "R-201", "status": "accepted", "priority": "P1"}],
            )
            context_pack = root / "agent" / "context-packs" / "T-001-complete.md"
            context_pack.write_text(
                """# T-001: Complete

Type: `implementation`

## Requirements

- `R-201` Requirement
""",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "add", "-f", "agent/context-packs/T-001-complete.md"],
                cwd=root,
                check=True,
            )
            write_data(
                root / "docs" / "release" / "evidence.yml",
                {
                    "schema": "agentspec.release_evidence.v0",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "tasks": {
                        "agent/context-packs/T-001-complete.md": {
                            "task_id": "T-001",
                            "context_pack": "agent/context-packs/T-001-complete.md",
                            "status": "complete",
                            "run_id": "complete-t001",
                            "requirements": ["R-201"],
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001", "verdict": "ready"},
                            "updated_at": "2026-06-29T00:00:00Z",
                        }
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["tasks"]["total"], 1)
            self.assertEqual(status["tasks"]["by_status"], {"complete": 1})
            self.assertEqual(status["tasks"]["ready"], [])
            self.assertIsNone(status["tasks"]["next"])
            self.assertEqual(status["requirements"]["uncovered_accepted_examples"], [])

    def test_status_prefers_tracked_private_completion_over_older_public_fields(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / "agent").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Ready."},
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            context_pack = "agent/context-packs/T-001-complete.md"
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        context_pack: {
                            "status": "complete",
                            "run_id": "private-run",
                            "verification": {"status": "passed"},
                            "updated_at": "2026-06-30T00:00:00Z",
                        }
                    },
                },
            )
            subprocess.run(["git", "add", "agent/task-ledger.yml"], cwd=root, check=True)
            write_data(
                root / "docs" / "release" / "evidence.yml",
                {
                    "schema": "agentspec.release_evidence.v0",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "tasks": {
                        context_pack: {
                            "task_id": "T-001",
                            "context_pack": context_pack,
                            "status": "complete",
                            "run_id": "public-run",
                            "verification": {"status": "failed"},
                            "updated_at": "2026-06-29T00:00:00Z",
                        }
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["tasks"]["completed"][0]["run_id"], "private-run")
            self.assertEqual(status["tasks"]["completed"][0]["verification"]["status"], "passed")

    def test_status_normalizes_context_pack_originating_dcr_headers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {"id": "R-201", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0001"},
                    {"id": "R-202", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0002"},
                    {"id": "R-203", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0003"},
                ],
            )
            _write_dcr(root, "DCR-0001", status="accepted")
            _write_dcr(root, "DCR-0002", status="accepted")
            _write_dcr(root, "DCR-0003", status="accepted")
            (root / "agent" / "context-packs" / "T-001-slugged-origin.md").write_text(
                """# T-001: Slugged Origin

Type: `implementation`
Originating DCR: `DCR-0001-supervised-runs`

## Requirements

- `R-201` Complete
""",
                encoding="utf-8",
            )
            (root / "agent" / "context-packs" / "T-002-plural-origin.md").write_text(
                """# T-002: Plural Origin

Type: `implementation`
Originating DCRs: `DCR-0002-design-change-management`, `DCR-0003-compile-material`

## Requirements

- `R-202` Complete
- `R-203` Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-slugged-origin.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "verification": {"status": "passed"},
                        },
                        "agent/context-packs/T-002-plural-origin.md": {
                            "status": "complete",
                            "run_id": "run-002",
                            "verification": {"status": "passed"},
                        },
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["dcrs"]["covered_by_task"], 3)
            self.assertEqual(status["dcrs"]["ready_for_tasking"], 0)

    def test_status_excludes_non_implementation_dcrs_from_ready_tasking(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {"id": "R-201", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0001"},
                    {"id": "R-202", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0002"},
                    {"id": "R-203", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0005"},
                ],
            )
            _write_dcr(root, "DCR-0001", status="accepted")
            _write_dcr(root, "DCR-0002", status="classified")
            _write_dcr(root, "DCR-0003", status="accepted", classification="spike")
            _write_dcr(root, "DCR-0004", status="accepted", classification="defer")
            _write_dcr(root, "DCR-0005", status="classified", classification="implement-now")
            (root / "agent" / "context-packs" / "T-001-complete-first-dcr.md").write_text(
                """# T-001: Complete first DCR

Type: `implementation`
Originating DCR: `DCR-0001`

## Requirements

- `R-201` Complete
""",
                encoding="utf-8",
            )
            (root / "agent" / "context-packs" / "T-002-complete-second-dcr.md").write_text(
                """# T-002: Complete second DCR

Type: `implementation`
Originating DCR: `DCR-0002`

## Requirements

- `R-202` Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-complete-first-dcr.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "verification": {"status": "passed"},
                        },
                        "agent/context-packs/T-002-complete-second-dcr.md": {
                            "status": "complete",
                            "run_id": "run-002",
                            "verification": {"status": "passed"},
                        },
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["dcrs"]["by_classification"], {"defer": 1, "implement-now": 3, "spike": 1})
            self.assertEqual(status["dcrs"]["covered_by_task"], 2)
            self.assertEqual(status["dcrs"]["ready_for_tasking"], 1)

    def test_status_marks_readiness_dcr_summary_historical_when_covered(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {
                    "score": 100,
                    "mode": "normal-implementation",
                    "summary": "DCR-0001 is accepted, implementation-ready, and ready for tasking.",
                },
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [{"id": "R-201", "status": "accepted", "priority": "P1", "originating_dcr": "DCR-0001"}],
            )
            _write_dcr(root, "DCR-0001", status="accepted")
            (root / "agent" / "context-packs" / "T-001-add-local-run-comparison-summaries.md").write_text(
                """# T-001: Add local run comparison summaries

Type: `implementation`
Originating DCR: `DCR-0001`

## Requirements

- `R-201` Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-add-local-run-comparison-summaries.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "verification": {"status": "passed"},
                        },
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["dcrs"]["covered_by_task"], 1)
            self.assertEqual(status["dcrs"]["ready_for_tasking"], 0)
            self.assertEqual(status["readiness"]["summary_status"], "historical_covered_dcr")
            self.assertEqual(
                status["readiness"]["source_summary"],
                "DCR-0001 is accepted, implementation-ready, and ready for tasking.",
            )
            self.assertNotIn("implementation-ready", status["readiness"]["summary"])
            self.assertIn("already covered by task context packs", status["readiness"]["summary"])
            self.assertNotIn("implementation-ready", status["lifecycle_summary"]["readiness"]["summary"])

    def test_status_counts_requirement_originating_dcr_as_task_covered(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {
                    "score": 100,
                    "mode": "normal-implementation",
                    "summary": "DCR-0001 is accepted, implementation-ready, and taskable.",
                },
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {
                        "id": "R-201",
                        "status": "accepted",
                        "priority": "P1",
                        "originating_dcr": "DCR-0001",
                    },
                ],
            )
            _write_dcr(root, "DCR-0001", status="accepted")
            (root / "agent" / "context-packs" / "T-001-missing-origin-header.md").write_text(
                """# T-001: Missing Origin Header

Type: `implementation`

## Requirements

- `R-201` Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-missing-origin-header.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "verification": {"status": "passed"},
                        },
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["requirements"]["uncovered_accepted_examples"], [])
            self.assertEqual(status["dcrs"]["covered_by_task"], 1)
            self.assertEqual(status["dcrs"]["ready_for_tasking"], 0)
            self.assertNotIn("DCR-0001 is accepted", status["lifecycle_summary"]["main_point"])

    def test_status_counts_bare_requirement_links_as_dcr_covered(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "change-requests").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {
                    "score": 100,
                    "mode": "normal-implementation",
                    "summary": "DCR-0001 is accepted, implementation-ready, and taskable.",
                },
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {
                        "id": "R-201",
                        "status": "accepted",
                        "priority": "P1",
                        "originating_dcr": "DCR-0001",
                    },
                ],
            )
            _write_dcr(root, "DCR-0001", status="accepted")
            (root / "agent" / "context-packs" / "T-001-bare-requirement-link.md").write_text(
                """# T-001: Bare Requirement Link

Type: `implementation`

## Requirements

- R-201 Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-bare-requirement-link.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "verification": {"status": "passed"},
                        },
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["requirements"]["uncovered_accepted_examples"], [])
            self.assertEqual(status["dcrs"]["covered_by_task"], 1)
            self.assertEqual(status["dcrs"]["ready_for_tasking"], 0)

    def test_status_recommends_session_before_ready_task_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_ready_task_only(root)

            status = build_project_status(root)

            summary = status["lifecycle_summary"]
            action = summary["recommended_next_action"]
            self.assertEqual(summary["current_stage"], "task_ready_session_needed")
            self.assertIn("branch/worktree session", summary["main_point"])
            self.assertEqual(action["label"], "Claim a branch/worktree session for the ready task.")
            self.assertIn("session start", action["commands"][0])
            self.assertFalse(action["agent_display"]["show_terminal_commands"])
            self.assertNotIn("aspec", json.dumps(action["agent_display"]).lower())
            self.assertEqual(summary["current_artifact"]["session_preflight"]["status"], "missing")

    def test_status_exposes_ready_task_workflow_plan_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_ready_task_only(root)
            workflow = root / "agent" / "workflows" / "W-003-ready.md"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(
                """---
workflow_id: W-003
task_pack: agent/context-packs/T-003-ready.md
status: planned
current_stage: planning
branch: codex/t-003-ready
---

# Workflow W-003: Ready Task
""",
                encoding="utf-8",
            )
            pack = root / "agent" / "context-packs" / "T-003-ready.md"
            pack.write_text(
                pack.read_text(encoding="utf-8").replace(
                    "Type: `implementation`",
                    "Type: `implementation`\nWorkflow: `agent/workflows/W-003-ready.md`",
                ),
                encoding="utf-8",
            )

            status = build_project_status(root)

            workflow_plan = status["lifecycle_summary"]["current_artifact"]["workflow_plan"]
            self.assertEqual(workflow_plan["path"], "agent/workflows/W-003-ready.md")
            self.assertEqual(workflow_plan["status"], "planned")
            self.assertEqual(workflow_plan["current_stage"], "planning")
            self.assertEqual(workflow_plan["branch"], "codex/t-003-ready")
            self.assertIn("Workflow plan: agent/workflows/W-003-ready.md", format_project_status(status))

    def test_status_active_session_satisfies_ready_task_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_ready_task_only(root)
            with redirect_stdout(io.StringIO()):
                main(
                    [
                        "--root",
                        str(root),
                        "session",
                        "start",
                        "--task",
                        "T-003",
                        "--owner",
                        "codex",
                        "--branch",
                        "feature/status-preflight",
                        "--worktree",
                        str(root),
                        "--session-id",
                        "S-status-preflight",
                        "--json",
                    ]
                )

            status = build_project_status(root)

            summary = status["lifecycle_summary"]
            self.assertEqual(summary["current_stage"], "task_ready")
            self.assertEqual(status["execution"]["selected"]["mode"], "provider_native")
            self.assertEqual(summary["execution"]["selected"]["provider"], "current-host")
            self.assertEqual(
                summary["recommended_next_action"]["label"],
                "Continue in the provider-native host workflow.",
            )
            self.assertEqual(summary["current_artifact"]["session_preflight"]["status"], "satisfied")
            self.assertEqual(
                summary["current_artifact"]["session_preflight"]["active_session"]["session_id"],
                "S-status-preflight",
            )

    def test_status_reports_unavailable_host_capability_and_generic_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_ready_task_only(root)

            with mock.patch.dict(
                "os.environ",
                {
                    "AGENTSPEC_EXECUTION_PROVIDER": "claude",
                    "AGENTSPEC_CLAUDE_NATIVE_EXECUTION": "0",
                },
                clear=False,
            ):
                status = build_project_status(root)

            execution = status["execution"]
            self.assertEqual(execution["selected"]["mode"], "agentspec_generic_fallback")
            self.assertEqual(
                execution["unavailable_capabilities"][0]["id"],
                "claude_loop_or_dynamic_workflow",
            )
            self.assertIn("aspec run package", execution["fallback"]["commands"])

    def test_human_status_includes_active_and_recent_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            text = format_project_status(build_project_status(root))

            self.assertIn("Active Runs:", text)
            self.assertIn("run-active", text)
            self.assertIn("Recent Runs:", text)
            # run-summary-only lives only in the recent block (its status is
            # `complete`, not active or attention), so its presence proves the
            # recent block rendered rather than being suppressed.
            self.assertIn("run-summary-only", text)

    def test_human_status_includes_cleanup_eligible_sessions(self) -> None:
        text = format_project_status(
            {
                "root": "/tmp/repo",
                "overall": "idle",
                "readiness": {},
                "outcomes": {},
                "maturity": {},
                "requirements": {},
                "dcrs": {},
                "tasks": {},
                "runs": {},
                "sessions": {
                    "cleanup": {
                        "eligible": [
                            {
                                "session_id": "S-cleanup",
                                "branch": "feature/cleanup",
                                "worktree": "/tmp/cleanup-worktree",
                                "disposition": "merge",
                            }
                        ]
                    }
                },
                "agent_profiles": {},
                "workflows": {},
                "lifecycle": {},
                "recommendation": "No action.",
            }
        )

        self.assertIn("Cleanup Eligible Sessions:", text)
        self.assertIn("S-cleanup", text)
        self.assertIn("disposition=merge", text)
        self.assertIn("advisory cleanup eligible", text)

    def test_status_includes_latest_handoff_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-05T00:00:00Z",
                    "last_completed_task": {
                        "id": "T-002",
                        "context_pack": "agent/context-packs/T-002-complete.md",
                        "run_id": "run-complete",
                    },
                    "next_action": {
                        "kind": "start_task",
                        "command": "aspec run loop agent/context-packs/T-003-ready.md",
                    },
                },
            )

            status = build_project_status(root)
            self.assertEqual(status["handoff"]["path"], "agent/handoff.yml")
            self.assertEqual(status["handoff"]["last_completed_task"]["id"], "T-002")
            self.assertEqual(status["handoff"]["next_action"]["kind"], "start_task")

            text = format_project_status(status)
            self.assertIn("Handoff: agent/handoff.yml", text)
            self.assertIn("start_task", text)

    def test_status_works_without_optional_folders(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            status = build_project_status(root)

            self.assertEqual(status["schema"], PROJECT_STATUS_SCHEMA)
            self.assertEqual(status["overall"], "idle")
            self.assertEqual(status["requirements"]["total"], 0)
            self.assertEqual(status["dcrs"]["total"], 0)
            self.assertEqual(status["tasks"]["total"], 0)
            self.assertEqual(status["runs"]["total"], 0)
            self.assertEqual(status["lifecycle"]["skill_gates"]["readiness"], "disabled")

    def test_summary_only_run_has_empty_recovery_context(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            status = build_project_status(root, recent_limit=5)
            summary_only = next(
                run for run in status["runs"]["recent"]
                if run["run_id"] == "run-summary-only"
            )

            self.assertIsNone(summary_only["last_review_reason"])
            self.assertEqual(summary_only["policy_flags"], [])
            self.assertIsNone(summary_only["test_status"])
            self.assertIsNone(summary_only["last_event_ref"])
            self.assertIsNone(summary_only["last_error"])
            self.assertEqual(summary_only["recovery_command"], "aspec run inspect run-summary-only")

    def test_status_exposes_latest_structured_run_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            events_path = root / "agent" / "runs" / "run-halted" / "events.jsonl"
            with events_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "kind": "runner_result_rejected",
                            "recovery_command": "aspec run package --runner generic --run-id run-halted --json",
                            "error": {
                                "schema": "agentspec.error.v1",
                                "code": "ASPEC_RUNNER_RESULT_INVALID",
                                "layer": "execution",
                                "message": "Runner result field test_status must be one of ['failed', 'not_run', 'passed'].",
                                "retryable": False,
                                "severity": "error",
                                "operation": "run.result",
                                "recovery_command": "aspec run package --runner generic --run-id run-halted --json",
                                "details": {"mutation": "none", "run_id": "run-halted"},
                            },
                        }
                    )
                    + "\n"
                )

            status = build_project_status(root, recent_limit=5)
            halted = status["runs"]["attention"][0]

            self.assertEqual(halted["last_error"]["code"], "ASPEC_RUNNER_RESULT_INVALID")
            self.assertEqual(halted["last_error"]["layer"], "execution")
            self.assertEqual(halted["last_error"]["operation"], "run.result")
            self.assertFalse(halted["last_error"]["retryable"])
            self.assertEqual(halted["last_error"]["event_ref"], "agent/runs/run-halted/events.jsonl:3")
            self.assertEqual(
                halted["last_error"]["recovery_command"],
                "aspec run package --runner generic --run-id run-halted --json",
            )
            self.assertIn("test_status", halted["last_error"]["message"])

    def test_next_action_inspects_attention_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "next-action"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["run_id"], "run-halted")
            self.assertEqual(payload["status"], "halted")

    def test_continue_prints_active_run_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            shutil.rmtree(root / "agent" / "runs" / "run-halted")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "continue"])

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("Continue AgentSpec supervised run `run-active`.", text)
            self.assertIn("Reviewer reason: Continue scoped work.", text)

    def test_next_action_starts_ready_task_when_no_run_needs_attention(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            shutil.rmtree(root / "agent" / "runs" / "run-active")
            shutil.rmtree(root / "agent" / "runs" / "run-halted")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "next-action"])

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("Started run", text)
            self.assertIn("agent/context-packs/T-003-ready.md", text)

    def test_next_action_reports_no_action(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "next-action"])

            self.assertEqual(code, 1)
            self.assertIn("No ready task context pack found", output.getvalue())
            self.assertIn("Next options:", output.getvalue())
            self.assertIn("aspec ingest docs/source/design.md", output.getvalue())

    def test_status_deprioritizes_stale_research_attention_covered_by_completed_task(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_stale_research_attention(root)

            status = build_project_status(root, recent_limit=5)

            self.assertEqual(status["overall"], "idle")
            self.assertEqual(status["runs"]["attention"], [])
            self.assertEqual(status["runs"]["stale_attention"][0]["run_id"], "research-stale")
            self.assertIn("research-stale", [run["run_id"] for run in status["runs"]["recent"]])
            self.assertNotIn("run inspect research-stale", status["recommendation"])
            stale = status["runs"]["stale_attention"][0]["stale_attention"]
            self.assertEqual(stale["covered_by_task"], "T-004")
            self.assertEqual(
                stale["covered_paths"],
                ["src/schema.ts", "tests/schema.test.ts", "agent/task-ledger.yml"],
            )
            self.assertEqual(status["lifecycle_summary"]["current_stage"], "idle_no_ready_task")

    def test_status_deprioritizes_halted_run_for_completed_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "agent" / "runs" / "run-t007").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            (root / "agent" / "context-packs" / "T-007-task.md").write_text(
                """# T-007: Task

Type: `implementation`

## Requirements

- `R-001` Requirement
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-007-task.md": {
                            "status": "complete",
                            "run_id": "complete-t007",
                            "updated_at": "2026-05-12T10:58:15Z",
                        }
                    },
                },
            )
            write_data(
                root / "agent" / "runs" / "run-t007" / "state.yml",
                {
                    "run_id": "run-t007",
                    "status": "halted",
                    "mode": "autonomous",
                    "context_pack": "agent/context-packs/T-007-task.md",
                    "context_pack_title": "T-007: Task",
                    "iteration": 1,
                    "max_iterations": 3,
                    "last_decision": "halt",
                    "updated_at": "2026-05-12T10:59:00Z",
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["runs"]["attention"], [])
            self.assertEqual(status["runs"]["stale_attention"][0]["run_id"], "run-t007")
            stale = status["runs"]["stale_attention"][0]["stale_attention"]
            self.assertEqual(stale["covered_by_task"], "T-007")
            self.assertNotIn("run inspect run-t007", status["recommendation"])

    def test_status_surfaces_orphan_workflow_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "plans").mkdir(parents=True)
            (root / "docs" / "plans" / "phase-five-workflow.md").write_text(
                "---\nintent: Phase five\n---\n\n## Steps\n",
                encoding="utf-8",
            )

            status = build_project_status(root)
            self.assertEqual(status["overall"], "attention_needed")
            self.assertEqual(status["workflows"]["orphan_count"], 1)
            self.assertEqual(status["lifecycle"]["readiness"], "needs_attention")
            self.assertTrue(
                any(warning["type"] == "orphan_workflow" for warning in status["lifecycle"]["warnings"])
            )
            self.assertIn(
                "aspec task create --from-workflow docs/plans/phase-five-workflow.md",
                status["recommendation"],
            )

            text = format_project_status(status)
            self.assertIn("Lifecycle: needs_attention", text)
            self.assertIn("Lifecycle Warnings:", text)
            self.assertIn("Workflow Warnings:", text)
            self.assertIn("Legacy execution plan without task pack", text)
            self.assertIn("docs/plans/phase-five-workflow.md", text)
            self.assertNotIn("HOTL workflow", text)

    def test_status_ignores_completed_context_pack_missing_workflow_for_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "agent" / "reviews").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [{"id": "R-001", "status": "accepted"}])
            (root / "agent" / "context-packs" / "T-001-complete.md").write_text(
                """# T-001: Complete

Type: `implementation`
Workflow: `AgentSpec autonomous cycle`

## Requirements

- `R-001` Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "reviews" / "REVIEW-0001.yml",
                {
                    "schema": "agentspec.code_review.v0",
                    "id": "REVIEW-0001",
                    "task": {"context_pack": "agent/context-packs/T-001-complete.md"},
                    "verdict": "ready",
                },
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-complete.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "updated_at": "2026-05-10T00:00:00Z",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001"},
                        }
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["workflows"]["broken_link_count"], 1)
            self.assertEqual(status["workflows"]["broken_links"][0]["context_pack"], "agent/context-packs/T-001-complete.md")
            self.assertEqual(status["lifecycle"]["readiness"], "ready")
            self.assertFalse(
                any(warning["type"] == "broken_workflow_link" for warning in status["lifecycle"]["warnings"])
            )
            self.assertEqual(status["overall"], "idle")
            self.assertEqual(status["lifecycle_summary"]["current_stage"], "idle_no_ready_task")

    def test_status_ignores_stale_non_current_context_pack_missing_workflow_for_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "agent" / "reviews").mkdir(parents=True)
            (root / "agent" / "runs" / "run-old").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [{"id": "R-001", "status": "accepted"}])
            (root / "agent" / "context-packs" / "T-001-old.md").write_text(
                """# T-001: Old Duplicate

Type: `implementation`
Workflow: `AgentSpec autonomous cycle`

## Requirements

- `R-001` Old duplicate
""",
                encoding="utf-8",
            )
            (root / "agent" / "context-packs" / "T-002-complete.md").write_text(
                """# T-002: Complete

Type: `implementation`

## Requirements

- `R-001` Complete
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "runs" / "run-old" / "state.yml",
                {
                    "run_id": "run-old",
                    "status": "aborted",
                    "context_pack": "agent/context-packs/T-001-old.md",
                    "updated_at": "2026-05-01T00:00:00Z",
                },
            )
            write_data(
                root / "agent" / "reviews" / "REVIEW-0001.yml",
                {
                    "schema": "agentspec.code_review.v0",
                    "id": "REVIEW-0001",
                    "task": {"context_pack": "agent/context-packs/T-002-complete.md"},
                    "verdict": "ready",
                },
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-002-complete.md": {
                            "status": "complete",
                            "run_id": "run-002",
                            "updated_at": "2026-06-15T00:00:00Z",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001"},
                        }
                    },
                },
            )

            status = build_project_status(root)

            self.assertEqual(status["tasks"]["next"], None)
            self.assertEqual(status["workflows"]["broken_link_count"], 1)
            self.assertEqual(status["workflows"]["broken_links"][0]["context_pack"], "agent/context-packs/T-001-old.md")
            self.assertFalse(
                any(warning["type"] == "broken_workflow_link" for warning in status["lifecycle"]["warnings"])
            )
            self.assertEqual(status["overall"], "idle")
            self.assertEqual(status["lifecycle_summary"]["current_stage"], "idle_no_ready_task")

    def test_status_reports_broken_workflow_link_path_and_repair(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [{"id": "R-001", "status": "accepted"}])
            (root / "agent" / "context-packs" / "T-001-active.md").write_text(
                """# T-001: Active

Type: `implementation`
Workflow: `AgentSpec autonomous cycle`

## Requirements

- `R-001` Active
""",
                encoding="utf-8",
            )

            status = build_project_status(root)

            self.assertEqual(status["workflows"]["broken_link_count"], 1)
            broken = status["workflows"]["broken_links"][0]
            self.assertEqual(broken["path"], "agent/context-packs/T-001-active.md")
            self.assertEqual(broken["context_pack"], "agent/context-packs/T-001-active.md")
            self.assertEqual(broken["workflow"], "AgentSpec autonomous cycle")
            self.assertEqual(broken["reference_value"], "AgentSpec autonomous cycle")

            lifecycle_warning = next(
                warning
                for warning in status["lifecycle"]["warnings"]
                if warning["type"] == "broken_workflow_link"
            )
            self.assertEqual(lifecycle_warning["path"], "agent/context-packs/T-001-active.md")
            self.assertEqual(lifecycle_warning["reference_value"], "AgentSpec autonomous cycle")
            self.assertEqual(lifecycle_warning["recommendation"], "aspec plan agent/context-packs/T-001-active.md")
            summary = build_lifecycle_summary(
                {
                    "root": str(root),
                    "readiness": status["readiness"],
                    "requirements": status["requirements"],
                    "tasks": {"next": None},
                    "runs": {"attention": [], "active": []},
                    "workflows": status["workflows"],
                    "lifecycle": {
                        "readiness": "needs_attention",
                        "warnings": [lifecycle_warning],
                        "blocking": [],
                    },
                    "outcomes": {},
                }
            )
            self.assertEqual(
                summary["blocked_by"][0]["path"],
                "agent/context-packs/T-001-active.md",
            )
            self.assertIn(
                "aspec plan agent/context-packs/T-001-active.md",
                summary["recommended_next_action"]["commands"],
            )

    def test_status_lifecycle_reports_writeback_readiness_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs").mkdir()
            (root / "docs" / "discovery").mkdir()
            (root / "docs" / "traceability").mkdir()
            (root / "agent" / "context-packs" / "T-001-complete.md").write_text(
                """# T-001: Complete Task

Type: `implementation`

## Requirements

- `R-001` Complete
""",
                encoding="utf-8",
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [{"id": "R-001", "status": "accepted"}])
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-complete.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "updated_at": "2026-05-10T00:00:00Z",
                        }
                    },
                },
            )
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-09T00:00:00Z",
                    "current_state": {
                        "requirements": {"total": 0},
                        "tasks": {"total": 0},
                        "runs": {"total": 0},
                    },
                    "next_action": {"kind": "idle", "command": "aspec status --json"},
                },
            )
            (root / "docs" / "ROADMAP.md").write_text("# stale\n", encoding="utf-8")

            status = build_project_status(root)
            warning_types = {warning["type"] for warning in status["lifecycle"]["warnings"]}

            self.assertEqual(status["lifecycle"]["readiness"], "needs_attention")
            self.assertIn("missing_verification", warning_types)
            self.assertIn("missing_review", warning_types)
            self.assertIn("stale_handoff", warning_types)
            self.assertIn("stale_roadmap", warning_types)

            text = format_project_status(status)
            self.assertIn("Lifecycle: needs_attention", text)
            self.assertIn("missing_verification", text)
            self.assertIn("stale_roadmap", text)

    def test_status_lifecycle_ignores_local_only_run_count_handoff_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent").mkdir()
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-11T00:00:00Z",
                    "current_state": {
                        "requirements": {"total": 0},
                        "dcrs": {"total": 0},
                        "tasks": {"total": 0},
                        "runs": {"total": 3},
                    },
                    "next_action": {"kind": "idle", "command": "aspec status --json"},
                },
            )

            status = build_project_status(root)
            warning_types = {warning["type"] for warning in status["lifecycle"]["warnings"]}

            self.assertNotIn("stale_handoff", warning_types)

    def test_status_lifecycle_suppresses_legacy_missing_review_before_review_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "agent" / "reviews").mkdir()
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            (root / "agent" / "context-packs" / "T-001-legacy.md").write_text(
                "# T-001: Legacy\n\nType: `implementation`\n",
                encoding="utf-8",
            )
            (root / "agent" / "context-packs" / "T-002-current.md").write_text(
                "# T-002: Current\n\nType: `implementation`\n",
                encoding="utf-8",
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-legacy.md": {
                            "status": "complete",
                            "verification": {"status": "passed"},
                            "updated_at": "2026-05-01T00:00:00Z",
                        },
                        "agent/context-packs/T-002-current.md": {
                            "status": "complete",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001"},
                            "updated_at": "2026-05-03T00:00:00Z",
                        },
                    },
                },
            )
            write_data(
                root / "agent" / "reviews" / "REVIEW-0001.yml",
                {
                    "schema": "agentspec.code_review.v0",
                    "id": "REVIEW-0001",
                    "task": {"context_pack": "agent/context-packs/T-002-current.md"},
                    "verdict": "ready",
                },
            )

            status = build_project_status(root)
            review_warnings = [
                warning for warning in status["lifecycle"]["warnings"] if warning["type"] == "missing_review"
            ]

            self.assertEqual(review_warnings, [])

    def test_status_lifecycle_reports_missing_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            (root / "agent" / "context-packs" / "T-001-current.md").write_text(
                "# T-001: Current\n\nType: `implementation`\n",
                encoding="utf-8",
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-current.md": {
                            "status": "complete",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-9999", "path": "agent/reviews/REVIEW-9999.yml"},
                            "updated_at": "2026-05-03T00:00:00Z",
                        },
                    },
                },
            )

            status = build_project_status(root)
            review_warnings = [
                warning for warning in status["lifecycle"]["warnings"] if warning["type"] == "missing_review"
            ]

            self.assertEqual(len(review_warnings), 1)
            self.assertIn("review evidence is missing", review_warnings[0]["message"])

    def test_abort_refreshes_handoff_next_action_for_aborted_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "agent" / "reviews").mkdir()
            (root / "agent" / "runs" / "research-stale").mkdir(parents=True)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
            )
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [{"id": "R-197", "status": "accepted", "priority": "P0"}],
            )
            (root / "agent" / "context-packs" / "T-001-complete.md").write_text(
                """# T-001: Complete

Type: `implementation`

## Requirements

- `R-197` Shared write-back helpers
""",
                encoding="utf-8",
            )
            write_data(
                root / "agent" / "reviews" / "REVIEW-0001.yml",
                {
                    "schema": "agentspec.code_review.v0",
                    "id": "REVIEW-0001",
                    "task": {"context_pack": "agent/context-packs/T-001-complete.md"},
                    "verdict": "ready",
                },
            )
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-complete.md": {
                            "status": "complete",
                            "run_id": "complete-t001",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001", "path": "agent/reviews/REVIEW-0001.yml"},
                            "updated_at": "2026-05-12T21:04:31Z",
                        },
                    },
                },
            )
            write_data(
                root / "agent" / "runs" / "research-stale" / "state.yml",
                {
                    "run_id": "research-stale",
                    "status": "started",
                    "mode": "research",
                    "context_pack": "<research-mode>",
                    "context_pack_title": "Research mode (no pack)",
                    "iteration": 0,
                    "max_iterations": 3,
                    "last_decision": None,
                    "updated_at": "2026-05-12T21:01:34Z",
                },
            )
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-12T21:04:31Z",
                    "root": ".",
                    "last_completed_task": {
                        "id": "T-001",
                        "context_pack": "agent/context-packs/T-001-complete.md",
                        "run_id": "complete-t001",
                    },
                    "current_state": {
                        "requirements": {"total": 1},
                        "dcrs": {"total": 0},
                        "tasks": {"total": 1},
                    },
                    "next_action": {
                        "kind": "continue_active_run",
                        "run_id": "research-stale",
                        "command": "aspec run prompt research-stale",
                    },
                },
            )

            abort_run(root, "research-stale", reason="Superseded by completed implementation.")

            handoff = load_data(root / "agent" / "handoff.yml")
            self.assertEqual(handoff["next_action"]["kind"], "idle")
            self.assertNotIn("research-stale", json.dumps(handoff["next_action"]))
            self.assertEqual(handoff["current_state"]["tasks"]["total"], 1)

            status = build_project_status(root)
            self.assertEqual(status["runs"]["active"], [])
            self.assertEqual(status["handoff"]["next_action"]["kind"], "idle")


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs").mkdir(parents=True)
    (root / "docs" / "change-requests").mkdir(parents=True)
    (root / "docs" / "discovery").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)

    write_data(
        root / "docs" / "discovery" / "readiness.yml",
        {"score": 88, "mode": "normal-implementation", "summary": "Readiness is 88/100."},
    )
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {"id": "R-001", "status": "accepted", "priority": "P0"},
            {"id": "R-002", "status": "proposed-pending-acceptance", "priority": "P1"},
        ],
    )
    (root / "docs" / "change-requests" / "DCR-0001-test.md").write_text(
        """# DCR-0001: Test

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-04-29 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-04-29 |
| Confidence | medium |
""",
        encoding="utf-8",
    )
    (root / "agent" / "context-packs" / "T-001-ready.md").write_text(
        """# T-001: Ready Task

Type: `implementation`

## Requirements

- `R-001` Ready
""",
        encoding="utf-8",
    )
    (root / "agent" / "context-packs" / "T-002-complete.md").write_text(
        """# T-002: Complete Task

Type: `implementation`

## Requirements

- `R-002` Complete
""",
        encoding="utf-8",
    )
    (root / "agent" / "context-packs" / "T-003-ready.md").write_text(
        """# T-003: Ready Task

Type: `implementation`

## Requirements

- `R-001` Ready
""",
        encoding="utf-8",
    )
    write_data(
        root / "agent" / "task-ledger.yml",
        {
            "schema": "agentspec.task_ledger.v0",
            "tasks": {
                "agent/context-packs/T-002-complete.md": {
                    "status": "complete",
                    "run_id": "run-complete",
                    "updated_at": "2026-04-29T00:00:00Z",
                }
            },
        },
    )
    write_data(
        root / "agent" / "runs" / "run-active" / "state.yml",
        {
            "run_id": "run-active",
            "status": "running",
            "mode": "supervised",
            "context_pack": "agent/context-packs/T-001-ready.md",
            "context_pack_title": "T-001: Ready Task",
            "iteration": 1,
            "max_iterations": 3,
            "last_decision": "auto_continue",
            "updated_at": "2026-04-29T00:01:00Z",
        },
    )
    (root / "agent" / "runs" / "run-active" / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "executor_output",
                        "test_summary": {"status": "passed"},
                    }
                ),
                json.dumps(
                    {
                        "kind": "reviewer_verdict",
                        "decision": "auto_continue",
                        "reason": "Continue scoped work.",
                        "policy_flags": [],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_data(
        root / "agent" / "runs" / "run-halted" / "state.yml",
        {
            "run_id": "run-halted",
            "status": "halted",
            "mode": "autonomous",
            "context_pack": "agent/context-packs/T-001-ready.md",
            "context_pack_title": "T-001: Ready Task",
            "iteration": 2,
            "max_iterations": 3,
            "last_decision": "halt",
            "updated_at": "2026-04-29T00:02:00Z",
        },
    )
    (root / "agent" / "runs" / "run-halted" / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "executor_output",
                        "test_summary": {"status": "failed"},
                    }
                ),
                json.dumps(
                    {
                        "kind": "reviewer_verdict",
                        "decision": "halt",
                        "reason": "Touched forbidden path.",
                        "policy_flags": ["forbidden_path"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_data(
        root / "agent" / "runs" / "run-summary-only" / "summary.yml",
        {
            "schema": "agentspec.supervised_run.summary.v0",
            "run_id": "run-summary-only",
            "status": "complete",
            "mode": "research",
            "context_pack": "agent/context-packs/T-002-complete.md",
            "iteration": 1,
            "max_iterations": 2,
            "last_decision": "complete",
            "updated_at": "2026-04-29T00:00:30Z",
            "terminal": True,
        },
    )


def _write_dcr(
    root: Path,
    dcr_id: str,
    *,
    status: str = "accepted",
    classification: str = "implement-now",
) -> None:
    (root / "docs" / "change-requests" / f"{dcr_id}-test.md").write_text(
        f"""# {dcr_id}: Test

| Field | Value |
|---|---|
| Status | {status} |
| Classification | {classification} |
| Submitted | 2026-05-12 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-12 |
| Confidence | medium |
""",
        encoding="utf-8",
    )


def _seed_stale_research_attention(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "reviews").mkdir(parents=True)
    (root / "agent" / "runs" / "research-stale").mkdir(parents=True)
    (root / "docs" / "change-requests").mkdir(parents=True)
    (root / "docs" / "discovery").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "discovery" / "readiness.yml",
        {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
    )
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [{"id": "R-172", "status": "accepted", "priority": "P1"}],
    )
    (root / "docs" / "change-requests" / "DCR-0001-test.md").write_text(
        """# DCR-0001: Test

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-12 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-12 |
| Confidence | medium |
""",
        encoding="utf-8",
    )
    (root / "agent" / "context-packs" / "T-004-implementation.md").write_text(
        """# T-004: Implementation Task

Type: `implementation`

## Requirements

- `R-172` Research mode

## Allowed Paths

- `src/schema.ts`
- `tests/schema.test.ts`
- `agent/task-ledger.yml`
""",
        encoding="utf-8",
    )
    write_data(
        root / "agent" / "task-ledger.yml",
        {
            "schema": "agentspec.task_ledger.v0",
            "tasks": {
                "agent/context-packs/T-004-implementation.md": {
                    "status": "complete",
                    "run_id": "run-t-004",
                    "verification": {"status": "passed"},
                    "code_review": {"id": "REVIEW-0002", "path": "agent/reviews/REVIEW-0002.yml"},
                    "updated_at": "2026-05-12T01:00:00Z",
                }
            },
        },
    )
    write_data(
        root / "agent" / "reviews" / "REVIEW-0002.yml",
        {
            "id": "REVIEW-0002",
            "verdict": "ready",
            "task": {"context_pack": "agent/context-packs/T-004-implementation.md"},
        },
    )
    write_data(
        root / "agent" / "runs" / "research-stale" / "state.yml",
        {
            "run_id": "research-stale",
            "status": "halted",
            "mode": "research",
            "context_pack": "<research-mode>",
            "context_pack_title": "Research mode (no pack)",
            "iteration": 1,
            "max_iterations": 3,
            "last_decision": "halt",
            "updated_at": "2026-05-12T00:30:00Z",
        },
    )
    (root / "agent" / "runs" / "research-stale" / "events.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "kind": "executor_output",
                        "touched_paths": [
                            "src/schema.ts",
                            "tests/schema.test.ts",
                            "agent/task-ledger.yml",
                        ],
                        "test_summary": {"status": "passed"},
                    }
                ),
                json.dumps(
                    {
                        "kind": "reviewer_verdict",
                        "decision": "halt",
                        "reason": "Touched path(s) outside allowed scope.",
                        "policy_flags": ["forbidden_path"],
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _seed_ready_task_only(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "discovery").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "discovery" / "readiness.yml",
        {"score": 100, "mode": "normal-implementation", "summary": "Readiness is 100/100."},
    )
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [{"id": "R-209", "status": "accepted", "priority": "P1"}],
    )
    (root / "agent" / "context-packs" / "T-003-ready.md").write_text(
        """# T-003: Ready Task

Type: `implementation`

## Requirements

- `R-209` Ready

## Allowed Paths

- `agentspec/status.py`
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
