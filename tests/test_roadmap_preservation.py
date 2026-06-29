import tempfile
import unittest
from pathlib import Path

from agentspec.io import load_data, write_data
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

    def test_roadmap_uses_public_release_evidence_without_task_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            (root / "agent").mkdir(parents=True)
            (root / "docs" / "traceability").mkdir(parents=True)
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            write_data(
                root / "docs" / "release" / "evidence.yml",
                {
                    "schema": "agentspec.release_evidence.v0",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "tasks": {
                        "agent/context-packs/T-013-task.md": {
                            "task_id": "T-013",
                            "context_pack": "agent/context-packs/T-013-task.md",
                            "status": "complete",
                            "run_id": "complete-t013",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001", "verdict": "ready"},
                            "updated_at": "2026-06-29T00:00:00Z",
                        }
                    },
                },
            )

            roadmap = build_roadmap(root)

            self.assertIn("`docs/release/evidence.yml`", roadmap)
            self.assertIn("`agent/context-packs/T-013-task.md`", roadmap)
            self.assertIn("complete-t013", roadmap)
            self.assertIn("passed", roadmap)
            self.assertIn("REVIEW-0001", roadmap)

    def test_roadmap_prefers_newer_public_review_over_private_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            _seed(root)
            context_pack = "agent/context-packs/T-001-test.md"
            ledger = load_data(root / "agent" / "task-ledger.yml")
            ledger["tasks"][context_pack]["code_review"] = {"id": "REVIEW-0001"}
            write_data(root / "agent" / "task-ledger.yml", ledger)
            write_data(
                root / "docs" / "release" / "evidence.yml",
                _public_evidence(
                    context_pack=context_pack,
                    task_id="T-001",
                    review_id="REVIEW-0002",
                    review_updated_at="2026-06-29T00:00:00Z",
                ),
            )

            roadmap = build_roadmap(root)
            task_row = next(line for line in roadmap.splitlines() if line.startswith("| ") and context_pack in line)

            self.assertIn("`run-001`", task_row)
            self.assertIn("passed", task_row)
            self.assertIn("REVIEW-0002", task_row)
            self.assertIn("2026-05-11T00:00:00Z", task_row)

    def test_roadmap_keeps_newer_private_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td).resolve()
            _seed(root)
            context_pack = "agent/context-packs/T-001-test.md"
            ledger = load_data(root / "agent" / "task-ledger.yml")
            ledger["tasks"][context_pack]["code_review"] = {"id": "REVIEW-0003"}
            ledger["tasks"][context_pack]["review_updated_at"] = "2026-07-01T00:00:00Z"
            write_data(root / "agent" / "task-ledger.yml", ledger)
            write_data(
                root / "docs" / "release" / "evidence.yml",
                _public_evidence(
                    context_pack=context_pack,
                    task_id="T-001",
                    review_id="REVIEW-0002",
                    review_updated_at="2026-06-29T00:00:00Z",
                ),
            )

            roadmap = build_roadmap(root)
            task_row = next(line for line in roadmap.splitlines() if line.startswith("| ") and context_pack in line)

            self.assertIn("REVIEW-0003", task_row)
            self.assertNotIn("REVIEW-0002", task_row)


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


def _public_evidence(
    *,
    context_pack: str,
    task_id: str,
    review_id: str,
    review_updated_at: str,
) -> dict:
    review = {"id": review_id, "verdict": "ready"}
    return {
        "schema": "agentspec.release_evidence.v0",
        "updated_at": review_updated_at,
        "tasks": {
            context_pack: {
                "task_id": task_id,
                "context_pack": context_pack,
                "status": "complete",
                "run_id": "public-run",
                "verification": {"status": "failed"},
                "updated_at": "2026-05-01T00:00:00Z",
                "code_review": review,
                "reviews": [review],
                "review_updated_at": review_updated_at,
            }
        },
    }


if __name__ == "__main__":
    unittest.main()
