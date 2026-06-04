import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.run import complete_context_pack_run, loop_run, start_run
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
            stored_state = load_data(state_path)
            self.assertEqual(stored_state["completion_reason"], "Historical backfill after verification.")
            self.assertEqual(stored_state["quality_gc"]["status"], "skipped")
            self.assertEqual(stored_state["quality_gc"]["reason"], "disabled")
            ledger = load_data(ledger_path)
            self.assertEqual(ledger["tasks"]["agent/context-packs/T-013-task.md"]["status"], "complete")
            self.assertEqual(ledger["tasks"]["agent/context-packs/T-013-task.md"]["verification"]["status"], "passed")
            events = _load_events(event_path)
            self.assertEqual(events[0]["kind"], "task_marked_complete")
            self.assertEqual(events[-1]["kind"], "quality_gc_completion")
            self.assertEqual(events[-1]["quality_gc"]["status"], "skipped")

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
            event = _load_events(root / "agent" / "runs" / "complete-t013" / "events.jsonl")[0]
            self.assertEqual(event["code_review"]["id"], "REVIEW-0001")
            handoff = load_data(root / "agent" / "handoff.yml")
            self.assertEqual(handoff["last_completed_task"]["code_review"]["id"], "REVIEW-0001")
            self.assertEqual(handoff["artifacts"]["last_code_review"], "agent/reviews/REVIEW-0001.yml")

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

    def test_roadmap_refresh_updates_handoff_current_state_after_task_complete(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_review(root, "REVIEW-0001", "agent/context-packs/T-013-task.md", "ready")
            (root / "docs" / "ROADMAP.md").write_text("# stale\n", encoding="utf-8")

            _run_json(
                root,
                [
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
                ],
            )
            handoff_before = load_data(root / "agent" / "handoff.yml")
            self.assertEqual(handoff_before["current_state"]["overall"], "attention_needed")

            _run_json(root, ["roadmap", "--json"])

            status = _run_json(root, ["status", "--json"])
            self.assertEqual(status["overall"], "idle")
            self.assertEqual(status["lifecycle"]["warnings"], [])
            self.assertEqual(status["handoff"]["current_state"]["overall"], status["overall"])
            self.assertEqual(status["handoff"]["current_state"]["recommendation"], status["recommendation"])

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

    def test_cli_task_complete_json_and_existing_run_id(self) -> None:
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
            self.assertEqual(payload["quality_gc"]["status"], "skipped")

            second = io.StringIO()
            with redirect_stdout(second):
                code = main(
                    [
                        "--root",
                        str(root),
                        "task",
                        "complete",
                        "T-013",
                        "--run-id",
                        "complete-t013",
                        "--json",
                    ]
                )
            self.assertEqual(code, 0)
            payload = json.loads(second.getvalue())
            self.assertEqual(payload["status"], "complete")
            self.assertEqual(payload["run_id"], "complete-t013")

    def test_cli_task_complete_links_existing_active_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_run(root, Path("agent/context-packs/T-013-task.md"), run_id="run-t013")

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
                        "run-t013",
                        "--test-status",
                        "passed",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["status"], "complete")
            self.assertEqual(payload["run_id"], "run-t013")
            stored = load_data(root / "agent" / "runs" / "run-t013" / "state.yml")
            self.assertEqual(stored["status"], "complete")
            ledger = load_data(root / "agent" / "task-ledger.yml")
            self.assertEqual(ledger["tasks"]["agent/context-packs/T-013-task.md"]["run_id"], "run-t013")

    def test_loop_run_reuses_existing_active_context_pack_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            first = loop_run(root, Path("agent/context-packs/T-013-task.md"), run_id="run-t013")
            second = loop_run(root, Path("agent/context-packs/T-013-task.md"))

            self.assertTrue(first["started"])
            self.assertFalse(second["started"])
            self.assertEqual(second["run_id"], "run-t013")
            self.assertEqual(len(list((root / "agent" / "runs").glob("*/state.yml"))), 1)

    def test_loop_run_honors_explicit_new_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            loop_run(root, Path("agent/context-packs/T-013-task.md"), run_id="run-t013")

            explicit = loop_run(root, Path("agent/context-packs/T-013-task.md"), run_id="run-t013-next")

            self.assertTrue(explicit["started"])
            self.assertEqual(explicit["run_id"], "run-t013-next")
            self.assertEqual(len(list((root / "agent" / "runs").glob("*/state.yml"))), 2)

    def test_autonomous_empty_queue_reuses_existing_research_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            first = loop_run(root, mode="autonomous", run_id="research-active")
            second = loop_run(root, mode="autonomous")

            self.assertTrue(first["started"])
            self.assertFalse(second["started"])
            self.assertEqual(second["run_id"], "research-active")
            self.assertEqual(len(list((root / "agent" / "runs").glob("*/state.yml"))), 1)

    def test_autonomous_empty_queue_ignores_research_run_superseded_by_completed_task(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            first = loop_run(root, mode="autonomous", run_id="research-active")
            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        "agent/context-packs/T-013-task.md": {
                            "status": "complete",
                            "run_id": "complete-t013",
                            "updated_at": "9999-01-01T00:00:00Z",
                        }
                    },
                },
            )
            second = loop_run(root, mode="autonomous", run_id="research-next")

            self.assertTrue(first["started"])
            self.assertTrue(second["started"])
            self.assertEqual(second["run_id"], "research-next")
            self.assertEqual(len(list((root / "agent" / "runs").glob("*/state.yml"))), 2)

    def test_task_complete_runs_quality_gc_when_enabled_and_due(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_config(root, run_on_task_complete=True, task_interval=3)

            state = complete_context_pack_run(root, "T-013", run_id="complete-t013", test_status="passed")

            self.assertEqual(state["quality_gc"]["status"], "ran")
            self.assertEqual(state["quality_gc"]["reason"], "cadence_due")
            self.assertEqual(state["quality_gc"]["cadence"]["completed_tasks"], 1)
            self.assertTrue((root / "reports" / "quality" / "latest.yml").exists())
            self.assertTrue((root / "reports" / "quality" / "latest.md").exists())
            stored_state = load_data(root / "agent" / "runs" / "complete-t013" / "state.yml")
            self.assertEqual(stored_state["quality_gc"]["status"], "ran")
            events = _load_events(root / "agent" / "runs" / "complete-t013" / "events.jsonl")
            self.assertEqual(events[-1]["kind"], "quality_gc_completion")
            self.assertEqual(events[-1]["quality_gc"]["status"], "ran")

    def test_task_complete_skips_quality_gc_when_cadence_not_due(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_config(root, run_on_task_complete=True, task_interval=3)
            write_data(
                root / "reports" / "quality" / "latest.yml",
                {"cadence": {"completed_tasks": 0}, "marker": "preserve"},
            )

            state = complete_context_pack_run(root, "T-013", run_id="complete-t013")

            self.assertEqual(state["quality_gc"]["status"], "skipped")
            self.assertEqual(state["quality_gc"]["reason"], "cadence_not_due")
            self.assertEqual(state["quality_gc"]["cadence"]["completed_tasks_since_last_quality"], 1)
            latest = load_data(root / "reports" / "quality" / "latest.yml")
            self.assertEqual(latest["marker"], "preserve")
            self.assertFalse((root / "reports" / "quality" / "latest.md").exists())

    def test_task_complete_records_quality_gc_errors_without_blocking_completion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_config(root, run_on_task_complete=True, task_interval=3, report_dir="blocked")
            (root / "blocked").write_text("not a directory", encoding="utf-8")

            state = complete_context_pack_run(root, "T-013", run_id="complete-t013")

            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["quality_gc"]["status"], "error")
            self.assertEqual(state["quality_gc"]["error_type"], "NotADirectoryError")
            ledger = load_data(root / "agent" / "task-ledger.yml")
            self.assertEqual(ledger["tasks"]["agent/context-packs/T-013-task.md"]["status"], "complete")
            stored_state = load_data(root / "agent" / "runs" / "complete-t013" / "state.yml")
            self.assertEqual(stored_state["quality_gc"]["status"], "error")


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


def _write_config(
    root: Path,
    *,
    run_on_task_complete: bool,
    task_interval: int,
    report_dir: str | None = None,
) -> None:
    write_data(
        root / ".agentspec" / "config.yml",
        {
            "version": 1,
            "quality_gc": {
                "run_on_task_complete": run_on_task_complete,
                "task_interval": task_interval,
                "report_dir": report_dir,
            },
        },
    )


def _load_events(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _run_json(root: Path, argv: list[str]) -> dict:
    output = io.StringIO()
    with redirect_stdout(output):
        code = main(["--root", str(root), *argv])
    if code != 0:
        raise AssertionError(output.getvalue())
    return json.loads(output.getvalue())


if __name__ == "__main__":
    unittest.main()
