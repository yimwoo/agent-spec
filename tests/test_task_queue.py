import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import build_parser, main
from agentspec.io import write_data
from agentspec.task import create_task_context_pack, list_task_context_packs, next_task_context_pack


class TaskQueueTests(unittest.TestCase):
    def test_list_task_context_packs_overlays_run_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            records = list_task_context_packs(root)
            by_id = {record["id"]: record for record in records}

            self.assertEqual(by_id["T-001"]["status"], "ready")
            self.assertEqual(by_id["T-001"]["requirements"][0]["status"], "accepted")
            self.assertEqual(by_id["T-002"]["status"], "complete")
            self.assertEqual(by_id["T-003"]["status"], "ready")

    def test_next_defaults_to_newest_ready_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            record = next_task_context_pack(root)

            self.assertIsNotNone(record)
            self.assertEqual(record["id"], "T-004")
            self.assertEqual(record["path"], "agent/context-packs/T-004-spike-ready.md")

    def test_next_can_select_oldest_ready_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            record = next_task_context_pack(root, order="oldest")

            self.assertIsNotNone(record)
            self.assertEqual(record["id"], "T-001")

    def test_next_can_filter_by_type(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            record = next_task_context_pack(root, task_type="spike")

            self.assertIsNotNone(record)
            self.assertEqual(record["id"], "T-004")

    def test_cli_task_next_json_does_not_recommend_unfiltered_ready_task(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "next", "--type", "review", "--json"])

            self.assertEqual(code, 1)
            payload = json.loads(output.getvalue())
            self.assertIsNone(payload["task"])
            self.assertEqual(payload["lifecycle_summary"]["current_stage"], "task_type_unavailable")
            self.assertIn("No review task context pack is ready", payload["reason"])
            self.assertNotIn("T-004", payload["reason"])
            self.assertIn("aspec task list --type review", payload["next_commands"])
            self.assertIn('aspec task create --type review --title "Prepare review work"', payload["next_commands"])
            self.assertNotIn("<title>", "\n".join(payload["next_commands"]))
            self.assertFalse(payload["agent_next_action"]["show_terminal_commands"])
            self.assertNotIn("aspec", json.dumps(payload["agent_next_action"]).lower())

    def test_cli_task_list_json_and_next(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "list", "--json"])
            self.assertEqual(code, 0)
            records = json.loads(output.getvalue())
            self.assertEqual(records[0]["id"], "T-001")
            self.assertIn("status", records[0])

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "next"])
            self.assertEqual(code, 0)
            self.assertEqual(output.getvalue().strip(), "agent/context-packs/T-004-spike-ready.md")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "next", "--order", "oldest"])
            self.assertEqual(code, 0)
            self.assertEqual(output.getvalue().strip(), "agent/context-packs/T-001-oldest-ready.md")

    def test_created_task_pack_includes_standard_verification_support_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_for_create(root)

            path = create_task_context_pack(root, requirement_id="R-010", title="Scoped task")
            text = path.read_text(encoding="utf-8")

            self.assertIn("- `agent/reviews/*.yml`", text)
            self.assertIn("- `agent/task-ledger.yml`", text)
            self.assertIn("- `agent/handoff.yml`", text)
            self.assertIn("| `agent/reviews/*.yml` | pattern; verification support |", text)
            self.assertIn("every non-verification allowed path is inferred", text)

    def test_cli_task_next_warns_about_orphan_workflow_when_no_ready_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agent" / "context-packs").mkdir(parents=True)
            (root / "docs" / "plans").mkdir(parents=True)
            (root / "docs" / "plans" / "phase-five-workflow.md").write_text(
                "---\nintent: Phase five\n---\n\n## Steps\n",
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "next"])

            self.assertEqual(code, 1)
            self.assertIn("No ready task context pack found", output.getvalue())
            self.assertIn("Why:", output.getvalue())
            self.assertIn("Recommended next action:", output.getvalue())
            self.assertIn("Terminal next commands:", output.getvalue())
            self.assertIn("Warning: Legacy execution plan without task pack", output.getvalue())
            self.assertIn("aspec task create --from-workflow docs/plans/phase-five-workflow.md", output.getvalue())

    def test_cli_task_next_json_explains_no_ready_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "docs" / "discovery").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(
                root / "docs" / "discovery" / "readiness.yml",
                {"score": 45, "mode": "discovery+spike", "summary": "Readiness is 45/100."},
            )
            write_data(root / "docs" / "traceability" / "requirements.yml", [])

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "next", "--json"])

            self.assertEqual(code, 1)
            payload = json.loads(output.getvalue())
            self.assertIsNone(payload["task"])
            self.assertEqual(payload["lifecycle_summary"]["current_stage"], "source_or_requirements_needed")
            self.assertIn("No implementation task is ready", payload["reason"])
            self.assertIn("aspec status --json", payload["next_commands"])
            self.assertIn("next_options", payload)
            self.assertTrue(payload["next_options"])
            self.assertIn("agent_next_action", payload)
            self.assertFalse(payload["agent_next_action"]["show_terminal_commands"])
            self.assertNotIn("aspec", json.dumps(payload["agent_next_action"]).lower())

    def test_task_create_help_uses_native_workflow_wording(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            build_parser(prog="aspec").parse_args(["task", "create", "--help"])

        self.assertEqual(raised.exception.code, 0)
        text = output.getvalue()
        self.assertIn("Backfill a context pack from a workflow or state file.", text)
        self.assertNotIn("HOTL workflow", text)

    def test_plan_help_uses_native_workflow_wording(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            build_parser(prog="aspec").parse_args(["plan", "--help"])

        self.assertEqual(raised.exception.code, 0)
        text = output.getvalue()
        self.assertIn("Create or link an AgentSpec workflow for a task context pack.", text)
        self.assertNotIn("HOTL", text)


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs" / "done-run").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {"id": "R-001", "status": "accepted", "priority": "P0"},
            {"id": "R-002", "status": "accepted", "priority": "P1"},
            {"id": "R-003", "status": "accepted", "priority": "P2"},
            {"id": "R-004", "status": "accepted", "priority": "P2"},
        ],
    )
    _write_pack(
        root / "agent" / "context-packs" / "T-001-oldest-ready.md",
        "T-001",
        "Oldest Ready",
        "implementation",
        "R-001",
    )
    _write_pack(
        root / "agent" / "context-packs" / "T-002-complete.md",
        "T-002",
        "Complete",
        "implementation",
        "R-002",
    )
    _write_pack(
        root / "agent" / "context-packs" / "T-003-newest-ready.md",
        "T-003",
        "Newest Ready",
        "implementation",
        "R-003",
    )
    _write_pack(
        root / "agent" / "context-packs" / "T-004-spike-ready.md",
        "T-004",
        "Spike Ready",
        "spike",
        "R-004",
    )
    write_data(
        root / "agent" / "runs" / "done-run" / "state.yml",
        {
            "run_id": "done-run",
            "status": "complete",
            "context_pack": "agent/context-packs/T-002-complete.md",
            "updated_at": "2026-04-28T20:00:00Z",
        },
    )


def _seed_for_create(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    (root / "docs" / "source").mkdir(parents=True)
    (root / "docs" / "discovery").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {
                "id": "R-010",
                "title": "Requirement",
                "description": "Update task handling.",
                "status": "accepted",
                "priority": "P1",
                "confidence": "medium",
                "source_sections": [],
                "code_targets": ["agentspec/task.py"],
                "test_targets": ["tests/test_task_queue.py"],
            }
        ],
    )
    write_data(root / "docs" / "source" / "sections.yml", [])
    write_data(root / "docs" / "source" / "sources.yml", [])
    write_data(root / "docs" / "discovery" / "assumptions.yml", [])
    write_data(root / "docs" / "discovery" / "readiness.yml", {"score": 100})


def _write_pack(path: Path, task_id: str, title: str, task_type: str, requirement_id: str) -> None:
    path.write_text(
        f"""# {task_id}: {title}

Type: `{task_type}`

## Requirements

- `{requirement_id}` Requirement

## Allowed Paths

- `agentspec/task.py`
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
