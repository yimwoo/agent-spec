import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import write_data
from agentspec.status import PROJECT_STATUS_SCHEMA, build_project_status, format_project_status


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

    def test_human_status_mentions_next_and_attention_runs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            text = format_project_status(build_project_status(root))

            self.assertIn("AgentSpec Status", text)
            self.assertIn("Overall: attention_needed", text)
            self.assertIn("Next: T-003", text)
            self.assertIn("Attention Runs:", text)
            self.assertIn("run-halted", text)

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
            self.assertEqual(summary_only["recovery_command"], "aspec run inspect run-summary-only")

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


if __name__ == "__main__":
    unittest.main()
