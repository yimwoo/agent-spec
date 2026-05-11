import tempfile
import unittest
from pathlib import Path

from agentspec.io import write_data
from agentspec.status import build_project_status
from agentspec.writeback import (
    build_completion_projection,
    update_handoff,
    update_roadmap,
    update_task_ledger,
    verify_writeback,
)


class WriteBackTests(unittest.TestCase):
    def test_writeback_helpers_update_existing_formats(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            _write_review(root, "REVIEW-0001", "agent/context-packs/T-001-task.md", "ready")
            completion = _completion(review_id="REVIEW-0001")

            ledger_entry = update_task_ledger(root, completion)
            self.assertEqual(ledger_entry["verification"]["status"], "passed")
            self.assertEqual(ledger_entry["code_review"]["id"], "REVIEW-0001")

            handoff = update_handoff(root, completion, build_project_status(root))
            self.assertEqual(handoff["last_completed_task"]["context_pack"], completion["context_pack"])
            self.assertEqual(handoff["last_completed_task"]["code_review"]["id"], "REVIEW-0001")
            self.assertEqual(handoff["artifacts"]["last_code_review"], "agent/reviews/REVIEW-0001.yml")

            roadmap_path = update_roadmap(root)
            self.assertTrue(roadmap_path.exists())

            projection = build_completion_projection(root, "T-001")
            self.assertEqual(projection["schema"], "agentspec.completion_projection.v0")
            self.assertEqual(projection["status"], "ready")
            self.assertEqual(projection["findings"], [])

            verification = verify_writeback(root, completion)
            self.assertTrue(verification["ready"])
            self.assertEqual(verification["findings"], [])

    def test_verify_writeback_reports_missing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            update_task_ledger(
                root,
                {
                    **_completion(review_id=None),
                    "verification": {"status": "failed"},
                    "code_review": None,
                },
            )

            verification = verify_writeback(root, "agent/context-packs/T-001-task.md")

            self.assertFalse(verification["ready"])
            finding_types = {finding["type"] for finding in verification["findings"]}
            self.assertIn("missing_verification", finding_types)
            self.assertIn("missing_review", finding_types)
            self.assertIn("missing_handoff", finding_types)
            self.assertIn("stale_roadmap", finding_types)


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [{"id": "R-001", "status": "accepted", "priority": "P0", "title": "Test requirement"}],
    )
    (root / "agent" / "context-packs" / "T-001-task.md").write_text(
        """# T-001: Task

Type: `implementation`

## Requirements

- `R-001` Test requirement

## Allowed Paths

- `agentspec/writeback.py`
- `tests/test_writeback.py`
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


def _completion(review_id: str | None) -> dict:
    code_review = None
    if review_id:
        code_review = {
            "id": review_id,
            "verdict": "ready",
            "summary": "Review summary.",
            "reviewer": "codex",
            "range": "worktree",
            "path": f"agent/reviews/{review_id}.yml",
        }
    return {
        "status": "complete",
        "run_id": "complete-t001",
        "context_pack": "agent/context-packs/T-001-task.md",
        "context_pack_title": "T-001: Task",
        "task_type": "implementation",
        "allowed_paths": ["agentspec/writeback.py", "tests/test_writeback.py"],
        "iteration": 1,
        "max_iterations": 3,
        "profiles": {},
        "created_at": "2026-05-11T00:00:00Z",
        "updated_at": "2026-05-11T00:00:00Z",
        "last_decision": "complete",
        "completion_reason": "Done.",
        "verification": {"status": "passed"},
        "code_review": code_review,
    }


if __name__ == "__main__":
    unittest.main()
