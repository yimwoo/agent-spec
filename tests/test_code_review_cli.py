import io
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from agentspec import review as review_module
from agentspec.cli import main
from agentspec.io import load_data, write_data


class CodeReviewCLITests(unittest.TestCase):
    def test_review_code_records_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "code",
                        "--task",
                        "T-013",
                        "--verdict",
                        "ready",
                        "--summary",
                        "No blocking findings.",
                        "--reviewer",
                        "codex",
                        "--range",
                        "HEAD",
                        "--json",
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], "agentspec.code_review.v0")
            self.assertEqual(payload["id"], "REVIEW-0001")
            self.assertEqual(payload["task"]["context_pack"], "agent/context-packs/T-013-task.md")
            self.assertEqual(payload["verdict"], "ready")
            self.assertEqual(payload["summary"], "No blocking findings.")
            self.assertEqual(payload["reviewer"], "codex")
            self.assertEqual(payload["range"], "HEAD")
            self.assertIn("created_at", payload)

            artifact = load_data(root / "agent" / "reviews" / "REVIEW-0001.yml")
            self.assertEqual(artifact, payload)

    def test_review_code_warns_when_review_artifact_is_gitignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("/agent/\n", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "code",
                        "--task",
                        "T-013",
                        "--verdict",
                        "ready",
                        "--summary",
                        "No blocking findings.",
                    ]
                )

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("Recorded code review REVIEW-0001 (ready).", text)
            self.assertIn("Preserve: git add -f -- agent/reviews/REVIEW-0001.yml", text)

    def test_review_code_retries_when_allocated_id_collides(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)
            original_write = review_module._write_data_exclusive
            collided = False

            def collide_once(path: Path, data: object) -> None:
                nonlocal collided
                if not collided:
                    collided = True
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('{"schema": "collision"}\n', encoding="utf-8")
                    raise FileExistsError(path)
                original_write(path, data)

            output = io.StringIO()
            with mock.patch.object(review_module, "_write_data_exclusive", side_effect=collide_once):
                with redirect_stdout(output):
                    code = main(
                        [
                            "--root",
                            str(root),
                            "review",
                            "code",
                            "--task",
                            "T-013",
                            "--verdict",
                            "ready",
                            "--summary",
                            "No blocking findings.",
                            "--reviewer",
                            "codex",
                            "--json",
                        ]
                    )

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["id"], "REVIEW-0002")
            self.assertTrue((root / "agent" / "reviews" / "REVIEW-0001.yml").exists())
            artifact = load_data(root / "agent" / "reviews" / "REVIEW-0002.yml")
            self.assertEqual(artifact["id"], "REVIEW-0002")

    def test_review_code_rejects_unknown_task_before_writing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root)

            err = io.StringIO()
            with redirect_stderr(err):
                code = main(
                    [
                        "--root",
                        str(root),
                        "review",
                        "code",
                        "--task",
                        "T-999",
                        "--verdict",
                        "ready",
                        "--summary",
                        "No blocking findings.",
                    ]
                )

            self.assertEqual(code, 1)
            self.assertIn("Task not found", err.getvalue())
            self.assertFalse((root / "agent" / "reviews").exists())


def _seed(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(
        root / "docs" / "traceability" / "requirements.yml",
        [{"id": "R-007", "status": "accepted", "priority": "P1"}],
    )
    (root / "agent" / "context-packs" / "T-013-task.md").write_text(
        """# T-013: Task

Type: `implementation`

## Requirements

- `R-007` Requirement
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
