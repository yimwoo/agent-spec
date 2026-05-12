"""Tests for R-143: severity gating in autonomous mode.

Severity classification rules live in `agentspec.model_review.classify_severity`.
The autonomous transform in `agentspec.run` branches on severity.
"""

import json
import tempfile
import unittest
from pathlib import Path

from agentspec.init import init_project
from agentspec.io import load_data
from agentspec.run import resume_run, start_run


def _seed_workspace(root: Path) -> Path:
    init_project(root)
    pack_dir = root / "agent" / "context-packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack = pack_dir / "T-998-fixture.md"
    (root / "agentspec").mkdir(exist_ok=True)
    (root / "agentspec" / "fixture_target.py").write_text("", encoding="utf-8")
    pack.write_text(
        "# T-998: Fixture\n\nType: `implementation`\n\n"
        "## Allowed Paths\n\n- `agentspec/fixture_target.py`\n",
        encoding="utf-8",
    )
    return pack


class ClassifySeverityTests(unittest.TestCase):
    """The deterministic rule layer from ADR-0005 / R-143."""

    def test_high_security_keywords(self) -> None:
        from agentspec.model_review import classify_severity
        self.assertEqual(classify_severity("Should I add this API key to .env?"), "high")
        self.assertEqual(classify_severity("Need credentials for the deploy step."), "high")
        self.assertEqual(classify_severity("Want me to skip the auth check?"), "high")

    def test_high_architecture_keywords(self) -> None:
        from agentspec.model_review import classify_severity
        self.assertEqual(classify_severity("Should we change the architecture here?"), "high")
        self.assertEqual(classify_severity("Modify ADR-0003 to allow this?"), "high")
        self.assertEqual(classify_severity("Expand scope to include the new module?"), "high")

    def test_high_destructive_keywords(self) -> None:
        from agentspec.model_review import classify_severity
        self.assertEqual(classify_severity("Should I force-push the rebased branch?"), "high")
        self.assertEqual(classify_severity("Drop the old table?"), "high")

    def test_minor_naming_keywords(self) -> None:
        from agentspec.model_review import classify_severity
        self.assertEqual(classify_severity("What name should this helper have?"), "minor")
        self.assertEqual(classify_severity("Pick a style: tabs or spaces?"), "minor")

    def test_minor_default_keywords(self) -> None:
        from agentspec.model_review import classify_severity
        self.assertEqual(classify_severity("What default value should I use here?"), "minor")
        self.assertEqual(classify_severity("Either way works — which do you prefer?"), "minor")

    def test_high_wins_when_both_match(self) -> None:
        """A pause that mentions naming AND security must be classified high."""
        from agentspec.model_review import classify_severity
        self.assertEqual(
            classify_severity("What should I name this credential helper?"),
            "high",
        )

    def test_returns_none_when_no_match(self) -> None:
        """Unrecognized phrasing returns None so the autonomous transform can
        fall back to the conservative T-028 path (open-question + halt)."""
        from agentspec.model_review import classify_severity
        self.assertIsNone(
            classify_severity("Status update: drafted three approaches yesterday."),
        )


class AutonomousMinorPauseTests(unittest.TestCase):
    def test_minor_pause_logs_open_question_and_auto_continues(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-minor", mode="autonomous")

            result = resume_run(
                root,
                "r-minor",
                executor_output="What name should I give this helper function?",
                touched_paths=[],
                test_status="not_run",
            )
            state = result["state"]

            # Did NOT halt.
            self.assertNotEqual(state["status"], "halted")
            # Decision was demoted to auto_continue.
            self.assertEqual(state["last_decision"], "auto_continue")
            # An open-question entry exists for this run.
            qs = load_data(root / "docs" / "discovery" / "open-questions.yml", []) or []
            entries = [q for q in qs if q.get("raised_by") == "r-minor"]
            self.assertEqual(len(entries), 1, f"expected one finding, got: {entries}")
            self.assertEqual(entries[0].get("severity"), "minor")


class AutonomousHighPauseTests(unittest.TestCase):
    def test_high_pause_drafts_dcr_stub_and_halts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-high", mode="autonomous")

            result = resume_run(
                root,
                "r-high",
                executor_output="Should we expand scope and modify ADR-0003 to allow this?",
                touched_paths=[],
                test_status="not_run",
            )
            state = result["state"]

            # Halted.
            self.assertEqual(state["status"], "halted")
            # State carries the new DCR id.
            self.assertIn("autonomous_dcr", state)
            dcr_id = state["autonomous_dcr"]
            # DCR file exists with the expected classification.
            from agentspec.dcr import find_dcr_by_id, parse_dcr
            dcr_path = find_dcr_by_id(root, dcr_id)
            self.assertIsNotNone(dcr_path, f"missing DCR file for {dcr_id}")
            dcr = parse_dcr(dcr_path)
            self.assertEqual(dcr["classification"], "needs-adr")
            self.assertEqual(dcr["status"], "classified")

    def test_high_pause_halt_remains_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-high-terminal", mode="autonomous")

            resume_run(
                root,
                "r-high-terminal",
                executor_output="Should we expand scope and modify ADR-0003 to allow this?",
                touched_paths=[],
                test_status="not_run",
            )

            with self.assertRaisesRegex(ValueError, "already halted"):
                resume_run(
                    root,
                    "r-high-terminal",
                    executor_output="Done. Acceptance criteria are covered and verification passed.",
                    touched_paths=["agentspec/fixture_target.py"],
                    test_status="passed",
                )


class AutonomousUnclassifiedFallbackTests(unittest.TestCase):
    def test_unclassified_pause_keeps_existing_t028_behavior(self) -> None:
        """Severity=None: open-question + halt (the T-028 path)."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-unclass", mode="autonomous")

            # An executor output that triggers pause_for_human in review.py
            # but matches neither HIGH nor MINOR keyword sets.
            result = resume_run(
                root,
                "r-unclass",
                executor_output="Want me to proceed with this approach, or pick another?",
                touched_paths=[],
                test_status="not_run",
            )
            state = result["state"]

            self.assertEqual(state["status"], "halted")
            # Existing T-028 path uses autonomous_finding (open-question).
            self.assertIn("autonomous_finding", state)
            self.assertNotIn("autonomous_dcr", state)


if __name__ == "__main__":
    unittest.main()
