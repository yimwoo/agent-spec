import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from agentspec.doctor import run_doctor
from agentspec.io import load_data, write_data


class DoctorTests(unittest.TestCase):
    def test_doctor_reports_agent_profile_health_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".agentspec").mkdir()
            write_data(
                root / ".agentspec" / "config.yml",
                {
                    "version": 1,
                    "agent_profiles": {
                        "main_executor": {"adapter": "current-host", "model": "host-default"},
                        "continuation_reviewer": {
                            "adapter": "codex",
                            "base_url": "https://example.test/v1",
                            "api_key": "secret-token",
                            "model": "gpt-5.5",
                        },
                    },
                    "supervised_runs": {
                        "executor_profile": "main_executor",
                        "continuation_reviewer_profile": "continuation_reviewer",
                        "quality_reviewer_profile": "missing_quality",
                    },
                },
            )

            scan = run_doctor(root)

            profiles = scan["agent_profiles"]
            self.assertEqual(profiles["bindings"]["continuation_reviewer"], "continuation_reviewer")
            self.assertEqual(profiles["profiles"]["continuation_reviewer"]["status"], "ready")
            self.assertEqual(profiles["profiles"]["continuation_reviewer"]["credential_status"], "profile")
            self.assertEqual(profiles["profiles"]["missing_quality"]["status"], "missing")
            self.assertNotIn("secret-token", json.dumps(scan))

            persisted = load_data(root / "reports" / "doctor" / "repo-scan.yml")
            report = (root / "reports" / "doctor" / "agent-readiness.md").read_text(encoding="utf-8")
            self.assertIn("agent_profiles", persisted)
            self.assertIn("## Agent Profiles", report)
            self.assertIn("continuation_reviewer=continuation_reviewer", report)

    def test_doctor_excludes_ignored_private_state_from_context_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("/agent/\n", encoding="utf-8")
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            write_data(root / "docs" / "discovery" / "readiness.yml", {"score": 100})
            write_data(root / "agent" / "task-ledger.yml", {"tasks": {}})
            (root / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
            (root / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
            codex_agent = root / ".codex" / "agents" / "spec-reviewer.toml"
            codex_agent.parent.mkdir(parents=True)
            codex_agent.write_text('name = "spec-reviewer"\n', encoding="utf-8")
            for path in [
                root / "docs" / "traceability" / "requirements.yml",
                root / "docs" / "discovery" / "readiness.yml",
            ]:
                os.utime(path, ns=(1_700_000_000_000_000_000,) * 2)
            for path in [root / "AGENTS.md", root / "CLAUDE.md", codex_agent]:
                os.utime(path, ns=(1_700_000_001_000_000_000,) * 2)
            os.utime(root / "agent" / "task-ledger.yml", ns=(1_700_000_002_000_000_000,) * 2)

            scan = run_doctor(root)

            context = scan["agent_context"]
            self.assertEqual(context["status"], "fresh")
            self.assertNotIn("agent/task-ledger.yml", context["source_artifacts"])
            self.assertEqual(context["warnings"], [])


if __name__ == "__main__":
    unittest.main()
