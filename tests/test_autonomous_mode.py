"""Tests for basic autonomous execution mode.

Covers R-135 (DCR-0019 / ADR-0004).
"""

import contextlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import main
from agentspec.init import init_project
from agentspec.io import load_data
from agentspec.policy import evaluate_policy
from agentspec.run import start_run, resume_run


@contextlib.contextmanager
def pushd(path: Path):
    old = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old)


def _seed_workspace(root: Path, *, eligible_pack: bool = True) -> Path:
    """Init a workspace and write a context pack for testing.

    `eligible_pack=True` produces a pack with at least one confirmed path
    (autonomous-eligible). `eligible_pack=False` produces a pack with
    only inferred paths (refused in autonomous).
    """
    init_project(root)
    pack_dir = root / "agent" / "context-packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack = pack_dir / "T-999-fixture.md"
    if eligible_pack:
        # Create a real source file so the path is `confirmed`.
        (root / "agentspec").mkdir(exist_ok=True)
        (root / "agentspec" / "fixture_target.py").write_text("", encoding="utf-8")
        body = (
            "# T-999: Fixture\n\nType: `implementation`\n\n"
            "## Allowed Paths\n\n- `agentspec/fixture_target.py`\n"
        )
    else:
        body = (
            "# T-999: Fixture (all inferred)\n\nType: `implementation`\n\n"
            "## Allowed Paths\n\n- `agentspec/missing_target.py`\n"
        )
    pack.write_text(body, encoding="utf-8")
    return pack


class StartRunModeTests(unittest.TestCase):
    def test_run_start_default_mode_is_supervised(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            state = start_run(root, pack, run_id="r-default")
            self.assertEqual(state.get("mode"), "supervised")

    def test_run_start_accepts_mode_autonomous(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            state = start_run(root, pack, run_id="r-auto", mode="autonomous")
            self.assertEqual(state.get("mode"), "autonomous")

            summary = load_data(root / "agent" / "runs" / "r-auto" / "summary.yml")
            self.assertEqual(summary["schema"], "agentspec.supervised_run.summary.v0")
            self.assertEqual(summary["mode"], "autonomous")
            self.assertEqual(summary["status"], "started")
            self.assertFalse(summary["terminal"])
            self.assertEqual(summary["event_counts"]["run_started"], 1)

    def test_run_start_autonomous_refuses_all_inferred_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root, eligible_pack=False)
            with self.assertRaises(ValueError) as ctx:
                start_run(root, pack, run_id="r-inferred", mode="autonomous")
            self.assertIn("inferred", str(ctx.exception).lower())

    def test_run_start_supervised_allows_all_inferred_pack(self) -> None:
        """Regression guard: supervised mode does not require eligibility."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root, eligible_pack=False)
            state = start_run(root, pack, run_id="r-inf-sup")  # default supervised
            self.assertEqual(state.get("mode"), "supervised")


class AutonomousPauseTransformTests(unittest.TestCase):
    def test_autonomous_pause_for_human_creates_blocked_finding_and_halts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-pause-auto", mode="autonomous")

            # Executor output that triggers pause_for_human (asks the human).
            result = resume_run(
                root,
                "r-pause-auto",
                executor_output="Want me to proceed with this approach, or pick another?",
                touched_paths=[],
                test_status="not_run",
            )

            state = result["state"]
            # In autonomous mode the pause is transformed into a halt.
            self.assertEqual(state["status"], "halted")
            self.assertIn("autonomous_finding", state)

            # A finding was written to open-questions.yml.
            qs = load_data(root / "docs" / "discovery" / "open-questions.yml", []) or []
            self.assertTrue(
                any(q.get("raised_by") == "r-pause-auto" for q in qs),
                f"no finding tagged with raised_by=r-pause-auto: {qs}",
            )

            summary = load_data(root / "agent" / "runs" / "r-pause-auto" / "summary.yml")
            self.assertEqual(summary["status"], "halted")
            self.assertTrue(summary["terminal"])
            self.assertEqual(summary["last_decision"], "pause_for_human")
            self.assertEqual(summary["verdict_counts"]["pause_for_human"], 1)
            self.assertEqual(summary["blocked_findings"][0]["id"], state["autonomous_finding"])
            self.assertEqual(summary["blocked_findings"][0]["kind"], "open-question")

    def test_supervised_pause_for_human_unchanged(self) -> None:
        """Regression guard: supervised mode produces the existing pause status,
        no finding written, no halt override."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_workspace(root)
            start_run(root, pack, run_id="r-pause-sup")

            result = resume_run(
                root,
                "r-pause-sup",
                executor_output="Want me to proceed with this approach, or pick another?",
                touched_paths=[],
                test_status="not_run",
            )

            state = result["state"]
            self.assertNotEqual(state["status"], "halted")
            self.assertNotIn("autonomous_finding", state)

            qs = load_data(root / "docs" / "discovery" / "open-questions.yml", []) or []
            self.assertFalse(
                any(q.get("raised_by") == "r-pause-sup" for q in qs),
                "supervised mode must not write open-questions findings",
            )


class AutonomousHardLimitTests(unittest.TestCase):
    """Each test checks evaluate_policy returns a halt verdict with the right
    flag when autonomous mode receives an executor_output that violates an
    ADR-0004 hard limit."""

    def test_autonomous_halts_on_destructive_git(self) -> None:
        verdict = evaluate_policy(
            allowed_paths=["**"], touched_paths=[], iteration=1, max_iterations=3,
            executor_output="ran git push --force origin main",
            mode="autonomous",
        )
        self.assertEqual(verdict.decision, "halt")
        self.assertIn("destructive_git", verdict.flags)

    def test_autonomous_halts_on_remote_push(self) -> None:
        verdict = evaluate_policy(
            allowed_paths=["**"], touched_paths=[], iteration=1, max_iterations=3,
            executor_output="finishing up: $ git push origin feature/x",
            mode="autonomous",
        )
        self.assertEqual(verdict.decision, "halt")
        self.assertIn("remote_push", verdict.flags)

    def test_autonomous_halts_on_credential_pattern(self) -> None:
        verdict = evaluate_policy(
            allowed_paths=["**"], touched_paths=[], iteration=1, max_iterations=3,
            executor_output="export OPENAI_API_KEY=sk-proj-AbCdEf123456789012345678",
            mode="autonomous",
        )
        self.assertEqual(verdict.decision, "halt")
        self.assertIn("credential_pattern", verdict.flags)

    def test_autonomous_halts_on_acceptance_attempt(self) -> None:
        verdict = evaluate_policy(
            allowed_paths=["**"], touched_paths=[], iteration=1, max_iterations=3,
            executor_output="now I'll run aspec requirement accept R-200",
            mode="autonomous",
        )
        self.assertEqual(verdict.decision, "halt")
        self.assertIn("auto_acceptance", verdict.flags)

    def test_supervised_mode_unaffected_by_content_gates(self) -> None:
        """Regression guard: supervised mode does not trigger content-based halts.
        The host human still reviews; the gates are autonomous-mode safety nets."""
        verdict = evaluate_policy(
            allowed_paths=["**"], touched_paths=[], iteration=1, max_iterations=3,
            executor_output="ran git push --force origin main",
            mode="supervised",
        )
        self.assertEqual(verdict.decision, "allow")


class AutonomousModeConfigTests(unittest.TestCase):
    def test_init_writes_autonomous_mode_config_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            config = load_data(root / ".agentspec" / "config.yml")
            self.assertIn("autonomous_mode", config)
            self.assertIs(config["autonomous_mode"]["allow_remote_push"], False)
            self.assertEqual(config["autonomous_mode"]["max_consecutive_blocks"], 3)


if __name__ == "__main__":
    unittest.main()
