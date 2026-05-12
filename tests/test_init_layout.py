"""Tests that `agentspec init` scaffolds the docs/change-requests/ artifact.

Covers R-121 (DCR-0002).
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

from agentspec.init import init_project
from agentspec.io import load_data


def _git_check_ignore(root: Path, path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", path],
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


class InitLayoutTests(unittest.TestCase):
    def test_init_creates_change_requests_directory_with_readme(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)

            cr_dir = root / "docs" / "change-requests"
            self.assertTrue(cr_dir.is_dir(), f"missing {cr_dir}")

            readme = cr_dir / "README.md"
            self.assertTrue(readme.exists(), f"missing {readme}")

            text = readme.read_text(encoding="utf-8")
            self.assertIn("Design Change Request", text)

    def test_init_creates_agent_model_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)

            config = load_data(root / ".agentspec" / "config.yml")

            self.assertEqual(config["agent_profiles"]["main_executor"]["adapter"], "current-host")
            self.assertEqual(config["agent_profiles"]["main_executor"]["model"], "host-default")
            self.assertIn("test_eval_reviewer", config["agent_profiles"])
            self.assertEqual(config["supervised_runs"]["executor_profile"], "main_executor")
            self.assertEqual(config["supervised_runs"]["quality_reviewer_profile"], "test_eval_reviewer")

    def test_init_creates_app_build_planner_evaluator_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)

            workflow = root / "agent" / "workflows" / "app-build.md"
            planner = root / "agent" / "roles" / "app-planner.md"
            evaluator = root / "agent" / "roles" / "app-evaluator.md"
            quality_gc = root / "agent" / "roles" / "quality-gc-reviewer.md"

            self.assertTrue(workflow.exists())
            self.assertTrue(planner.exists())
            self.assertTrue(evaluator.exists())
            self.assertTrue(quality_gc.exists())
            workflow_text = workflow.read_text(encoding="utf-8")
            self.assertIn("Planner", workflow_text)
            self.assertIn("Generator", workflow_text)
            self.assertIn("Evaluator", workflow_text)
            self.assertIn("external code agent", workflow_text)
            self.assertIn("screenshots", workflow_text)
            self.assertIn("DOM snapshots", workflow_text)

    def test_init_creates_dogfood_directory(self) -> None:
        """R-139: reports/dogfood/ exists in the artifact layout after init."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            self.assertTrue((root / "reports" / "dogfood").is_dir())
            self.assertTrue((root / "reports" / "dogfood" / ".gitkeep").exists())
            self.assertTrue((root / "reports" / "quality").is_dir())
            self.assertTrue((root / "reports" / "quality" / ".gitkeep").exists())

    def test_init_creates_gitignore_with_runs_block(self) -> None:
        """R-140: fresh init writes a .gitignore that ignores runtime state.

        Dogfood notes (R-139) are durable artifacts so the block must
        carry an explicit `!reports/dogfood/*.md` exception.
        """
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            gitignore = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("agent/runs/*", gitignore)
            self.assertIn("!agent/runs/.gitkeep", gitignore)
            self.assertIn("!agent/runs/*/summary.yml", gitignore)
            self.assertIn("agent/sessions/active/*", gitignore)
            self.assertIn("!agent/sessions/active/.gitkeep", gitignore)
            self.assertIn("agent/sessions/archived/*", gitignore)
            self.assertIn("!agent/sessions/archived/.gitkeep", gitignore)
            self.assertIn("reports/", gitignore)
            self.assertIn(".agentspec/cache", gitignore)
            self.assertIn("!reports/dogfood/*.md", gitignore)
            self.assertIn("!reports/quality/latest.yml", gitignore)
            self.assertIn("!reports/quality/latest.md", gitignore)

    def test_init_gitignore_ignores_session_lease_files(self) -> None:
        """Issue #30: session lease records are generated runtime state."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            subprocess.run(
                ["git", "init"],
                cwd=root,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            self.assertTrue(_git_check_ignore(root, "agent/sessions/active/S-test.yml"))
            self.assertTrue(_git_check_ignore(root, "agent/sessions/archived/S-test.yml"))
            self.assertFalse(_git_check_ignore(root, "agent/sessions/active/.gitkeep"))
            self.assertFalse(_git_check_ignore(root, "agent/sessions/archived/.gitkeep"))

    def test_init_appends_to_existing_gitignore_idempotently(self) -> None:
        """R-140: init must not duplicate the AgentSpec block on re-run, and
        must append it if a .gitignore already exists without it."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            # Pre-existing .gitignore with unrelated content.
            (root / ".gitignore").write_text("# project-local\n*.log\n", encoding="utf-8")

            init_project(root)
            first_pass = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertIn("*.log", first_pass)
            self.assertIn("agent/runs/*", first_pass)

            # Second init must not re-append the AgentSpec block.
            init_project(root)
            second_pass = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(first_pass, second_pass)

    def test_init_updates_existing_agentspec_gitignore_block(self) -> None:
        """Existing AgentSpec blocks should receive newly added ignore rules."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old_block = """# === AgentSpec ===
# Runtime cache + locks (.agentspec/config.yml is committed; cache is not).
.agentspec/cache/
.agentspec/locks/
# Supervised-run state (per ADR-0003 / Q-014). Keep .gitkeep markers.
agent/runs/*
!agent/runs/.gitkeep
# ADR-0004 committed projection: keep run dirs visible, ignore raw state,
# but track per-run summaries.
!agent/runs/*/
agent/runs/*/*
!agent/runs/*/summary.yml
# Generated reports — regenerable via doctor / compile / drift.
reports/*/*
!reports/*/.gitkeep
# Dogfood notes (R-139) are durable artifacts; keep them tracked.
!reports/dogfood/*.md
# Latest quality grade is durable agent-facing state.
!reports/quality/latest.yml
!reports/quality/latest.md
# === /AgentSpec ===
"""
            (root / ".gitignore").write_text("# project-local\n*.log\n\n" + old_block, encoding="utf-8")

            init_project(root)

            updated = (root / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(updated.count("# === AgentSpec ==="), 1)
            self.assertIn("*.log", updated)
            self.assertIn("agent/sessions/active/*", updated)
            self.assertIn("!agent/sessions/active/.gitkeep", updated)
            self.assertIn("agent/sessions/archived/*", updated)
            self.assertIn("!agent/sessions/archived/.gitkeep", updated)


if __name__ == "__main__":
    unittest.main()
