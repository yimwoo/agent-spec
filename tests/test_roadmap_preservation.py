import tempfile
import unittest
from pathlib import Path

from agentspec.io import write_data
from agentspec.roadmap import (
    ROADMAP_BLOCK_BEGIN,
    ROADMAP_BLOCK_END,
    ROADMAP_MODE_FULL_FILE,
    ROADMAP_MODE_GENERATED_BLOCK,
    build_roadmap,
    check_roadmap,
    write_roadmap,
)


class RoadmapPreservationTests(unittest.TestCase):
    def test_full_file_generation_remains_default(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            _seed(root)

            path = write_roadmap(root)
            result = check_roadmap(root)

            self.assertEqual(path.relative_to(root), Path("docs/ROADMAP.md"))
            self.assertEqual(path.read_text(encoding="utf-8"), build_roadmap(root))
            self.assertEqual(result["mode"], ROADMAP_MODE_FULL_FILE)
            self.assertTrue(result["current"])

    def test_generated_block_mode_appends_block_without_rewriting_manual_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            _seed(root)
            _write_roadmap_config(root, ROADMAP_MODE_GENERATED_BLOCK)
            manual_content = "# Product Roadmap\n\nManual planning notes stay here.\n"
            roadmap = root / "docs" / "ROADMAP.md"
            roadmap.write_text(manual_content, encoding="utf-8")

            write_roadmap(root)

            text = roadmap.read_text(encoding="utf-8")
            self.assertTrue(text.startswith(manual_content))
            self.assertIn(_expected_block(root), text)
            self.assertEqual(check_roadmap(root)["current"], True)

    def test_generated_block_mode_replaces_only_managed_block(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            _seed(root)
            _write_roadmap_config(root, ROADMAP_MODE_GENERATED_BLOCK)
            before = "# Product Roadmap\n\nManual section before.\n\n"
            after = "\n\n## Release Notes\n\nManual section after.\n"
            stale_block = f"{ROADMAP_BLOCK_BEGIN}\nold generated content\n{ROADMAP_BLOCK_END}"
            roadmap = root / "docs" / "ROADMAP.md"
            roadmap.write_text(f"{before}{stale_block}{after}", encoding="utf-8")

            write_roadmap(root)

            text = roadmap.read_text(encoding="utf-8")
            self.assertTrue(text.startswith(before))
            self.assertTrue(text.endswith(after))
            self.assertIn(_expected_block(root), text)
            self.assertNotIn("old generated content", text)
            self.assertEqual(check_roadmap(root)["current"], True)

    def test_generated_block_check_fails_when_block_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            _seed(root)
            _write_roadmap_config(root, ROADMAP_MODE_GENERATED_BLOCK)
            (root / "docs" / "ROADMAP.md").write_text("# Product Roadmap\n", encoding="utf-8")

            result = check_roadmap(root)

            self.assertEqual(result["mode"], ROADMAP_MODE_GENERATED_BLOCK)
            self.assertTrue(result["exists"])
            self.assertFalse(result["current"])
            self.assertIn("managed block", result["summary"])

    def test_generated_block_check_fails_when_block_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            _seed(root)
            _write_roadmap_config(root, ROADMAP_MODE_GENERATED_BLOCK)
            stale_block = f"{ROADMAP_BLOCK_BEGIN}\nstale\n{ROADMAP_BLOCK_END}\n"
            (root / "docs" / "ROADMAP.md").write_text(stale_block, encoding="utf-8")

            result = check_roadmap(root)

            self.assertEqual(result["mode"], ROADMAP_MODE_GENERATED_BLOCK)
            self.assertTrue(result["exists"])
            self.assertFalse(result["current"])
            self.assertIn("stale", result["summary"])


def _seed(root: Path) -> None:
    (root / "agent").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(root / "docs" / "traceability" / "requirements.yml", [])
    write_data(
        root / "agent" / "handoff.yml",
        {
            "schema": "agentspec.project_handoff.v0",
            "updated_at": "2026-05-11T00:00:00Z",
            "last_completed_task": {
                "id": "T-001",
                "context_pack": "agent/context-packs/T-001-test.md",
                "run_id": "run-001",
            },
            "next_action": {"kind": "idle", "command": "aspec status --json"},
        },
    )
    write_data(
        root / "agent" / "task-ledger.yml",
        {
            "schema": "agentspec.task_ledger.v0",
            "tasks": {
                "agent/context-packs/T-001-test.md": {
                    "status": "complete",
                    "run_id": "run-001",
                    "verification": {"status": "passed"},
                    "updated_at": "2026-05-11T00:00:00Z",
                }
            },
        },
    )


def _write_roadmap_config(root: Path, mode: str) -> None:
    write_data(root / ".agentspec" / "config.yml", {"roadmap": {"mode": mode}})


def _expected_block(root: Path) -> str:
    return f"{ROADMAP_BLOCK_BEGIN}\n{build_roadmap(root).rstrip()}\n{ROADMAP_BLOCK_END}\n"


if __name__ == "__main__":
    unittest.main()
