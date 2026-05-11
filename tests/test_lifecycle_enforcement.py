import tempfile
import unittest
from pathlib import Path

from agentspec.io import write_data
from agentspec.status import build_project_status


class LifecycleEnforcementTests(unittest.TestCase):
    def test_warn_mode_keeps_lifecycle_findings_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_completed_task_with_drift(root)

            lifecycle = build_project_status(root)["lifecycle"]

            self.assertEqual(lifecycle["enforcement"], "warn")
            self.assertEqual(lifecycle["readiness"], "needs_attention")
            self.assertEqual(lifecycle["counts"]["blocking"], 0)
            self.assertEqual(lifecycle["blocking"], [])
            self.assertTrue(all(finding["severity"] == "warning" for finding in lifecycle["warnings"]))

    def test_strict_mode_reports_blocking_lifecycle_findings_with_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_completed_task_with_drift(root)
            write_data(root / ".agentspec" / "config.yml", {"lifecycle": {"enforcement": "strict"}})

            lifecycle = build_project_status(root)["lifecycle"]

            self.assertEqual(lifecycle["enforcement"], "strict")
            self.assertEqual(lifecycle["readiness"], "blocked")
            self.assertGreater(lifecycle["counts"]["blocking"], 0)
            blocker_types = {finding["type"] for finding in lifecycle["blocking"]}
            self.assertIn("missing_verification", blocker_types)
            self.assertIn("missing_review", blocker_types)
            self.assertIn("stale_roadmap", blocker_types)
            for finding in lifecycle["blocking"]:
                self.assertTrue(finding.get("repair") or finding.get("recommendation"), finding)

    def test_strict_mode_blocks_orphan_and_broken_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            write_data(root / ".agentspec" / "config.yml", {"lifecycle": {"enforcement": "strict"}})
            _write_orphan_workflow(root)
            _write_broken_workflow_link(root)

            lifecycle = build_project_status(root)["lifecycle"]

            blocker_types = {finding["type"] for finding in lifecycle["blocking"]}
            self.assertIn("orphan_workflow", blocker_types)
            self.assertIn("broken_workflow_link", blocker_types)
            orphan = next(finding for finding in lifecycle["blocking"] if finding["type"] == "orphan_workflow")
            broken = next(finding for finding in lifecycle["blocking"] if finding["type"] == "broken_workflow_link")
            self.assertIn("aspec task create --from-workflow", orphan["recommendation"])
            self.assertTrue(broken.get("repair") or broken.get("recommendation"))

    def test_stale_handoff_remains_warning_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            write_data(root / ".agentspec" / "config.yml", {"lifecycle": {"enforcement": "strict"}})
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "current_state": {
                        "requirements": {"total": 99},
                        "tasks": {"total": 99},
                        "runs": {"total": 99},
                    },
                    "next_action": {"kind": "idle", "command": "aspec status --json"},
                },
            )

            lifecycle = build_project_status(root)["lifecycle"]

            stale_handoff = [finding for finding in lifecycle["warnings"] if finding["type"] == "stale_handoff"]
            self.assertEqual(lifecycle["counts"]["blocking"], 0)
            self.assertEqual(lifecycle["blocking"], [])
            self.assertEqual(len(stale_handoff), 1)
            self.assertEqual(stale_handoff[0]["severity"], "warning")


def _seed_minimal(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    (root / "docs" / "plans").mkdir(parents=True)
    write_data(root / "docs" / "traceability" / "requirements.yml", [])


def _seed_completed_task_with_drift(root: Path) -> None:
    _seed_minimal(root)
    (root / "agent" / "context-packs" / "T-001-complete.md").write_text(
        """# T-001: Complete Task

Type: `implementation`

## Requirements

- `R-001` Complete
""",
        encoding="utf-8",
    )
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [{"id": "R-001", "status": "accepted", "priority": "P0", "title": "Complete"}],
    )
    write_data(
        root / "agent" / "task-ledger.yml",
        {
            "schema": "agentspec.task_ledger.v0",
            "tasks": {
                "agent/context-packs/T-001-complete.md": {
                    "status": "complete",
                    "run_id": "run-001",
                    "verification": {"status": "failed"},
                    "updated_at": "2026-05-11T00:00:00Z",
                }
            },
        },
    )
    (root / "docs" / "ROADMAP.md").write_text("# stale\n", encoding="utf-8")


def _write_orphan_workflow(root: Path) -> None:
    (root / "docs" / "plans" / "2026-05-11-orphan-workflow.md").write_text(
        """---
intent: Orphan workflow
---

## Steps

- [ ] **Step 1: Do work**
action: Exercise orphan workflow detection.
loop: false
verify: python -m unittest tests/test_lifecycle_enforcement.py -v
""",
        encoding="utf-8",
    )


def _write_broken_workflow_link(root: Path) -> None:
    (root / "agent" / "context-packs" / "T-002-broken.md").write_text(
        """# T-002: Broken Workflow Link

Type: `implementation`
Workflow: `agent/workflows/W-001-missing.md`

## Requirements

- No accepted requirement attached.
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
