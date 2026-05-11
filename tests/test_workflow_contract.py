import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import write_data
from agentspec.workflow import build_workflow_contract_status, workflow_warning_lines


class WorkflowContractTests(unittest.TestCase):
    def test_drift_reports_orphan_workflow_with_native_terminology(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            workflow = _write_workflow(root)

            self.assertEqual(main(["--root", str(root), "drift"]), 0)

            report = (root / "reports" / "drift" / "latest.md").read_text(encoding="utf-8")
            self.assertIn("## Workflow Coverage", report)
            self.assertIn("- Workflow/state artifacts loaded: 1", report)
            self.assertIn(str(workflow), report)
            self.assertIn("orphan", report)
            self.assertIn(f"aspec task create --from-workflow {workflow}", report)
            self.assertNotIn("HOTL workflow", report)

    def test_workflow_summary_and_warnings_use_native_terminology(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)

            empty_status = build_workflow_contract_status(root)
            self.assertEqual(empty_status["summary"], "No workflow artifacts found.")

            workflow = _write_workflow(root)
            status = build_workflow_contract_status(root)

            self.assertEqual(status["summary"], "1/1 workflow artifact(s) lack a referencing task context pack.")
            self.assertNotIn("HOTL", status["summary"])
            warnings = workflow_warning_lines(status)
            self.assertEqual(
                warnings,
                [
                    "Legacy execution plan without task pack: "
                    f"{workflow} -> aspec task create --from-workflow {workflow}"
                ],
            )

    def test_workflow_is_referenced_when_context_pack_mentions_it(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            workflow = _write_workflow(root)
            (root / "agent" / "context-packs" / "T-001-phase-five.md").write_text(
                f"""# T-001: Phase Five

Type: `implementation`
Workflow: `{workflow}`

## Requirements

- No accepted requirement attached.

## Allowed Paths

- `agentspec/workflow.py`
""",
                encoding="utf-8",
            )

            status = build_workflow_contract_status(root)

            self.assertEqual(status["orphan_count"], 0)
            self.assertEqual(status["artifacts"][0]["referenced_by"], ["agent/context-packs/T-001-phase-five.md"])

    def test_task_with_missing_workflow_reports_broken_link(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            (root / "agent" / "context-packs" / "T-001-phase-five.md").write_text(
                """# T-001: Phase Five

Type: `implementation`
Workflow: `agent/workflows/W-001-phase-five.md`

## Requirements

- No accepted requirement attached.

## Allowed Paths

- `agentspec/workflow.py`
""",
                encoding="utf-8",
            )

            status = build_workflow_contract_status(root)

            self.assertEqual(status["orphan_count"], 0)
            self.assertEqual(status["broken_link_count"], 1)
            broken = status["broken_links"][0]
            self.assertEqual(broken["type"], "missing_workflow")
            self.assertEqual(broken["context_pack"], "agent/context-packs/T-001-phase-five.md")
            self.assertEqual(broken["workflow"], "agent/workflows/W-001-phase-five.md")

    def test_workflow_with_missing_task_backlink_is_broken_not_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            (root / "agent" / "workflows").mkdir()
            (root / "agent" / "workflows" / "W-001-phase-five.md").write_text(
                """---
task_pack: agent/context-packs/T-001-phase-five.md
---

# Phase Five Workflow
""",
                encoding="utf-8",
            )
            (root / "agent" / "context-packs" / "T-001-phase-five.md").write_text(
                """# T-001: Phase Five

Type: `implementation`
Workflow: `none`

## Requirements

- No accepted requirement attached.
""",
                encoding="utf-8",
            )

            status = build_workflow_contract_status(root)

            self.assertEqual(status["orphan_count"], 0)
            self.assertEqual(status["broken_link_count"], 1)
            self.assertEqual(status["broken_links"][0]["type"], "missing_task_workflow_reference")

    def test_native_workflow_without_task_pack_backlink_is_broken_when_task_references_it(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            (root / "agent" / "workflows").mkdir()
            (root / "agent" / "workflows" / "W-001-phase-five.md").write_text(
                "# Phase Five Workflow\n",
                encoding="utf-8",
            )
            (root / "agent" / "context-packs" / "T-001-phase-five.md").write_text(
                """# T-001: Phase Five

Type: `implementation`
Workflow: `agent/workflows/W-001-phase-five.md`

## Requirements

- No accepted requirement attached.
""",
                encoding="utf-8",
            )

            status = build_workflow_contract_status(root)

            self.assertEqual(status["orphan_count"], 0)
            self.assertEqual(status["broken_link_count"], 1)
            self.assertEqual(status["broken_links"][0]["type"], "missing_workflow_task_pack_reference")

    def test_task_create_from_workflow_scaffolds_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            workflow = _write_workflow(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "create", "--from-workflow", str(workflow)])

            self.assertEqual(code, 0)
            pack_path = root / output.getvalue().strip().removeprefix("Created task context pack: ")
            text = pack_path.read_text(encoding="utf-8")
            self.assertIn("Stream: `workflow-backfill`", text)
            self.assertIn(f"Workflow: `{workflow}`", text)
            self.assertIn("- `agentspec/workflow.py`", text)
            self.assertIn("- `agent/reviews/*.yml`", text)
            self.assertIn("- `python -m unittest tests/test_workflow_contract.py`", text)

    def test_task_create_from_workflow_does_not_attach_default_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            write_data(
                root / "docs" / "traceability" / "requirements.yml",
                [
                    {
                        "id": "R-001",
                        "title": "Unrelated accepted requirement",
                        "priority": "P0",
                        "status": "accepted",
                        "confidence": "high",
                    }
                ],
            )
            workflow = _write_workflow(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "task", "create", "--from-workflow", str(workflow)])

            self.assertEqual(code, 0)
            pack_path = root / output.getvalue().strip().removeprefix("Created task context pack: ")
            text = pack_path.read_text(encoding="utf-8")
            self.assertNotIn("`R-001`", text)
            self.assertIn("No accepted requirement attached", text)

    def test_roadmap_write_and_check(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-001-test.md": {
                            "status": "complete",
                            "run_id": "run-001",
                            "verification": {"status": "passed"},
                            "updated_at": "2026-05-10T00:00:00Z",
                        }
                    },
                },
            )
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-10T00:00:00Z",
                    "last_completed_task": {
                        "id": "T-001",
                        "context_pack": "agent/context-packs/T-001-test.md",
                        "run_id": "run-001",
                    },
                    "next_action": {"kind": "idle", "command": "aspec status --json"},
                },
            )

            self.assertEqual(main(["--root", str(root), "roadmap"]), 0)
            roadmap = root / "docs" / "ROADMAP.md"
            self.assertIn("AgentSpec Roadmap", roadmap.read_text(encoding="utf-8"))
            self.assertEqual(main(["--root", str(root), "roadmap", "--check"]), 0)

            roadmap.write_text("# stale\n", encoding="utf-8")
            self.assertEqual(main(["--root", str(root), "roadmap", "--check"]), 1)


def _seed_minimal(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "source").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    (root / "docs" / "plans").mkdir(parents=True)
    write_data(root / "docs" / "source" / "sections.yml", [])
    write_data(root / "docs" / "traceability" / "requirements.yml", [])


def _write_workflow(root: Path) -> str:
    relative = "docs/plans/phase-five-workflow.md"
    path = root / relative
    path.write_text(
        """---
intent: Implement phase five contract enforcement
allowed_paths:
  - agentspec/workflow.py
verify:
  - python -m unittest tests/test_workflow_contract.py
---

## Steps

- [ ] **Step 1: Implement scanner**
action: Update `agentspec/workflow.py`.
verify: python -m unittest tests/test_workflow_contract.py
""",
        encoding="utf-8",
    )
    return relative


if __name__ == "__main__":
    unittest.main()
