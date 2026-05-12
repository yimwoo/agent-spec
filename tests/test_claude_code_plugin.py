import json
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from agentspec.emit import emit_targets


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
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "aspec")
        self.assertEqual(manifest["version"], pyproject["project"]["version"])
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

    def test_claude_marketplace_points_to_plugin_package(self) -> None:
        marketplace_path = REPO_ROOT / ".claude-plugin" / "marketplace.json"
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

        self.assertEqual(marketplace["name"], "agentspec")
        self.assertEqual(marketplace["owner"]["name"], "AgentSpec")
        self.assertEqual(len(marketplace["plugins"]), 1)

        plugin = marketplace["plugins"][0]
        self.assertEqual(plugin["name"], "aspec")
        self.assertEqual(plugin["source"], "./agentspec-claude-plugin")
        self.assertIn("AgentSpec", plugin["description"])

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
            "/plugin marketplace add yimwoo/agent-spec",
            "/plugin install aspec@agentspec",
            "/aspec:init-project",
            "/aspec:continue-work",
            "CLI path",
            "Plugin path",
            "aspec --root \"$TARGET\" init",
            "aspec status",
        ]:
            self.assertIn(text, readme)
        self.assertNotIn("/plugin marketplace add https://github.com/yimwoo/agent-spec.git", readme)
        self.assertNotIn("claude --plugin-dir", readme)

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

    def test_claude_start_and_delegate_skills_require_dedicated_write_leases(self) -> None:
        start_skill = (PLUGIN_ROOT / "skills" / "start-branch" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        delegate_skill = (PLUGIN_ROOT / "skills" / "delegate-work" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        for text in [
            "dedicated git branch",
            "dedicated git worktree",
            "Do not reuse an active",
            "--mode observer",
            "--allow-shared",
            "git worktree add",
        ]:
            self.assertIn(text, start_skill)
        for text in [
            "branch/worktree lease for write-mode",
            "Do not point two owner/patcher",
            "--allow-shared",
            "aspec session list --json",
        ]:
            self.assertIn(text, delegate_skill)

    def test_plugin_skills_hide_internal_cli_checks_from_human_replies(self) -> None:
        plugin_roots = [
            REPO_ROOT / "agentspec-codex-plugin",
            REPO_ROOT / "agentspec-claude-plugin",
        ]
        for plugin_root in plugin_roots:
            with self.subTest(plugin=plugin_root.name):
                finish_work = (
                    plugin_root / "skills" / "finish-work" / "SKILL.md"
                ).read_text(encoding="utf-8")
                verify_work = (
                    plugin_root / "skills" / "verify-work" / "SKILL.md"
                ).read_text(encoding="utf-8")
                combined = finish_work + "\n" + verify_work

                self.assertIn("Human-Facing Output", combined)
                self.assertIn("keep raw `aspec ...` commands internal", combined)
                self.assertIn("Outcome gates are ready", combined)
                self.assertIn("Roadmap freshness check passed", combined)
                self.assertIn("Do not include a final \"Tests / checks run\" section", combined)
                self.assertIn("Do not list `aspec outcome --json`", combined)

    def test_plugin_guidance_requires_session_gate_before_execution(self) -> None:
        plugin_roots = [
            REPO_ROOT / "agentspec-codex-plugin",
            REPO_ROOT / "agentspec-claude-plugin",
        ]
        for plugin_root in plugin_roots:
            with self.subTest(plugin=plugin_root.name):
                combined = "\n".join(
                    [
                        (plugin_root / "README.md").read_text(encoding="utf-8"),
                        (plugin_root / "skills" / "continue-work" / "SKILL.md").read_text(
                            encoding="utf-8"
                        ),
                        (plugin_root / "skills" / "create-task" / "SKILL.md").read_text(
                            encoding="utf-8"
                        ),
                        (plugin_root / "skills" / "plan-workflow" / "SKILL.md").read_text(
                            encoding="utf-8"
                        ),
                        (plugin_root / "skills" / "start-branch" / "SKILL.md").read_text(
                            encoding="utf-8"
                        ),
                        (plugin_root / "skills" / "execute-workflow" / "SKILL.md").read_text(
                            encoding="utf-8"
                        ),
                        (plugin_root / "skills" / "finish-work" / "SKILL.md").read_text(
                            encoding="utf-8"
                        ),
                    ]
                )
                normalized = " ".join(combined.split())

                for text in [
                    "task pack -> workflow -> branch/worktree/session -> execution -> verification -> review -> finish",
                    "Claim or verify an active owner/patcher session lease before implementation execution.",
                    "Do not start `aspec run loop`, `aspec run package`, or `aspec run exec` until session preflight is satisfied.",
                    "Explicit host-worktree execution is an auditable escape hatch",
                ]:
                    self.assertIn(text, normalized)

    def test_emitted_agent_guidance_requires_session_gate_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            emit_targets(root, "agents-md,claude,codex")

            combined = "\n".join(
                [
                    (root / "AGENTS.md").read_text(encoding="utf-8"),
                    (root / "CLAUDE.md").read_text(encoding="utf-8"),
                    (
                        root / ".claude" / "skills" / "agentspec-execute-workflow" / "SKILL.md"
                    ).read_text(encoding="utf-8"),
                    (
                        root / ".claude" / "skills" / "agentspec-start-branch" / "SKILL.md"
                    ).read_text(encoding="utf-8"),
                    (root / ".codex" / "agents" / "spec-reviewer.toml").read_text(
                        encoding="utf-8"
                    ),
                ]
            )
            normalized = " ".join(combined.split())

            for text in [
                "task pack -> workflow -> branch/worktree/session -> execution -> verification -> review -> finish",
                "Claim or verify an active owner/patcher session lease before implementation execution.",
                "Do not start `aspec run loop`, `aspec run package`, or `aspec run exec` until session preflight is satisfied.",
                "Explicit host-worktree execution is an auditable escape hatch",
            ]:
                self.assertIn(text, normalized)

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
