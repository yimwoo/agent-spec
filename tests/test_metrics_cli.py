import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import main
from agentspec.io import write_data
from agentspec.metrics import METRICS_SCHEMA, build_project_metrics, format_project_metrics


@contextlib.contextmanager
def pushd(path: Path):
    old = Path.cwd()
    try:
        import os

        os.chdir(path)
        yield
    finally:
        os.chdir(old)


class MetricsCLITests(unittest.TestCase):
    def test_build_project_metrics_derives_feedback_loop_rates(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            metrics = build_project_metrics(root)

            self.assertEqual(metrics["schema"], METRICS_SCHEMA)
            self.assertEqual(metrics["requirements"]["acceptance_rate"], 0.5)
            self.assertEqual(metrics["dcrs"]["open_or_classified"], 1)
            self.assertEqual(metrics["tasks"]["completion_rate"], 0.6667)
            self.assertEqual(metrics["runs"]["completion_rate"], 0.3333)
            self.assertEqual(metrics["runs"]["pause_halt_rate"], 0.3333)
            self.assertEqual(metrics["runs"]["abort_rate"], 0.3333)
            self.assertEqual(metrics["verification"]["pass_rate"], 0.5)
            self.assertEqual(metrics["policy_flags"]["by_flag"]["forbidden_path"], 1)
            self.assertEqual(metrics["policy_flags"]["reviewer_fallback_count"], 1)
            self.assertEqual(metrics["policy_flags"]["reviewer_fallback_rate"], 0.3333)
            self.assertEqual(metrics["cycle_time"]["completed_run_count"], 1)
            self.assertEqual(metrics["cycle_time"]["median_seconds"], 600.0)
            self.assertEqual(metrics["quality_gc"]["grade"], "B")
            self.assertEqual(metrics["quality_gc"]["finding_count"], 1)

    def test_cli_metrics_json_outputs_schema(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["--root", str(root), "metrics", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], METRICS_SCHEMA)
            self.assertEqual(payload["verification"]["passed"], 1)

    def test_human_metrics_output_summarizes_key_signals(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            text = format_project_metrics(build_project_metrics(root))

            self.assertIn("AgentSpec Metrics", text)
            self.assertIn("Tasks: 3 total, 2 complete (66.7%)", text)
            self.assertIn("Runs: 3 total, complete 33.3%", text)
            self.assertIn("Verification: 1 passed, 1 failed, pass rate 50.0%", text)
            self.assertIn("Quality GC: B (1 finding(s))", text)

    def test_metrics_handles_empty_workspace_without_division_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            metrics = build_project_metrics(Path(td))

            self.assertIsNone(metrics["requirements"]["acceptance_rate"])
            self.assertIsNone(metrics["tasks"]["completion_rate"])
            self.assertIsNone(metrics["runs"]["completion_rate"])
            self.assertIsNone(metrics["verification"]["pass_rate"])
            self.assertIsNone(metrics["policy_flags"]["reviewer_fallback_rate"])
            self.assertFalse(metrics["quality_gc"]["present"])

            text = format_project_metrics(metrics)
            self.assertIn("Requirements: 0 total, 0 accepted (-)", text)

    def test_cli_metrics_human_runs_from_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                with pushd(root):
                    code = main(["metrics"])

            self.assertEqual(code, 0)
            self.assertIn("AgentSpec Metrics", output.getvalue())


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs").mkdir(parents=True)
    (root / "docs" / "change-requests").mkdir(parents=True)
    (root / "docs" / "discovery").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    (root / "reports" / "quality").mkdir(parents=True)

    write_data(
        root / "docs" / "discovery" / "readiness.yml",
        {"score": 91, "mode": "normal-implementation", "summary": "Readiness is 91/100."},
    )
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [
            {"id": "R-001", "status": "accepted", "priority": "P0"},
            {"id": "R-002", "status": "proposed-pending-acceptance", "priority": "P1"},
        ],
    )
    (root / "docs" / "change-requests" / "DCR-0001-accepted.md").write_text(
        _dcr("DCR-0001", "accepted", "implement-now"),
        encoding="utf-8",
    )
    (root / "docs" / "change-requests" / "DCR-0002-classified.md").write_text(
        _dcr("DCR-0002", "classified", "defer"),
        encoding="utf-8",
    )
    for task_id in ("T-001", "T-002", "T-003"):
        (root / "agent" / "context-packs" / f"{task_id}-task.md").write_text(
            f"# {task_id}: Task\n\nType: `implementation`\n\n## Requirements\n\n- `R-001` Task\n",
            encoding="utf-8",
        )
    write_data(
        root / "agent" / "task-ledger.yml",
        {
            "schema": "agentspec.task_ledger.v0",
            "tasks": {
                "agent/context-packs/T-001-task.md": {"status": "complete"},
                "agent/context-packs/T-002-task.md": {"status": "complete"},
            },
        },
    )
    _write_run(
        root,
        "run-complete",
        {
            "status": "complete",
            "created_at": "2026-05-05T00:00:00Z",
            "updated_at": "2026-05-05T00:10:00Z",
            "verification": {"status": "passed"},
        },
        [],
    )
    _write_run(
        root,
        "run-halted",
        {
            "status": "halted",
            "created_at": "2026-05-05T00:00:00Z",
            "updated_at": "2026-05-05T00:03:00Z",
        },
        [
            {"kind": "executor_output", "test_summary": {"status": "failed"}},
            {
                "kind": "reviewer_verdict",
                "reason": "Needs operator review.",
                "policy_flags": ["forbidden_path", "model_review_unavailable"],
            },
        ],
    )
    _write_run(
        root,
        "run-aborted",
        {
            "status": "aborted",
            "created_at": "2026-05-05T00:00:00Z",
            "updated_at": "2026-05-05T00:01:00Z",
        },
        [],
    )
    write_data(
        root / "reports" / "quality" / "latest.yml",
        {
            "schema": "agentspec.quality_gc_report.v0",
            "generated_at": "2026-05-05T00:00:00Z",
            "grade": "B",
            "summary": "0 error(s), 1 warning(s), 0 info finding(s).",
            "findings": [{"id": "QG-001", "severity": "warning"}],
            "cadence": {"completed_tasks": 2, "task_interval": 3},
        },
    )


def _write_run(root: Path, run_id: str, state_updates: dict, events: list[dict]) -> None:
    state = {
        "schema": "agentspec.supervised_run.state.v0",
        "run_id": run_id,
        "mode": "supervised",
        "context_pack": "agent/context-packs/T-001-task.md",
        "context_pack_title": "T-001: Task",
        "iteration": 1,
        "max_iterations": 3,
        "last_decision": "complete",
    }
    state.update(state_updates)
    write_data(root / "agent" / "runs" / run_id / "state.yml", state)
    if events:
        lines = [json.dumps(event) for event in events]
        (root / "agent" / "runs" / run_id / "events.jsonl").write_text(
            "\n".join(lines),
            encoding="utf-8",
        )


def _dcr(dcr_id: str, status: str, classification: str) -> str:
    return f"""# {dcr_id}: Test

| Field | Value |
|---|---|
| Status | {status} |
| Classification | {classification} |
| Submitted | 2026-05-05 |
| Submitted by | user |
| Decided by | user |
| Decided on | 2026-05-05 |
| Confidence | medium |
"""
