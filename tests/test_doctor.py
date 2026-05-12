import json
import tempfile
import unittest
from pathlib import Path

from agentspec.doctor import run_doctor
from agentspec.io import load_data, write_data


class DoctorProfileDiagnosticsTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
