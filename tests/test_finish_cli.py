import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.roadmap import check_roadmap, write_roadmap
from agentspec.status import build_project_status


class FinishCLITests(unittest.TestCase):
    def test_finish_completes_with_review_and_updates_roadmap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_review(root, "REVIEW-0001", "agent/context-packs/T-013-task.md", "ready")
            write_data(
                root / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-09T00:00:00Z",
                    "current_state": {
                        "requirements": {"total": 0},
                        "dcrs": {"total": 0},
                        "tasks": {"total": 0},
                    },
                    "next_action": {"kind": "idle", "command": "aspec status --json"},
                },
            )
            write_roadmap(root)
            self.assertEqual(check_roadmap(root)["current"], True)

            payload = _run_json(
                root,
                [
                    "finish",
                    "T-013",
                    "--run-id",
                    "finish-t013",
                    "--test-status",
                    "passed",
                    "--review",
                    "REVIEW-0001",
                    "--json",
                ],
            )

            self.assertEqual(payload["schema"], "agentspec.finish_result.v0")
            self.assertFalse(payload["dry_run"])
            self.assertTrue(payload["completed"])
            self.assertEqual(payload["context_pack"], "agent/context-packs/T-013-task.md")
            self.assertEqual(payload["run_id"], "finish-t013")
            self.assertTrue(payload["writeback"]["ready"])
            self.assertEqual(check_roadmap(root)["current"], True)

            ledger = load_data(root / "agent" / "task-ledger.yml")
            entry = ledger["tasks"]["agent/context-packs/T-013-task.md"]
            self.assertEqual(entry["verification"]["status"], "passed")
            self.assertEqual(entry["code_review"]["id"], "REVIEW-0001")

            handoff = load_data(root / "agent" / "handoff.yml")
            self.assertEqual(handoff["last_completed_task"]["run_id"], "finish-t013")
            self.assertEqual(handoff["last_completed_task"]["code_review"]["id"], "REVIEW-0001")
            status = build_project_status(root)
            self.assertEqual(status["overall"], "idle")
            self.assertEqual(status["lifecycle"]["warnings"], [])
            self.assertEqual(handoff["current_state"]["overall"], status["overall"])
            self.assertEqual(handoff["current_state"]["recommendation"], status["recommendation"])

    def test_finish_dry_run_reports_findings_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            payload = _run_json(root, ["finish", "T-013", "--dry-run", "--json"])

            self.assertEqual(payload["schema"], "agentspec.finish_result.v0")
            self.assertTrue(payload["dry_run"])
            self.assertFalse(payload["completed"])
            self.assertFalse(payload["finishable"])
            self.assertEqual(payload["projection"]["task_id"], "T-013")
            finding_types = {finding["type"] for finding in payload["findings"]}
            self.assertIn("missing_verification", finding_types)
            self.assertIn("missing_review", finding_types)
            self.assertIn("missing_ledger", finding_types)
            self.assertIn("stale_roadmap", finding_types)

            self.assertFalse((root / "agent" / "task-ledger.yml").exists())
            self.assertFalse((root / "agent" / "handoff.yml").exists())
            self.assertFalse((root / "agent" / "runs").exists())
            self.assertFalse((root / "docs" / "ROADMAP.md").exists())

    def test_finish_strict_mode_blocks_missing_review_before_state_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            write_data(root / ".agentspec" / "config.yml", {"finish": {"enforcement": "strict"}})
            write_roadmap(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "finish",
                        "T-013",
                        "--run-id",
                        "finish-t013",
                        "--test-status",
                        "passed",
                        "--json",
                    ]
                )

            self.assertEqual(code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["error"]["type"], "FinishBlockedError")
            projection = payload["error"]["details"]["projection"]
            blocker_types = {finding["type"] for finding in projection["strict_blockers"]}
            self.assertEqual(blocker_types, {"missing_review"})
            self.assertFalse((root / "agent" / "task-ledger.yml").exists())
            self.assertFalse((root / "agent" / "runs" / "finish-t013" / "state.yml").exists())

    def test_finish_reads_lifecycle_strict_mode_and_blocks_stale_roadmap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_review(root, "REVIEW-0001", "agent/context-packs/T-013-task.md", "ready")
            write_data(root / ".agentspec" / "config.yml", {"lifecycle": {"enforcement": "strict"}})
            (root / "docs" / "ROADMAP.md").write_text("# stale\n", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "finish",
                        "T-013",
                        "--run-id",
                        "finish-t013",
                        "--test-status",
                        "passed",
                        "--review",
                        "REVIEW-0001",
                        "--json",
                    ]
                )

            self.assertEqual(code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["error"]["type"], "FinishBlockedError")
            projection = payload["error"]["details"]["projection"]
            blocker_types = {finding["type"] for finding in projection["strict_blockers"]}
            self.assertIn("stale_roadmap", blocker_types)
            roadmap_blocker = next(
                finding for finding in projection["strict_blockers"] if finding["type"] == "stale_roadmap"
            )
            self.assertEqual(roadmap_blocker["repair"], "aspec roadmap")
            self.assertFalse((root / "agent" / "task-ledger.yml").exists())
            self.assertFalse((root / "agent" / "runs" / "finish-t013" / "state.yml").exists())


def _run_json(root: Path, argv: list[str]) -> dict:
    output = io.StringIO()
    with redirect_stdout(output):
        code = main(["--root", str(root), *argv])
    if code != 0:
        raise AssertionError(output.getvalue())
    return json.loads(output.getvalue())


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [{"id": "R-013", "status": "accepted", "priority": "P0", "title": "Finish task"}],
    )
    (root / "agent" / "context-packs" / "T-013-task.md").write_text(
        """# T-013: Task

Type: `implementation`

## Requirements

- `R-013` Finish task

## Allowed Paths

- `agentspec/cli.py`
- `agentspec/writeback.py`
- `tests/test_finish_cli.py`
""",
        encoding="utf-8",
    )


def _write_review(root: Path, review_id: str, context_pack: str, verdict: str) -> None:
    write_data(
        root / "agent" / "reviews" / f"{review_id}.yml",
        {
            "schema": "agentspec.code_review.v0",
            "id": review_id,
            "task": {"selector": context_pack, "context_pack": context_pack},
            "verdict": verdict,
            "summary": "Review summary.",
            "reviewer": "codex",
            "range": "worktree",
            "created_at": "2026-05-11T00:00:00Z",
        },
    )


if __name__ == "__main__":
    unittest.main()
