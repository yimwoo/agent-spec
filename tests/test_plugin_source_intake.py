import json
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

from agentspec.emit import EMITTED_CLAUDE_SKILLS, emit_targets


REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_SKILL_NAMES = [
    "brainstorm",
    "continue-work",
    "design-work",
    "finish-work",
    "init-project",
    "outcome-audit",
    "plan-workflow",
    "project-status",
    "review-doc",
]
CONTROLLER_SKILL_NAMES = [
    "compile-spec",
    "create-task",
    "delegate-work",
    "drift-review",
    "execute-workflow",
    "finish-branch",
    "handoff-recovery",
    "manual-source-intake",
    "review-code",
    "roadmap",
    "start-branch",
    "verify-work",
]


class PluginSourceIntakeTests(unittest.TestCase):
    def test_codex_plugin_manual_source_intake_skill_is_cli_backed(self) -> None:
        plugin_root = REPO_ROOT / "agentspec-codex-plugin"
        plugin_manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
        skill_path = plugin_root / "controller" / "skills" / "manual-source-intake" / "SKILL.md"
        status_skill_path = plugin_root / "skills" / "project-status" / "SKILL.md"
        skill_manifest_path = plugin_root / "manifests" / "skill-manifest.json"

        manifest = json.loads(plugin_manifest_path.read_text(encoding="utf-8"))
        skill_manifest = json.loads(skill_manifest_path.read_text(encoding="utf-8"))
        skill = skill_path.read_text(encoding="utf-8")
        status_skill = status_skill_path.read_text(encoding="utf-8")

        self.assertEqual(manifest["name"], "aspec")
        self.assertEqual(manifest["interface"]["displayName"], "aspec")
        self.assertEqual(sorted(skill_manifest["public_skills"]), sorted(PUBLIC_SKILL_NAMES))
        self.assertEqual(
            sorted(skill["id"] for skill in skill_manifest["controller_skills"]),
            sorted(CONTROLLER_SKILL_NAMES),
        )
        for skill_name in PUBLIC_SKILL_NAMES:
            self.assertTrue((plugin_root / "skills" / skill_name / "SKILL.md").exists())
        for skill_name in CONTROLLER_SKILL_NAMES:
            self.assertFalse((plugin_root / "skills" / skill_name / "SKILL.md").exists())
            self.assertTrue((plugin_root / "controller" / "skills" / skill_name / "SKILL.md").exists())
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
            "aspec:review-doc",
            "Codex CLI",
            "/plugins",
            "Codex app",
            "Plugins > Local Plugins",
        ]:
            self.assertIn(text, readme)
        self.assertNotIn("agentspec-codex-plugin:", readme)

    def test_codex_installer_documents_cli_and_app_next_steps(self) -> None:
        script_path = REPO_ROOT / "install.sh"
        result = subprocess.run(
            ["bash", "-n", str(script_path)],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        script = script_path.read_text(encoding="utf-8")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Codex CLI", script)
        self.assertIn("/plugins", script)
        self.assertIn("Codex app", script)
        self.assertIn("Plugins > Local Plugins", script)

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

    def test_codex_start_and_delegate_skills_require_dedicated_write_leases(self) -> None:
        plugin_root = REPO_ROOT / "agentspec-codex-plugin"
        start_skill = (
            plugin_root / "controller" / "skills" / "start-branch" / "SKILL.md"
        ).read_text(
            encoding="utf-8"
        )
        delegate_skill = (
            plugin_root / "controller" / "skills" / "delegate-work" / "SKILL.md"
        ).read_text(encoding="utf-8")

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
                self.assertIn("aspec:continue-work", role_config["developer_instructions"])
                self.assertIn("aspec:review-doc", role_config["developer_instructions"])
                self.assertNotIn("aspec:execute-workflow", role_config["developer_instructions"])
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
            expected_skill_names = [f"agentspec-{name}" for name in PUBLIC_SKILL_NAMES]

            self.assertEqual(sorted(skill_names), sorted(expected_skill_names))
            for controller_name in CONTROLLER_SKILL_NAMES:
                self.assertNotIn(f"agentspec-{controller_name}", skill_names)
            self.assertNotIn("agentspec-lifecycle", skill_names)
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
            emitted_dirs = sorted(
                path.parent.name
                for path in (root / ".claude" / "skills").glob("*/SKILL.md")
            )
            self.assertEqual(sorted(expected_skill_names), emitted_dirs)

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
                "aspec task create",
                "aspec plan",
                "aspec run loop",
                "aspec outcome --json",
                "aspec review doc",
                "aspec review code",
                "aspec finish",
                "aspec drift",
            ]:
                self.assertIn(command, combined)

    def test_repo_does_not_ship_project_local_agentspec_skills(self) -> None:
        local_skills = list((REPO_ROOT / ".agents" / "skills").glob("agentspec-*/SKILL.md"))

        self.assertEqual([], local_skills)

    def test_plugin_packages_exclude_project_local_artifacts(self) -> None:
        forbidden_prefixes = (
            ".agents/",
            ".agentspec/",
            ".claude/",
            ".codex/",
            "agent/",
            "docs/",
            "reports/",
        )
        plugin_roots = {
            "agentspec-codex-plugin": {
                ".codex-plugin",
                "README.md",
                "controller",
                "hooks",
                "manifests",
                "reviewers",
                "skills",
                "workers",
            },
            "agentspec-claude-plugin": {
                ".claude-plugin",
                "README.md",
                "controller",
                "hooks",
                "manifests",
                "reviewers",
                "skills",
                "workers",
            },
        }

        for plugin_name, allowed_roots in plugin_roots.items():
            plugin_root = REPO_ROOT / plugin_name
            rel_files = [
                path.relative_to(plugin_root).as_posix()
                for path in plugin_root.rglob("*")
                if path.is_file() and path.name != ".DS_Store"
            ]
            offenders = [
                rel for rel in rel_files if rel.startswith(forbidden_prefixes)
            ]
            unexpected_roots = sorted(
                {
                    rel.split("/", 1)[0]
                    for rel in rel_files
                    if rel.split("/", 1)[0] not in allowed_roots
                }
            )

            self.assertEqual([], offenders, plugin_name)
            self.assertEqual([], unexpected_roots, plugin_name)

    def test_public_git_index_excludes_private_agentspec_state(self) -> None:
        if not (REPO_ROOT / ".git").exists():
            self.skipTest("Git metadata is not available.")

        result = subprocess.run(
            ["git", "ls-files"],
            cwd=REPO_ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

        forbidden_prefixes = (
            ".agents/",
            ".agentspec/",
            ".claude/",
            ".codex/",
            "agent/",
            "reports/",
            "docs/adr/",
            "docs/change-requests/",
            "docs/designs/",
            "docs/discovery/",
            "docs/plans/",
            "docs/source/",
            "docs/spec/",
            "docs/traceability/",
        )
        forbidden_exact = {
            "AGENTS.md",
            "CLAUDE.md",
            "docs/ROADMAP.md",
            ".github/workflows/agentspec-drift.yml",
        }
        offenders = [
            path
            for path in result.stdout.splitlines()
            if path in forbidden_exact or path.startswith(forbidden_prefixes)
        ]

        self.assertEqual([], offenders)

    def test_manual_source_intake_explains_ingest_baseline_source_key(self) -> None:
        plugin_root = REPO_ROOT / "agentspec-codex-plugin"
        skill = (
            plugin_root / "controller" / "skills" / "manual-source-intake" / "SKILL.md"
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

        for skill_name in PUBLIC_SKILL_NAMES:
            self.assertIn(f"aspec:{skill_name}", combined)
        for skill_name in CONTROLLER_SKILL_NAMES:
            self.assertNotIn(f"aspec:{skill_name}", combined)
        self.assertNotIn("agentspec-codex-plugin:", combined)

    def test_codex_internal_guidance_is_reachable_outside_public_skills(self) -> None:
        plugin_root = REPO_ROOT / "agentspec-codex-plugin"
        manifest = json.loads(
            (plugin_root / "manifests" / "skill-manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(manifest["schema"], "agentspec.skill_manifest.v0")
        controller_by_id = {skill["id"]: skill for skill in manifest["controller_skills"]}
        self.assertEqual(controller_by_id["execute-workflow"]["public_entrypoint"], "continue-work")
        self.assertEqual(controller_by_id["review-code"]["public_entrypoint"], "finish-work")
        self.assertEqual(controller_by_id["manual-source-intake"]["public_entrypoint"], "design-work")
        self.assertTrue((plugin_root / manifest["worker_bundles"][0]["path"]).exists())
        self.assertTrue((plugin_root / manifest["reviewer_profiles"][0]["path"]).exists())
        self.assertIn(
            "aspec run loop",
            (plugin_root / "controller" / "skills" / "execute-workflow" / "SKILL.md").read_text(
                encoding="utf-8"
            ),
        )


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
