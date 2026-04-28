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


if __name__ == "__main__":
    unittest.main()
