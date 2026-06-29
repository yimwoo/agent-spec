import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.run import loop_run


PROMPT = "Want me to proceed with T-008, or pick one of the others?"


class SupervisedRunLoopTests(unittest.TestCase):
    def test_loop_selects_newest_ready_pack_and_starts_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            result = loop_run(root, run_id="loop-001")

            self.assertTrue(result["started"])
            self.assertEqual(result["execution_strategy"]["mode"], "agentspec_generic_fallback")
            self.assertFalse(result["execution_strategy"]["preferred"])
            self.assertEqual(result["selected_task"]["id"], "T-008")
            self.assertEqual(result["state"]["run_id"], "loop-001")
            self.assertEqual(result["state"]["status"], "started")
            self.assertEqual(
                result["state"]["context_pack"],
                "agent/context-packs/T-008-dcr-accept-cascade-fix.md",
            )
            self.assertTrue((root / "agent" / "runs" / "loop-001" / "state.yml").exists())

    def test_loop_resumes_existing_run_and_auto_continues(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            loop_run(root, run_id="loop-001")

            result = loop_run(root, run_id="loop-001", executor_output=PROMPT)

            self.assertFalse(result["started"])
            self.assertEqual(result["review"]["decision"], "auto_continue")
            self.assertIn("Continue with T-008", result["review"]["message_to_executor"])
            self.assertEqual(result["state"]["status"], "running")

            state = load_data(root / "agent" / "runs" / "loop-001" / "state.yml")
            self.assertEqual(state["iteration"], 1)
            self.assertEqual(state["last_decision"], "auto_continue")
            self.assertIn("controller_response", [event["kind"] for event in _events(root, "loop-001")])

    def test_loop_can_start_and_resume_in_one_call(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            result = loop_run(
                root,
                Path("agent/context-packs/T-008-dcr-accept-cascade-fix.md"),
                run_id="loop-001",
                executor_output=PROMPT,
            )

            self.assertTrue(result["started"])
            self.assertEqual(result["review"]["decision"], "auto_continue")
            self.assertEqual(result["state"]["iteration"], 1)

    def test_cli_loop_json_starts_and_resumes_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "run", "loop", "--run-id", "loop-cli", "--json"])
            self.assertEqual(code, 0)
            started = json.loads(output.getvalue())
            self.assertEqual(started["selected_task"]["id"], "T-008")
            self.assertEqual(started["state"]["status"], "started")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "loop",
                        "--run-id",
                        "loop-cli",
                        "--executor-output",
                        PROMPT,
                        "--json",
                    ]
                )
            self.assertEqual(code, 0)
            resumed = json.loads(output.getvalue())
            self.assertIsNone(resumed["selected_task"])
            self.assertEqual(resumed["review"]["decision"], "auto_continue")
            self.assertEqual(resumed["state"]["status"], "running")


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs" / "done-run").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {"id": "R-007", "status": "accepted", "priority": "P1"},
            {"id": "R-127", "status": "proposed-pending-acceptance", "priority": "P2"},
        ],
    )
    _write_pack(
        root / "agent" / "context-packs" / "T-008-dcr-accept-cascade-fix.md",
        "T-008",
        "DCR Accept Cascade Fix",
    )
    _write_pack(
        root / "agent" / "context-packs" / "T-009-already-complete.md",
        "T-009",
        "Already Complete",
    )
    write_data(
        root / "agent" / "runs" / "done-run" / "state.yml",
        {
            "run_id": "done-run",
            "status": "complete",
            "context_pack": "agent/context-packs/T-009-already-complete.md",
            "updated_at": "2026-04-28T20:00:00Z",
        },
    )


def _write_pack(path: Path, task_id: str, title: str) -> None:
    path.write_text(
        f"""# {task_id}: {title}

Type: `implementation`
Host Worktree Execution: `explicit`

## Requirements

- `R-007` Requirement
- `R-127` Requirement

## Allowed Paths

- `agentspec/run.py`
- `agentspec/cli.py`
- `tests/test_supervised_run_loop.py`
""",
        encoding="utf-8",
    )


def _events(root: Path, run_id: str) -> list[dict[str, object]]:
    path = root / "agent" / "runs" / run_id / "events.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
