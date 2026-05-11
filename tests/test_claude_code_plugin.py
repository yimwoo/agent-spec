import json
import shutil
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "agentspec-claude-plugin"
SKILL_NAMES = [
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
    "roadmap",
    "start-branch",
    "verify-work",
]


class ClaudeCodePluginTests(unittest.TestCase):
    def test_claude_plugin_manifest_and_skill_layout(self) -> None:
        manifest_path = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "aspec")
        self.assertEqual(manifest["version"], "0.1.5")
        self.assertIn("Claude Code", manifest["description"])
        self.assertIn("claude-code", manifest["keywords"])
        self.assertEqual(
            [manifest_path],
            sorted((PLUGIN_ROOT / ".claude-plugin").glob("*")),
        )

        for skill_name in SKILL_NAMES:
            self.assertTrue(
                (PLUGIN_ROOT / "skills" / skill_name / "SKILL.md").exists(),
                skill_name,
            )

    def test_claude_plugin_skills_have_discoverable_frontmatter(self) -> None:
        for skill_name in SKILL_NAMES:
            skill_path = PLUGIN_ROOT / "skills" / skill_name / "SKILL.md"
            text = skill_path.read_text(encoding="utf-8")
            frontmatter = _frontmatter(text)

            self.assertEqual(frontmatter.get("name"), skill_name)
            self.assertIn("description", frontmatter)
            self.assertLessEqual(len(frontmatter["description"]), 1536)
            self.assertIn(f"/aspec:{skill_name}", text)

    def test_claude_plugin_readme_documents_cli_and_plugin_paths(self) -> None:
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

        for text in [
            "claude plugin validate agentspec-claude-plugin",
            "claude --plugin-dir ./agentspec-claude-plugin",
            "/aspec:init-project",
            "/aspec:continue-work",
            "CLI path",
            "Plugin path",
            "aspec --root \"$TARGET\" init",
            "aspec status",
        ]:
            self.assertIn(text, readme)

    def test_claude_plugin_skills_are_cli_backed_thin_adapters(self) -> None:
        combined = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((PLUGIN_ROOT / "skills").glob("*/SKILL.md"))
        )
        readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
        normalized = " ".join((combined + "\n" + readme).split())

        for text in [
            "aspec status --json",
            "aspec lifecycle --json",
            "aspec outcome --json",
            "aspec task next",
            "aspec run loop",
            "aspec run package",
            "aspec run result",
            "aspec task create",
            "aspec review code",
            "aspec roadmap",
            "aspec finish",
            "aspec session start",
            "aspec session finish",
            "aspec task complete",
            "aspec compile",
            "aspec drift",
            "aspec intake import",
            "--as-candidate",
            "aspec intake diff",
            "aspec intake promote",
            "Do not auto-promote",
            "does not own source parsing, diffing, promotion, or accepted snapshots",
        ]:
            self.assertIn(text, normalized)
        self.assertNotIn("agentspec-codex-plugin", normalized)

    def test_claude_cli_validates_plugin_when_available(self) -> None:
        if shutil.which("claude") is None:
            self.skipTest("Claude Code CLI is not installed.")

        result = subprocess.run(
            ["claude", "plugin", "validate", str(PLUGIN_ROOT)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Validation passed", result.stdout)


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
