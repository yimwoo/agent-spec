import tempfile
import unittest
from pathlib import Path

from agentspec.io import load_data, write_data
from agentspec.run import resume_run, start_run
from agentspec.task import list_task_context_packs, next_task_context_pack, record_task_ledger_status


class TaskLedgerTests(unittest.TestCase):
    def test_task_list_uses_ledger_without_local_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            record_task_ledger_status(
                root,
                context_pack="agent/context-packs/T-001-ledger-complete.md",
                status="complete",
                run_id="shared-run",
                reason="Committed completion.",
                test_status="passed",
                updated_at="2026-04-28T20:00:00Z",
            )

            records = list_task_context_packs(root)
            by_id = {record["id"]: record for record in records}
            self.assertEqual(by_id["T-001"]["status"], "complete")
            self.assertEqual(by_id["T-001"]["status_source"], "ledger")
            self.assertIn("shared-run", by_id["T-001"]["status_reason"])

            next_record = next_task_context_pack(root)
            self.assertIsNotNone(next_record)
            self.assertEqual(next_record["id"], "T-002")

    def test_newer_local_run_state_overrides_older_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            record_task_ledger_status(
                root,
                context_pack="agent/context-packs/T-001-ledger-complete.md",
                status="complete",
                run_id="old-ledger",
                updated_at="2026-04-28T20:00:00Z",
            )
            write_data(
                root / "agent" / "runs" / "newer-run" / "state.yml",
                {
                    "run_id": "newer-run",
                    "status": "paused",
                    "context_pack": "agent/context-packs/T-001-ledger-complete.md",
                    "updated_at": "2026-04-28T21:00:00Z",
                },
            )

            record = list_task_context_packs(root)[0]
            self.assertEqual(record["status"], "paused")
            self.assertEqual(record["status_source"], "run")
            self.assertIn("newer-run", record["status_reason"])

    def test_newer_ledger_overrides_older_local_run_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            write_data(
                root / "agent" / "runs" / "old-run" / "state.yml",
                {
                    "run_id": "old-run",
                    "status": "paused",
                    "context_pack": "agent/context-packs/T-001-ledger-complete.md",
                    "updated_at": "2026-04-28T20:00:00Z",
                },
            )
            record_task_ledger_status(
                root,
                context_pack="agent/context-packs/T-001-ledger-complete.md",
                status="complete",
                run_id="new-ledger",
                updated_at="2026-04-28T21:00:00Z",
            )

            record = list_task_context_packs(root)[0]
            self.assertEqual(record["status"], "complete")
            self.assertEqual(record["status_source"], "ledger")
            self.assertIn("new-ledger", record["status_reason"])

    def test_completed_ledger_ignores_newer_aborted_stale_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            record_task_ledger_status(
                root,
                context_pack="agent/context-packs/T-001-ledger-complete.md",
                status="complete",
                run_id="finish-run",
                updated_at="2026-04-28T20:00:00Z",
            )
            write_data(
                root / "agent" / "runs" / "stale-run" / "state.yml",
                {
                    "run_id": "stale-run",
                    "status": "aborted",
                    "context_pack": "agent/context-packs/T-001-ledger-complete.md",
                    "updated_at": "2026-04-28T21:00:00Z",
                },
            )

            records = list_task_context_packs(root)
            by_id = {record["id"]: record for record in records}
            self.assertEqual(by_id["T-001"]["status"], "complete")
            self.assertEqual(by_id["T-001"]["status_source"], "ledger")
            self.assertIn("finish-run", by_id["T-001"]["status_reason"])

            next_record = next_task_context_pack(root)
            self.assertIsNotNone(next_record)
            self.assertEqual(next_record["id"], "T-002")

    def test_record_task_ledger_status_writes_sorted_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            record_task_ledger_status(
                root,
                context_pack="agent/context-packs/T-002-ready.md",
                status="complete",
                run_id="run-2",
            )
            record_task_ledger_status(
                root,
                context_pack="agent/context-packs/T-001-ledger-complete.md",
                status="complete",
                run_id="run-1",
            )

            ledger = load_data(root / "agent" / "task-ledger.yml")
            self.assertEqual(ledger["schema"], "agentspec.task_ledger.v0")
            self.assertEqual(list(ledger["tasks"].keys()), sorted(ledger["tasks"].keys()))

    def test_completed_supervised_run_updates_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            start_run(root, Path("agent/context-packs/T-001-ledger-complete.md"), run_id="run-001")

            resume_run(
                root,
                "run-001",
                executor_output="Done. Acceptance criteria are met.",
                touched_paths=["agentspec/task.py"],
                test_status="passed",
            )

            ledger = load_data(root / "agent" / "task-ledger.yml")
            entry = ledger["tasks"]["agent/context-packs/T-001-ledger-complete.md"]
            self.assertEqual(entry["status"], "complete")
            self.assertEqual(entry["run_id"], "run-001")
            self.assertEqual(entry["verification"]["status"], "passed")

            handoff = load_data(root / "agent" / "handoff.yml")
            self.assertEqual(handoff["schema"], "agentspec.project_handoff.v0")
            self.assertEqual(handoff["last_completed_task"]["id"], "T-001")
            self.assertEqual(handoff["last_completed_task"]["run_id"], "run-001")


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [{"id": "R-007", "status": "accepted", "priority": "P1"}],
    )
    _write_pack(root / "agent" / "context-packs" / "T-001-ledger-complete.md", "T-001", "Ledger Complete")
    _write_pack(root / "agent" / "context-packs" / "T-002-ready.md", "T-002", "Ready")


def _write_pack(path: Path, task_id: str, title: str) -> None:
    path.write_text(
        f"""# {task_id}: {title}

Type: `implementation`

## Requirements

- `R-007` Requirement

## Allowed Paths

- `agentspec/task.py`
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
