"""Tests that `agentspec init` scaffolds the docs/change-requests/ artifact.

Covers R-121 (DCR-0002).
"""

import tempfile
import unittest
from pathlib import Path

from agentspec.init import init_project
from agentspec.io import load_data


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
            self.assertEqual(config["supervised_runs"]["executor_profile"], "main_executor")

    def test_init_creates_dogfood_directory(self) -> None:
        """R-139: reports/dogfood/ exists in the artifact layout after init."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            self.assertTrue((root / "reports" / "dogfood").is_dir())
            self.assertTrue((root / "reports" / "dogfood" / ".gitkeep").exists())

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
            self.assertIn("reports/", gitignore)
            self.assertIn(".agentspec/cache", gitignore)
            self.assertIn("!reports/dogfood/*.md", gitignore)

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


if __name__ == "__main__":
    unittest.main()
