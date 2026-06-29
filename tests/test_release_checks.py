import json
import tomllib
import unittest
from pathlib import Path

import agentspec


ROOT = Path(__file__).resolve().parents[1]


class ReleaseChecksTests(unittest.TestCase):
    def test_version_metadata_is_synchronized(self) -> None:
        version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]

        self.assertEqual(version, "0.1.42")
        self.assertEqual(agentspec.__version__, version)
        for path in [
            ROOT / "agentspec-codex-plugin" / ".codex-plugin" / "plugin.json",
            ROOT / "agentspec-claude-plugin" / ".claude-plugin" / "plugin.json",
        ]:
            plugin = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(plugin["version"], version)

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(f"@v{version}", readme)

    def test_release_workflow_checks_tag_build_assets_and_publication(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")

        self.assertIn("release:", workflow)
        self.assertIn("types: [published]", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("RELEASE_TAG", workflow)
        self.assertIn('tomllib.load(open("pyproject.toml", "rb"))', workflow)
        self.assertRegex(workflow, r"git rev-parse .+RELEASE_TAG")
        self.assertIn("python -m pytest -q", workflow)
        self.assertIn("python -m compileall", workflow)
        self.assertIn("python -m mypy", workflow)
        self.assertIn("python -m pylint agentspec", workflow)
        self.assertNotIn("agentspec/evidence.py \\", workflow)
        self.assertIn("python -m build", workflow)
        self.assertIn("dist/agentspec-${VERSION}.tar.gz", workflow)
        self.assertIn("dist/agentspec-${VERSION}-py3-none-any.whl", workflow)
        self.assertIn("python -m twine check", workflow)
        self.assertIn("PASSING_PUBLIC_REVIEW_VERDICTS", workflow)
        self.assertIn('"docs/release/**"', workflow)
        self.assertIn("gh release view", workflow)
        self.assertIn("if: env.RELEASE_TAG != ''", workflow)
        self.assertIn("if: github.event_name == 'release' || github.event_name == 'workflow_dispatch'", workflow)
        self.assertIn("agentspec-codex-plugin", workflow)
        self.assertIn("agentspec-claude-plugin", workflow)
        self.assertIn("plugin.json", workflow)
        self.assertIn("load_task_evidence", workflow)
        self.assertIn('- "install.sh"', workflow)

    def test_default_mypy_scope_covers_the_package(self) -> None:
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(config["tool"]["mypy"]["files"], ["agentspec"])

    def test_codex_installer_pins_stable_source_and_checks_cli_compatibility(self) -> None:
        version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn(f'DEFAULT_SOURCE_REF="v{version}"', installer)
        self.assertIn("--ref", installer)
        self.assertIn("verify_cli_plugin_compatibility", installer)
        self.assertIn("--allow-version-mismatch", installer)
        self.assertIn(f"defaults to the release-pinned plugin `v{version}`", readme)


if __name__ == "__main__":
    unittest.main()
