import io
import json
import subprocess
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

    def test_cli_task_next_json_includes_session_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "next", "--type", "implementation", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["id"], "T-003")
            self.assertEqual(payload["session_preflight"]["status"], "missing")
            self.assertTrue(payload["session_preflight"]["required"])
            self.assertIn("session start", payload["session_preflight"]["recommended_command"])

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

    def test_dcr_backed_task_pack_includes_lifecycle_writeback_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_for_create(root)
            requirements = json.loads((root / "docs" / "traceability" / "requirements.yml").read_text())
            requirements[0]["originating_dcr"] = "DCR-0099"
            write_data(root / "docs" / "traceability" / "requirements.yml", requirements)
            (root / "docs" / "traceability" / "design-to-code-map.md").write_text(
                "# Design to Code Map\n", encoding="utf-8"
            )
            (root / "docs" / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
            (root / "package.json").write_text('{"name":"fixture"}', encoding="utf-8")
            (root / "src" / "index.ts").parent.mkdir(parents=True, exist_ok=True)
            (root / "src" / "index.ts").write_text("export const value = 1;\n", encoding="utf-8")
            (root / "tests" / "index.test.ts").parent.mkdir(parents=True, exist_ok=True)
            (root / "tests" / "index.test.ts").write_text("test('value', () => {});\n", encoding="utf-8")
            _write_dcr(
                root / "docs" / "change-requests" / "DCR-0099-generated-pack-scope.md"
            )

            path = create_task_context_pack(root, requirement_id="R-010", title="Scoped task")
            text = path.read_text(encoding="utf-8")

            expected_paths = [
                "agent/context-packs/T-001-scoped-task.md",
                "docs/change-requests/DCR-0099-generated-pack-scope.md",
                "docs/traceability/requirements.yml",
                "docs/traceability/design-to-code-map.md",
                "docs/ROADMAP.md",
                "agent/doc-reviews/*.yml",
                "agent/reviews/*.yml",
                "agent/task-ledger.yml",
                "agent/handoff.yml",
                "agent/workflows/W-001-scoped-task.md",
                "src/**/*.ts",
                "tests/**/*.ts",
            ]
            allowed_paths = _markdown_list_after_heading(text, "Allowed Paths")
            for expected_path in expected_paths:
                self.assertIn(expected_path, allowed_paths)
            self.assertNotIn("agentspec/task.py", allowed_paths)
            self.assertIn(
                "| `agent/workflows/W-001-scoped-task.md` | inferred; lifecycle write-back |",
                text,
            )

    def test_task_create_warns_when_context_pack_is_gitignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_for_create(root)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("/agent/\n", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "task",
                        "create",
                        "--requirement",
                        "R-010",
                        "--title",
                        "Ignored task",
                    ]
                )

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("Created task context pack: agent/context-packs/T-001-ignored-task.md", text)
            self.assertIn("Preserve: git add -f -- agent/context-packs/T-001-ignored-task.md", text)

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

    def test_cli_task_next_avoids_requirement_followup_when_outcomes_are_ready(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_no_ready_task_with_ready_outcomes(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "next", "--json"])

            self.assertEqual(code, 1)
            payload = json.loads(output.getvalue())
            self.assertIsNone(payload["task"])
            self.assertEqual(payload["lifecycle_summary"]["current_stage"], "idle_no_ready_task")
            action = payload["lifecycle_summary"]["recommended_next_action"]
            self.assertIn("all configured product outcomes", action["reason"].lower())
            commands = "\n".join(payload["next_commands"])
            self.assertNotIn("task create --requirement", commands)
            self.assertNotIn("Follow up on", commands)
            self.assertIn("aspec outcome", commands)
            option_text = json.dumps(payload["next_options"])
            self.assertIn("Run research mode", option_text)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "next"])

            self.assertEqual(code, 1)
            text = output.getvalue()
            self.assertIn("all configured product outcomes", text.lower())
            self.assertNotIn("task create --requirement", text)
            self.assertNotIn("Follow up on", text)

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


def _write_dcr(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# DCR-0099: Generated pack scope

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-25 |
| Submitted by | tester |
| Decided by | tester |
| Decided on | 2026-05-25 |
| Confidence | high |

## Summary
Generated DCR-backed task packs must include lifecycle write-back scope.
""",
        encoding="utf-8",
    )


def _markdown_list_after_heading(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    items: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == f"## {heading}":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.strip().startswith("- `") and line.strip().endswith("`"):
            items.append(line.strip()[3:-1])
    return items


def _seed_no_ready_task_with_ready_outcomes(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs" / "complete-run").mkdir(parents=True)
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
                "id": "R-120",
                "title": "FeatureDomain UI projection",
                "description": "FeatureDomain UI projection.",
                "status": "accepted",
                "priority": "P1",
            }
        ],
    )
    _write_pack(
        root / "agent" / "context-packs" / "T-001-complete.md",
        "T-001",
        "Complete R-120 Slice",
        "implementation",
        "R-120",
    )
    write_data(
        root / "agent" / "runs" / "complete-run" / "state.yml",
        {
            "run_id": "complete-run",
            "status": "complete",
            "context_pack": "agent/context-packs/T-001-complete.md",
            "updated_at": "2026-05-12T00:00:00Z",
        },
    )
    write_data(
        root / "agent" / "outcomes.yml",
        {
            "schema": "agentspec.outcomes.v0",
            "outcomes": [
                {
                    "id": "OUT-005",
                    "title": "FeatureDomain UI projection",
                    "gates": [
                        {
                            "id": "G-001",
                            "title": "FeatureDomain UI projection is verified",
                            "status": "passed",
                            "required": True,
                            "evidence": [{"kind": "test", "path": "tests/test_feature_domain.py"}],
                        }
                    ],
                }
            ],
        },
    )


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
