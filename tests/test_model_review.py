import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from agentspec.cli import main
from agentspec.model_review import MODEL_REVIEW_SCHEMA, _resolve_chat_settings
from agentspec.run import resume_run, start_run


PACK = """# T-018: Model Reviewer

Type: `implementation`

## Allowed Paths

- `agentspec/model_review.py`
- `agentspec/review.py`
- `tests/test_model_review.py`
"""


def _verdict(decision: str, *, message: str | None = "Continue with T-018.") -> str:
    return json.dumps(
        {
            "schema": MODEL_REVIEW_SCHEMA,
            "decision": decision,
            "confidence": "high",
            "reason": f"static {decision}",
            "message_to_executor": message,
        }
    )


class ModelReviewTests(unittest.TestCase):
    def test_model_reviewer_can_auto_continue_deterministic_pause(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, _verdict("auto_continue", message="Continue with T-018 under the active pack."))
            start_run(root, Path("agent/context-packs/T-018-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="Should I continue this implementation?",
                reviewer_mode="model",
            )

            review = result["review"]
            self.assertEqual(review["decision"], "auto_continue")
            self.assertFalse(review["requires_human"])
            self.assertIn("Model reviewer", review["reason"])
            self.assertIn("model_reviewer", review["evidence_refs"])
            self.assertEqual(review["message_to_executor"], "Continue with T-018 under the active pack.")
            self.assertEqual(result["state"]["status"], "running")

    def test_policy_halt_cannot_be_overridden_by_model(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, _verdict("auto_continue"))
            start_run(root, Path("agent/context-packs/T-018-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="Should I continue this implementation?",
                touched_paths=["docs/source/sections.yml"],
                reviewer_mode="model",
            )

            review = result["review"]
            self.assertEqual(review["decision"], "halt")
            self.assertTrue(review["requires_human"])
            self.assertIn("forbidden_path", review["policy_flags"])
            self.assertNotIn("model_reviewer", review["evidence_refs"])
            self.assertEqual(result["state"]["status"], "halted")

    def test_invalid_model_response_falls_back_to_deterministic_pause(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, "not json")
            start_run(root, Path("agent/context-packs/T-018-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="Should I continue this implementation?",
                reviewer_mode="model",
            )

            review = result["review"]
            self.assertEqual(review["decision"], "pause_for_human")
            self.assertTrue(review["requires_human"])
            self.assertIn("model_review_unavailable", review["policy_flags"])
            self.assertIn("invalid", review["reason"])
            self.assertEqual(result["state"]["status"], "paused")

    def test_wrong_model_schema_falls_back_to_deterministic_pause(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(
                root,
                json.dumps(
                    {
                        "schema": "wrong.schema",
                        "decision": "auto_continue",
                        "confidence": "high",
                        "reason": "schema drift",
                        "message_to_executor": "Continue.",
                    }
                ),
            )
            start_run(root, Path("agent/context-packs/T-018-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="Should I continue this implementation?",
                reviewer_mode="model",
            )

            review = result["review"]
            self.assertEqual(review["decision"], "pause_for_human")
            self.assertIn("model_review_unavailable", review["policy_flags"])
            self.assertIn(MODEL_REVIEW_SCHEMA, review["reason"])
            self.assertEqual(result["state"]["status"], "paused")

    def test_unavailable_model_response_falls_back_to_deterministic_pause(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, None)
            start_run(root, Path("agent/context-packs/T-018-test.md"), run_id="run-001")

            result = resume_run(
                root,
                "run-001",
                executor_output="Should I continue this implementation?",
                reviewer_mode="model",
            )

            review = result["review"]
            self.assertEqual(review["decision"], "pause_for_human")
            self.assertTrue(review["requires_human"])
            self.assertIn("model_review_unavailable", review["policy_flags"])
            self.assertIn("fell back", review["reason"])
            self.assertEqual(result["state"]["status"], "paused")

    def test_model_complete_cannot_bypass_missing_or_failed_verification(self) -> None:
        for test_status in ["not_run", "failed"]:
            with self.subTest(test_status=test_status), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                _seed(root, _verdict("complete", message=None))
                start_run(root, Path("agent/context-packs/T-018-test.md"), run_id="run-001")

                result = resume_run(
                    root,
                    "run-001",
                    executor_output="Done. Acceptance criteria are met.",
                    test_status=test_status,
                    reviewer_mode="model",
                )

                review = result["review"]
                self.assertEqual(review["decision"], "pause_for_human")
                self.assertTrue(review["requires_human"])
                self.assertIn("verification has not passed", review["reason"])
                self.assertEqual(result["state"]["status"], "paused")

    def test_cli_resume_accepts_model_reviewer_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed(root, _verdict("auto_continue", message="Continue from the static reviewer."))
            self.assertEqual(
                main(["--root", str(root), "run", "start", "agent/context-packs/T-018-test.md", "--run-id", "run-001"]),
                0,
            )

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "resume",
                        "run-001",
                        "--reviewer",
                        "model",
                        "--executor-output",
                        "Should I continue this implementation?",
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn("auto_continue", output.getvalue())
            self.assertIn("Continue from the static reviewer.", output.getvalue())

    def test_codex_config_source_can_supply_litellm_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            home = Path(td)
            (home / ".codex").mkdir()
            (home / ".codex" / "config.toml").write_text(
                """
model_provider = "oca"

[model_providers.oca]
base_url = "https://example.test/20250206/app/litellm"
""",
                encoding="utf-8",
            )

            with mock.patch("agentspec.model_review.Path.home", return_value=home):
                settings = _resolve_chat_settings(
                    {
                        "adapter": "codex",
                        "config_source": "codex-config",
                        "model": "oca/gpt-5.4",
                    }
                )

            self.assertEqual(settings["model"], "oca/gpt-5.4")
            self.assertEqual(settings["base_url"], "https://example.test/20250206/app/litellm")


def _seed(root: Path, reviewer_response: str | None) -> None:
    (root / ".agentspec").mkdir(parents=True)
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "agent" / "runs").mkdir(parents=True)
    (root / "agent" / "context-packs" / "T-018-test.md").write_text(PACK, encoding="utf-8")

    profile = {
        "adapter": "static",
        "model": "static-reviewer",
    }
    if reviewer_response is not None:
        profile["response"] = reviewer_response

    (root / ".agentspec" / "config.yml").write_text(
        json.dumps(
            {
                "version": 1,
                "agent_profiles": {
                    "main_executor": {"adapter": "current-host", "model": "host-default"},
                    "continuation_reviewer": profile,
                    "quality_reviewer": {"adapter": "static", "model": "static-quality"},
                },
                "supervised_runs": {
                    "executor_profile": "main_executor",
                    "continuation_reviewer_profile": "continuation_reviewer",
                    "quality_reviewer_profile": "quality_reviewer",
                    "reviewer_mode": "deterministic",
                    "max_iterations": {"implementation": 3},
                },
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
