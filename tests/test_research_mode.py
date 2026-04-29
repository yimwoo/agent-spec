"""Tests for R-142: research-mode fallback in autonomous runs."""

import json
import tempfile
import unittest
from pathlib import Path

from agentspec.init import init_project
from agentspec.io import load_data
from agentspec.run import (
    MAX_RESEARCH_FINDINGS_DEFAULT,
    RESEARCH_ALLOWED_PATHS,
    RESEARCH_CONTEXT_PACK_SENTINEL,
    loop_run,
    resume_run,
    start_research_run,
)


def _seed_workspace(root: Path) -> None:
    init_project(root)


class StartResearchRunTests(unittest.TestCase):
    def test_creates_state_with_research_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            state = start_research_run(root, run_id="r-research-1")

            self.assertEqual(state["mode"], "research")
            self.assertEqual(state["context_pack"], RESEARCH_CONTEXT_PACK_SENTINEL)
            # Allowed paths are exactly the research findings dirs.
            self.assertEqual(set(state["allowed_paths"]), set(RESEARCH_ALLOWED_PATHS))
            self.assertEqual(state["research_findings_produced"], 0)
            self.assertEqual(
                state["max_research_findings"],
                MAX_RESEARCH_FINDINGS_DEFAULT,
            )

            summary = load_data(root / "agent" / "runs" / "r-research-1" / "summary.yml")
            self.assertEqual(summary["schema"], "agentspec.supervised_run.summary.v0")
            self.assertEqual(summary["mode"], "research")
            self.assertEqual(summary["status"], "started")
            self.assertEqual(summary["event_counts"]["research_run_started"], 1)

    def test_max_research_findings_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            state = start_research_run(root, run_id="r-research-2", max_research_findings=2)
            self.assertEqual(state["max_research_findings"], 2)


class ResearchPolicyEnforcementTests(unittest.TestCase):
    def test_writes_outside_findings_dirs_halt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-outside")

            result = resume_run(
                root,
                "r-outside",
                executor_output="Looked at agentspec/cli.py and edited it.",
                touched_paths=["agentspec/cli.py"],  # forbidden in research
                test_status="not_run",
            )
            state = result["state"]
            self.assertEqual(state["status"], "halted")
            review = result["review"]
            self.assertIn("forbidden_path", review.get("policy_flags", []))

    def test_writes_inside_findings_dirs_count_toward_cap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-inside", max_research_findings=3)

            result = resume_run(
                root,
                "r-inside",
                executor_output="Logged a finding.",
                touched_paths=["reports/dogfood/2026-04-28-something.md"],
                test_status="not_run",
            )
            state = result["state"]
            # Allowed write — counter incremented.
            self.assertEqual(state.get("research_findings_produced"), 1)

    def test_terminates_at_max_research_findings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-cap", max_research_findings=2)

            resume_run(
                root, "r-cap",
                executor_output="finding 1",
                touched_paths=["reports/dogfood/2026-04-28-a.md"],
                test_status="not_run",
            )
            result = resume_run(
                root, "r-cap",
                executor_output="finding 2",
                touched_paths=["reports/dogfood/2026-04-28-b.md"],
                test_status="not_run",
            )
            state = result["state"]
            # At cap → halt with the structured flag.
            self.assertEqual(state["status"], "halted")
            self.assertIn(
                "research_findings_cap",
                result["review"].get("policy_flags", []),
            )


class ResearchHardLimitsTests(unittest.TestCase):
    """ADR-0004 hard limits also fire in research mode."""

    def test_destructive_git_halts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-git")

            result = resume_run(
                root, "r-git",
                executor_output="ran git push --force origin main",
                touched_paths=[],
                test_status="not_run",
            )
            state = result["state"]
            self.assertEqual(state["status"], "halted")
            self.assertIn("destructive_git", result["review"].get("policy_flags", []))

    def test_acceptance_attempt_halts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-accept")

            result = resume_run(
                root, "r-accept",
                executor_output="now I'll run aspec requirement accept R-200",
                touched_paths=[],
                test_status="not_run",
            )
            state = result["state"]
            self.assertEqual(state["status"], "halted")
            self.assertIn("auto_acceptance", result["review"].get("policy_flags", []))


class LoopAutonomousFallbackTests(unittest.TestCase):
    def test_loop_autonomous_with_empty_queue_enters_research_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            # No context packs added → task_next returns nothing.

            result = loop_run(root, mode="autonomous", run_id="r-loop-research")
            state = result["state"]
            self.assertTrue(result["started"])
            self.assertEqual(state["mode"], "research")
            self.assertEqual(state["context_pack"], RESEARCH_CONTEXT_PACK_SENTINEL)


if __name__ == "__main__":
    unittest.main()
