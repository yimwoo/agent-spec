"""Tests for R-144: dual-reviewer signoff in autonomous mode."""

import json
import tempfile
import unittest
from pathlib import Path

from agentspec.dcr import find_dcr_by_id
from agentspec.init import init_project
from agentspec.io import load_data, write_data
from agentspec.model_review import QUALITY_REVIEW_SCHEMA
from agentspec.run import resume_run, start_run


def _seed_workspace(root: Path) -> Path:
    init_project(root)
    pack_dir = root / "agent" / "context-packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack = pack_dir / "T-997-fixture.md"
    (root / "agentspec").mkdir(exist_ok=True)
    (root / "agentspec" / "fixture_target.py").write_text("", encoding="utf-8")
    pack.write_text(
        "# T-997: Fixture\n\nType: `implementation`\nHost Worktree Execution: `explicit`\n\n"
        "## Allowed Paths\n\n- `agentspec/fixture_target.py`\n",
        encoding="utf-8",
    )
    return pack


class QualityReviewerSignoffTests(unittest.TestCase):
    """The deterministic quality-reviewer signoff function."""

    def test_approves_with_acceptance_evidence(self) -> None:
        from agentspec.review import quality_reviewer_signoff
        decision, reason = quality_reviewer_signoff(
            "All acceptance criteria are met; tests pass.",
            test_status="passed",
        )
        self.assertEqual(decision, "approve")

    def test_rejects_when_test_status_not_passed(self) -> None:
        from agentspec.review import quality_reviewer_signoff
        decision, _ = quality_reviewer_signoff(
            "All acceptance criteria are met; tests pass.",
            test_status="not_run",
        )
        self.assertEqual(decision, "reject")

    def test_rejects_when_no_acceptance_language(self) -> None:
        from agentspec.review import quality_reviewer_signoff
        decision, reason = quality_reviewer_signoff(
            "Done.",
            test_status="passed",
        )
        self.assertEqual(decision, "reject")
        self.assertIn("acceptance", reason.lower())


class AutonomousCompleteDualSignoffTests(unittest.TestCase):
    def test_autonomous_complete_with_dual_signoff_proceeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-dual-pass", mode="autonomous")

            result = resume_run(
                root,
                "r-dual-pass",
                executor_output=(
                    "All acceptance criteria are met. Verification passed; tests are green."
                ),
                touched_paths=["agentspec/fixture_target.py"],
                test_status="passed",
            )
            state = result["state"]

            # Both reviewers approved → complete proceeds.
            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["last_decision"], "complete")
            self.assertNotIn("autonomous_dcr", state)

    def test_autonomous_complete_without_quality_signoff_degrades_to_dcr_stub(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-dual-fail", mode="autonomous")

            result = resume_run(
                root,
                "r-dual-fail",
                # Continuation reviewer accepts on "done" + passed; quality
                # rejects because no acceptance-criteria evidence.
                executor_output="Done.",
                touched_paths=["agentspec/fixture_target.py"],
                test_status="passed",
            )
            state = result["state"]

            # Quality reject → degraded to pause_for_human severity=high
            # → R-143 high path → DCR stub + halt.
            self.assertEqual(state["status"], "halted")
            self.assertIn("autonomous_dcr", state)
            dcr_id = state["autonomous_dcr"]
            self.assertIsNotNone(find_dcr_by_id(root, dcr_id))

    def test_autonomous_model_quality_signoff_uses_configured_test_eval_profile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            config_path = root / ".agentspec" / "config.yml"
            config = load_data(config_path)
            config["agent_profiles"]["test_eval_reviewer"] = {
                "adapter": "static",
                "model": "oca/gpt5.3-codex",
                "response": json.dumps(
                    {
                        "schema": QUALITY_REVIEW_SCHEMA,
                        "decision": "approve",
                        "confidence": "high",
                        "reason": "Evaluator model approved the UI evidence and tests.",
                    }
                ),
            }
            config["supervised_runs"]["quality_reviewer_profile"] = "test_eval_reviewer"
            write_data(config_path, config)
            start_run(root, pack, run_id="r-model-quality", mode="autonomous")

            result = resume_run(
                root,
                "r-model-quality",
                # Continuation accepts on "done" + passed; deterministic
                # quality would reject, so this proves the configured
                # test_eval_reviewer model profile is used.
                executor_output="Done.",
                touched_paths=["agentspec/fixture_target.py"],
                test_status="passed",
                reviewer_mode="model",
            )

            self.assertEqual(result["state"]["status"], "complete")
            events_path = root / "agent" / "runs" / "r-model-quality" / "events.jsonl"
            events = [
                json.loads(line)
                for line in events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            signoff = next(event for event in events if event["kind"] == "dual_signoff_check")
            self.assertEqual(signoff["quality_decision"], "approve")
            self.assertIn("Model quality reviewer", signoff["quality_reason"])

    def test_supervised_complete_unaffected_by_dual_signoff(self) -> None:
        """Regression guard: supervised mode does not invoke dual-signoff;
        an executor that says "Done." with passed tests still completes."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-sup-complete")  # default supervised

            result = resume_run(
                root,
                "r-sup-complete",
                executor_output="Done.",
                touched_paths=["agentspec/fixture_target.py"],
                test_status="passed",
            )
            state = result["state"]

            self.assertEqual(state["status"], "complete")
            self.assertNotIn("autonomous_dcr", state)


if __name__ == "__main__":
    unittest.main()
