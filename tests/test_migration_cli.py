import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import build_parser, main
from agentspec.io import write_data
from agentspec.workflow import build_workflow_contract_status


class MigrationCliTests(unittest.TestCase):
    def test_legacy_execution_dry_run_reports_orphan_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            workflow = _write_workflow(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "migrate", "legacy-execution"])

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("Legacy execution migration plan (dry-run)", text)
            self.assertIn(workflow, text)
            self.assertIn("Run with --write to apply", text)
            self.assertEqual(list((root / "agent" / "context-packs").glob("T-*.md")), [])

    def test_legacy_execution_write_creates_migration_context_pack_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            workflow = _write_workflow(root)
            workflow_path = root / workflow
            original = workflow_path.read_text(encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "migrate", "legacy-execution", "--from", workflow, "--write"])

            self.assertEqual(code, 0)
            text = output.getvalue()
            packs = sorted((root / "agent" / "context-packs").glob("T-*.md"))
            self.assertEqual(len(packs), 1)
            pack_text = packs[0].read_text(encoding="utf-8")
            self.assertIn("Type: `migration`", pack_text)
            self.assertIn(f"Workflow: `{workflow}`", pack_text)
            self.assertIn("Created task pack:", text)
            self.assertIn("Rollback:", text)
            self.assertIn(str(packs[0].relative_to(root)), text)
            self.assertEqual(workflow_path.read_text(encoding="utf-8"), original)

            status = build_workflow_contract_status(root)
            self.assertEqual(status["orphan_count"], 0)
            self.assertEqual(status["artifacts"][0]["referenced_by"], [str(packs[0].relative_to(root))])

    def test_legacy_execution_write_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            workflow = _write_workflow(root)

            first = io.StringIO()
            with redirect_stdout(first):
                self.assertEqual(main(["--root", str(root), "migrate", "legacy-execution", "--write"]), 0)

            second = io.StringIO()
            with redirect_stdout(second):
                self.assertEqual(main(["--root", str(root), "migrate", "legacy-execution", "--write"]), 0)

            packs = sorted((root / "agent" / "context-packs").glob("T-*.md"))
            self.assertEqual(len(packs), 1)
            self.assertIn(workflow, second.getvalue())
            self.assertIn("already referenced", second.getvalue())

    def test_legacy_execution_from_unknown_scanned_path_fails_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            unknown = root / "docs" / "other-workflow.md"
            unknown.write_text("# External Workflow\n", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "migrate",
                        "legacy-execution",
                        "--from",
                        "docs/other-workflow.md",
                        "--write",
                        "--json",
                    ]
                )

            self.assertEqual(code, 1)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["error"]["type"], "ValueError")
            self.assertIn("not a scanner-recognized legacy execution artifact", payload["error"]["message"])
            self.assertEqual(list((root / "agent" / "context-packs").glob("T-*.md")), [])

    def test_legacy_execution_json_reports_actions_and_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            workflow = _write_workflow(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", str(root), "migrate", "legacy-execution", "--from", workflow, "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], "agentspec.legacy_execution_migration.v0")
            self.assertEqual(payload["mode"], "dry-run")
            self.assertEqual(payload["summary"]["to_create"], 1)
            self.assertEqual(payload["artifacts"][0]["path"], workflow)
            self.assertEqual(payload["artifacts"][0]["action"], "create_task_pack")
            self.assertIn("Remove created task context pack", payload["artifacts"][0]["rollback"])

    def test_migrate_help_uses_native_wording(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output), self.assertRaises(SystemExit) as raised:
            build_parser(prog="aspec").parse_args(["migrate", "legacy-execution", "--help"])

        self.assertEqual(raised.exception.code, 0)
        text = output.getvalue()
        self.assertIn("Migrate legacy execution artifacts into AgentSpec governance.", text)
        self.assertNotIn("HOTL", text)


def _seed_minimal(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "source").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    (root / "docs" / "plans").mkdir(parents=True)
    write_data(root / "docs" / "source" / "sections.yml", [])
    write_data(root / "docs" / "traceability" / "requirements.yml", [])


def _write_workflow(root: Path) -> str:
    relative = "docs/plans/phase-seven-workflow.md"
    path = root / relative
    path.write_text(
        """---
intent: Migrate phase seven execution plan
allowed_paths:
  - agentspec/migration.py
verify:
  - python -m unittest tests/test_migration_cli.py
---

# Phase Seven Workflow

## Steps

- [ ] **Step 1: Implement migration command**
action: Update `agentspec/migration.py`.
verify: python -m unittest tests/test_migration_cli.py
""",
        encoding="utf-8",
    )
    return relative


if __name__ == "__main__":
    unittest.main()
