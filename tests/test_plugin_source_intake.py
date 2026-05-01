import json
import tempfile
import unittest
from pathlib import Path

from agentspec.emit import emit_targets


REPO_ROOT = Path(__file__).resolve().parent.parent


class PluginSourceIntakeTests(unittest.TestCase):
    def test_codex_plugin_manual_source_intake_skill_is_cli_backed(self) -> None:
        plugin_root = REPO_ROOT / "agentspec-codex-plugin"
        manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        skill_path = plugin_root / "skills" / "manual-source-intake" / "SKILL.md"
        status_skill_path = plugin_root / "skills" / "project-status" / "SKILL.md"

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        skill = skill_path.read_text(encoding="utf-8")
        status_skill = status_skill_path.read_text(encoding="utf-8")

        self.assertEqual(manifest["name"], "agentspec-codex-plugin")
        self.assertIn("AgentSpec", manifest["interface"]["displayName"])
        for skill_name in [
            "compile-spec",
            "continue-work",
            "create-task",
            "drift-review",
            "init-project",
            "manual-source-intake",
            "project-status",
        ]:
            self.assertTrue((plugin_root / "skills" / skill_name / "SKILL.md").exists())
        self.assertIn("Initialize AgentSpec", manifest["description"])
        self.assertIn("Continue AgentSpec work", manifest["interface"]["defaultPrompt"])
        self.assertIn("aspec intake import", skill)
        self.assertIn("--as-candidate", skill)
        self.assertIn("aspec intake diff", skill)
        self.assertIn("aspec intake promote", skill)
        self.assertIn("host-provided", skill)
        self.assertIn("does not fetch Confluence or Jira", skill)
        self.assertIn("Do not auto-promote", skill)
        self.assertIn("aspec status", status_skill)
        self.assertIn("aspec task next", status_skill)

    def test_codex_plugin_readme_explains_cli_and_plugin_paths(self) -> None:
        readme = (REPO_ROOT / "agentspec-codex-plugin" / "README.md").read_text(
            encoding="utf-8"
        )

        for text in [
            "CLI path",
            "Plugin path",
            "Initialize a repository",
            "Continue work in a repository",
            "aspec --root \"$TARGET\" init",
            "agentspec-codex-plugin:init-project",
            "aspec status",
            "agentspec-codex-plugin:continue-work",
        ]:
            self.assertIn(text, readme)

    def test_init_and_continue_skills_are_cli_backed(self) -> None:
        plugin_root = REPO_ROOT / "agentspec-codex-plugin"
        init_skill = (plugin_root / "skills" / "init-project" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        continue_skill = (
            plugin_root / "skills" / "continue-work" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for text in [
            "new repository",
            "existing repository",
            "aspec --root \"$TARGET\" init",
            "aspec --root \"$TARGET\" emit --target claude,codex",
            "aspec --root \"$TARGET\" status",
        ]:
            self.assertIn(text, init_skill)
        for text in [
            "continue work",
            "aspec status --json",
            "aspec task next",
            "aspec run loop",
            "Do not bypass the task context pack",
        ]:
            self.assertIn(text, continue_skill)

    def test_emit_codex_includes_manual_source_intake_skill(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            written = emit_targets(root, "codex")
            skill_path = root / ".agents" / "skills" / "agentspec-source-intake" / "SKILL.md"

            self.assertIn(skill_path, written)
            skill = skill_path.read_text(encoding="utf-8")
            self.assertIn("aspec intake import", skill)
            self.assertIn("aspec intake diff", skill)
            self.assertIn("aspec intake promote", skill)
            self.assertIn("host-provided", skill)
            self.assertIn("Do not auto-promote", skill)


if __name__ == "__main__":
    unittest.main()
