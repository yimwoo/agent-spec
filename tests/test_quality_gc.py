import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec.quality import QUALITY_GC_SCHEMA, quality_gc_cadence_status, run_quality_gc


class QualityGCTests(unittest.TestCase):
    def test_quality_gc_writes_reports_and_promotes_doctor_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_agent_context(root)
            _write_agent_context_outputs(root)
            _set_mtime(root / "AGENTS.md", 1_700_000_000_000_000_000)
            _set_mtime(root / "docs" / "traceability" / "requirements.yml", 1_700_000_001_000_000_000)

            report = run_quality_gc(root)

            self.assertEqual(report["schema"], QUALITY_GC_SCHEMA)
            self.assertEqual(report["grade"], "B")
            self.assertTrue((root / "reports" / "quality" / "latest.yml").exists())
            self.assertTrue((root / "reports" / "quality" / "latest.md").exists())
            stored = load_data(root / "reports" / "quality" / "latest.yml")
            self.assertEqual(stored["schema"], QUALITY_GC_SCHEMA)
            stale = [
                finding
                for finding in report["findings"]
                if finding["category"] == "agent_context_freshness"
            ]
            self.assertTrue(stale, report["findings"])
            self.assertEqual(stale[0]["recovery_command"], "aspec emit --target claude,codex")
            self.assertTrue(
                any(finding["id"] == "QG-INVARIANTS-001" for finding in report["findings"]),
                report["findings"],
            )
            self.assertTrue(
                any(finding["id"] == "QG-OUTCOMES-001" for finding in report["findings"]),
                report["findings"],
            )
            self.assertEqual(report["doctor"]["agent_context_status"], "warning")
            self.assertEqual(report["handoff"]["present"], False)
            self.assertIn("cadence", report)

    def test_quality_cli_json_and_report_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            out = root / "out"
            _seed_agent_context(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "quality", "--report-dir", str(out), "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], QUALITY_GC_SCHEMA)
            self.assertTrue((out / "quality" / "latest.yml").exists())
            self.assertTrue((out / "quality" / "latest.md").exists())
            self.assertTrue((out / "doctor" / "repo-scan.yml").exists())

    def test_quality_gc_cadence_uses_previous_completed_task_count(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_agent_context(root)
            _write_completed_tasks(root, 4)
            write_data(root / "reports" / "quality" / "latest.yml", {"cadence": {"completed_tasks": 1}})

            report = run_quality_gc(root, task_interval=3)

            self.assertEqual(report["cadence"]["completed_tasks"], 4)
            self.assertEqual(report["cadence"]["completed_tasks_at_last_quality"], 1)
            self.assertEqual(report["cadence"]["completed_tasks_since_last_quality"], 3)
            self.assertEqual(report["cadence"]["was_due"], True)
            self.assertEqual(report["cadence"]["next_recommended_completed_tasks"], 7)

    def test_quality_gc_cadence_status_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_agent_context(root)
            _write_completed_tasks(root, 2)
            write_data(root / "reports" / "quality" / "latest.yml", {"cadence": {"completed_tasks": 1}})

            cadence = quality_gc_cadence_status(root, task_interval=3)

            self.assertEqual(cadence["completed_tasks"], 2)
            self.assertEqual(cadence["completed_tasks_since_last_quality"], 1)
            self.assertEqual(cadence["was_due"], False)
            self.assertFalse((root / "reports" / "quality" / "latest.md").exists())


def _seed_agent_context(root: Path) -> None:
    write_data(root / "docs" / "traceability" / "requirements.yml", [])
    write_data(root / "docs" / "discovery" / "readiness.yml", {"score": 100, "mode": "normal-implementation"})
    write_data(root / "docs" / "discovery" / "open-questions.yml", [])
    write_data(root / "agent" / "task-ledger.yml", {"schema": "agentspec.task_ledger.v0", "tasks": {}})


def _write_agent_context_outputs(root: Path) -> None:
    (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    (root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    codex_agent = root / ".codex" / "agents" / "spec-reviewer.toml"
    codex_agent.parent.mkdir(parents=True, exist_ok=True)
    codex_agent.write_text('name = "spec-reviewer"\n', encoding="utf-8")


def _write_completed_tasks(root: Path, count: int) -> None:
    ledger = {"schema": "agentspec.task_ledger.v0", "tasks": {}}
    context_dir = root / "agent" / "context-packs"
    context_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, count + 1):
        rel = f"agent/context-packs/T-{index:03d}-task.md"
        (root / rel).write_text(
            f"""# T-{index:03d}: Task

Type: `implementation`

## Requirements

- `R-{index:03d}` Requirement

## Allowed Paths

- `agentspec/example.py`
""",
            encoding="utf-8",
        )
        ledger["tasks"][rel] = {
            "status": "complete",
            "run_id": f"run-{index:03d}",
            "verification": {"status": "passed"},
            "updated_at": f"2026-05-05T00:00:0{index}Z",
        }
    write_data(root / "agent" / "task-ledger.yml", ledger)


def _set_mtime(path: Path, ns: int) -> None:
    os.utime(path, ns=(ns, ns))


if __name__ == "__main__":
    unittest.main()
