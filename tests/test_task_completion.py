import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.run import complete_context_pack_run
from agentspec.task import list_task_context_packs


class TaskCompletionTests(unittest.TestCase):
    def test_complete_context_pack_by_task_id_writes_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            state = complete_context_pack_run(
                root,
                "T-013",
                run_id="complete-t013",
                reason="Historical backfill after verification.",
                test_status="passed",
            )

            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["context_pack"], "agent/context-packs/T-013-task.md")
            self.assertEqual(state["last_decision"], "complete")
            self.assertEqual(state["verification"]["status"], "passed")

            state_path = root / "agent" / "runs" / "complete-t013" / "state.yml"
            event_path = root / "agent" / "runs" / "complete-t013" / "events.jsonl"
            ledger_path = root / "agent" / "task-ledger.yml"
            self.assertTrue(state_path.exists())
            self.assertTrue(ledger_path.exists())
            self.assertEqual(load_data(state_path)["completion_reason"], "Historical backfill after verification.")
            ledger = load_data(ledger_path)
            self.assertEqual(ledger["tasks"]["agent/context-packs/T-013-task.md"]["status"], "complete")
            self.assertEqual(ledger["tasks"]["agent/context-packs/T-013-task.md"]["verification"]["status"], "passed")
            self.assertEqual(json.loads(event_path.read_text(encoding="utf-8").strip())["kind"], "task_marked_complete")

            handoff = load_data(root / "agent" / "handoff.yml")
            self.assertEqual(handoff["schema"], "agentspec.project_handoff.v0")
            self.assertEqual(handoff["root"], ".")
            self.assertEqual(handoff["last_completed_task"]["id"], "T-013")
            self.assertEqual(handoff["last_completed_task"]["context_pack"], "agent/context-packs/T-013-task.md")
            self.assertEqual(handoff["last_completed_task"]["run_id"], "complete-t013")
            self.assertEqual(handoff["next_action"]["kind"], "idle")
            self.assertEqual(handoff["commands"]["status"], "aspec status --json")

    def test_complete_context_pack_by_path_updates_task_list_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            complete_context_pack_run(
                root,
                "agent/context-packs/T-013-task.md",
                run_id="complete-t013",
            )

            records = list_task_context_packs(root)
            by_id = {record["id"]: record for record in records}
            self.assertEqual(by_id["T-013"]["status"], "complete")
            self.assertIn("complete-t013", by_id["T-013"]["status_reason"])

    def test_complete_links_ready_code_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_review(root, "REVIEW-0001", "agent/context-packs/T-013-task.md", "ready")

            state = complete_context_pack_run(
                root,
                "T-013",
                run_id="complete-t013",
                reason="Verified with code review.",
                test_status="passed",
                review_id="REVIEW-0001",
            )

            self.assertEqual(state["code_review"]["id"], "REVIEW-0001")
            self.assertEqual(state["code_review"]["verdict"], "ready")
            ledger = load_data(root / "agent" / "task-ledger.yml")
            entry = ledger["tasks"]["agent/context-packs/T-013-task.md"]
            self.assertEqual(entry["code_review"]["id"], "REVIEW-0001")
            self.assertEqual(entry["code_review"]["verdict"], "ready")
            event = json.loads(
                (root / "agent" / "runs" / "complete-t013" / "events.jsonl")
                .read_text(encoding="utf-8")
                .strip()
            )
            self.assertEqual(event["code_review"]["id"], "REVIEW-0001")

    def test_cli_task_complete_links_code_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_review(root, "REVIEW-0001", "agent/context-packs/T-013-task.md", "ready-with-warnings")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "task",
                        "complete",
                        "T-013",
                        "--run-id",
                        "complete-t013",
                        "--test-status",
                        "passed",
                        "--review",
                        "REVIEW-0001",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["code_review"]["id"], "REVIEW-0001")
            self.assertEqual(payload["code_review"]["verdict"], "ready-with-warnings")

    def test_complete_rejects_not_ready_code_review_before_state_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_review(root, "REVIEW-0001", "agent/context-packs/T-013-task.md", "not-ready")

            with self.assertRaises(ValueError):
                complete_context_pack_run(
                    root,
                    "T-013",
                    run_id="complete-t013",
                    test_status="passed",
                    review_id="REVIEW-0001",
                )

            self.assertFalse((root / "agent" / "runs" / "complete-t013" / "state.yml").exists())

    def test_complete_rejects_mismatched_code_review_before_state_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_pack(root / "agent" / "context-packs" / "T-014-other.md", "T-014", "Other")
            _write_review(root, "REVIEW-0001", "agent/context-packs/T-014-other.md", "ready")

            with self.assertRaises(ValueError):
                complete_context_pack_run(
                    root,
                    "T-013",
                    run_id="complete-t013",
                    test_status="passed",
                    review_id="REVIEW-0001",
                )

            self.assertFalse((root / "agent" / "runs" / "complete-t013" / "state.yml").exists())

    def test_complete_refuses_unknown_or_ambiguous_task_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            with self.assertRaises(FileNotFoundError):
                complete_context_pack_run(root, "T-999", run_id="missing")

            _write_pack(root / "agent" / "context-packs" / "T-013-other.md", "T-013", "Other")
            with self.assertRaises(ValueError):
                complete_context_pack_run(root, "T-013", run_id="ambiguous")

    def test_complete_preflights_ledger_before_writing_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            write_data(root / "agent" / "task-ledger.yml", {"schema": "agentspec.task_ledger.v0", "tasks": []})

            with self.assertRaises(ValueError):
                complete_context_pack_run(root, "T-013", run_id="bad-ledger")

            self.assertFalse((root / "agent" / "runs" / "bad-ledger" / "state.yml").exists())

    def test_cli_task_complete_json_and_duplicate_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "task",
                        "complete",
                        "T-013",
                        "--run-id",
                        "complete-t013",
                        "--test-status",
                        "passed",
                        "--json",
                    ]
                )
            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "complete")
            self.assertEqual(payload["verification"]["status"], "passed")

            err = io.StringIO()
            with redirect_stderr(err):
                code = main(
                    [
                        "--root",
                        str(root),
                        "task",
                        "complete",
                        "T-013",
                        "--run-id",
                        "complete-t013",
                    ]
                )
            self.assertEqual(code, 1)
            self.assertIn("Run already exists", err.getvalue())


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [{"id": "R-007", "status": "accepted", "priority": "P1"}],
    )
    _write_pack(root / "agent" / "context-packs" / "T-013-task.md", "T-013", "Task")


def _write_pack(path: Path, task_id: str, title: str) -> None:
    path.write_text(
        f"""# {task_id}: {title}

Type: `implementation`

## Requirements

- `R-007` Requirement

## Allowed Paths

- `agentspec/run.py`
- `agentspec/cli.py`
- `tests/test_task_completion.py`
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
            "created_at": "2026-05-02T00:00:00Z",
        },
    )


if __name__ == "__main__":
    unittest.main()
