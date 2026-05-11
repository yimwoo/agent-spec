import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from agentspec.emit import EMITTED_CLAUDE_SKILLS, emit_targets


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

        self.assertEqual(manifest["name"], "aspec")
        self.assertEqual(manifest["interface"]["displayName"], "aspec")
        for skill_name in [
            "brainstorm",
            "compile-spec",
            "continue-work",
            "create-task",
            "delegate-work",
            "design-work",
            "drift-review",
            "execute-workflow",
            "finish-branch",
            "finish-work",
            "handoff-recovery",
            "init-project",
            "manual-source-intake",
            "outcome-audit",
            "plan-workflow",
            "project-status",
            "review-code",
            "start-branch",
            "verify-work",
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
            "aspec:init-project",
            "aspec status",
            "aspec:continue-work",
        ]:
            self.assertIn(text, readme)
        self.assertNotIn("agentspec-codex-plugin:", readme)

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
            "readiness is below 60",
            "discovery, spike, or scaffold",
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

    def test_emit_codex_uses_plugin_skills_instead_of_project_local_skills(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            written = emit_targets(root, "codex")

            self.assertIn(root / ".codex" / "agents" / "spec-reviewer.toml", written)
            for role in ["spec-reviewer", "security-reviewer", "brownfield-mapper"]:
                role_path = root / ".codex" / "agents" / f"{role}.toml"
                role_text = role_path.read_text(encoding="utf-8")
                role_config = tomllib.loads(role_text)

                self.assertIn("\ndeveloper_instructions =", role_text)
                self.assertIn("developer_instructions", role_config)
                self.assertIn("aspec lifecycle --json", role_config["developer_instructions"])
                self.assertIn("aspec:execute-workflow", role_config["developer_instructions"])
                self.assertIn("Do not create project-local Codex skill state", role_config["developer_instructions"])
                self.assertNotIn("instructions", role_config)
            self.assertFalse(
                list((root / ".agents" / "skills").glob("agentspec-*/SKILL.md"))
            )
            self.assertFalse(list((root / ".codex" / "skills").glob("*/SKILL.md")))

    def test_emit_claude_generates_lifecycle_aligned_project_skills(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            written = emit_targets(root, "claude")
            skill_names = [skill["name"] for skill in EMITTED_CLAUDE_SKILLS]

            self.assertIn("agentspec-lifecycle", skill_names)
            self.assertIn("agentspec-execute-workflow", skill_names)
            self.assertIn("agentspec-handoff-recovery", skill_names)
            for skill_name in skill_names:
                skill_path = root / ".claude" / "skills" / skill_name / "SKILL.md"
                self.assertIn(skill_path, written)
                text = skill_path.read_text(encoding="utf-8")
                frontmatter = _frontmatter(text)

                self.assertEqual(frontmatter.get("name"), skill_name)
                self.assertIn("description", frontmatter)
                self.assertNotEqual(frontmatter["description"], "AgentSpec helper skill generated for this repository.")
                self.assertLessEqual(len(frontmatter["description"]), 1536)
                self.assertIn("## Commands", text)
                self.assertIn("Boundary:", text)
                self.assertNotIn("Run the matching AgentSpec CLI command", text)

            combined = "\n".join(
                (root / ".claude" / "skills" / skill_name / "SKILL.md").read_text(
                    encoding="utf-8"
                )
                for skill_name in skill_names
            )
            for command in [
                "aspec lifecycle --json",
                "aspec status --json",
                "aspec compile",
                "aspec intake import",
                "aspec plan",
                "aspec run loop",
                "aspec outcome --json",
                "aspec review code",
                "aspec finish",
                "aspec next-action",
                "aspec drift",
            ]:
                self.assertIn(command, combined)

    def test_repo_does_not_ship_project_local_agentspec_skills(self) -> None:
        local_skills = list((REPO_ROOT / ".agents" / "skills").glob("agentspec-*/SKILL.md"))

        self.assertEqual([], local_skills)

    def test_manual_source_intake_explains_ingest_baseline_source_key(self) -> None:
        plugin_root = REPO_ROOT / "agentspec-codex-plugin"
        skill = (
            plugin_root / "skills" / "manual-source-intake" / "SKILL.md"
        ).read_text(encoding="utf-8")

        for text in [
            "aspec ingest",
            "accepted source id",
            "SRC-0001",
            "source_key",
        ]:
            self.assertIn(text, skill)

    def test_codex_plugin_public_docs_use_short_aspec_prefix(self) -> None:
        plugin_root = REPO_ROOT / "agentspec-codex-plugin"
        docs = [
            plugin_root / "README.md",
            *sorted((plugin_root / "skills").glob("*/SKILL.md")),
        ]

        combined = "\n".join(path.read_text(encoding="utf-8") for path in docs)

        self.assertIn("aspec:init-project", combined)
        self.assertIn("aspec:continue-work", combined)
        self.assertIn("aspec:brainstorm", combined)
        self.assertIn("aspec:design-work", combined)
        self.assertIn("aspec:start-branch", combined)
        self.assertIn("aspec:execute-workflow", combined)
        self.assertIn("aspec:delegate-work", combined)
        self.assertIn("aspec:outcome-audit", combined)
        self.assertIn("aspec:plan-workflow", combined)
        self.assertIn("aspec:verify-work", combined)
        self.assertIn("aspec:review-code", combined)
        self.assertIn("aspec:finish-branch", combined)
        self.assertIn("aspec:finish-work", combined)
        self.assertIn("aspec:handoff-recovery", combined)
        self.assertNotIn("agentspec-codex-plugin:", combined)


def _frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return {}
    out: dict[str, str] = {}
    for line in lines[1:]:
        if line == "---":
            return out
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip()
    return out


if __name__ == "__main__":
    unittest.main()
