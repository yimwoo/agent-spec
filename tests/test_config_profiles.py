import tempfile
import unittest
from pathlib import Path

from agentspec.config import merged_runtime_config, resolve_agent_profile
from agentspec.init import init_project
from agentspec.io import load_data


class ConfigProfileTests(unittest.TestCase):
    def test_init_writes_portable_agent_profile_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)

            config = load_data(root / ".agentspec" / "config.yml")
            profiles = config["agent_profiles"]

            self.assertEqual(
                profiles["main_executor"],
                {"adapter": "current-host", "model": "host-default"},
            )
            self.assertEqual(profiles["continuation_reviewer"]["adapter"], "codex")
            self.assertEqual(profiles["continuation_reviewer"]["credential_source"], "codex-auth")
            self.assertEqual(profiles["continuation_reviewer"]["config_source"], "codex-config")
            self.assertIsNone(profiles["continuation_reviewer"]["model"])
            self.assertNotIn("api_key", profiles["continuation_reviewer"])
            self.assertNotIn("token", profiles["continuation_reviewer"])

            self.assertEqual(profiles["quality_reviewer"]["reasoning"], "high")
            self.assertIsNone(profiles["quality_reviewer"]["model"])
            self.assertEqual(profiles["test_eval_reviewer"]["adapter"], "codex")
            self.assertEqual(profiles["test_eval_reviewer"]["config_source"], "codex-config")
            self.assertEqual(profiles["test_eval_reviewer"]["reasoning"], "high")
            self.assertIsNone(profiles["test_eval_reviewer"]["model"])

    def test_init_writes_supervised_run_profile_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)

            config = load_data(root / ".agentspec" / "config.yml")
            runs = config["supervised_runs"]

            self.assertEqual(runs["executor_profile"], "main_executor")
            self.assertEqual(runs["continuation_reviewer_profile"], "continuation_reviewer")
            self.assertEqual(runs["quality_reviewer_profile"], "test_eval_reviewer")
            self.assertEqual(runs["max_iterations"]["implementation"], 3)

    def test_resolve_agent_profile_merges_defaults_for_existing_configs(self) -> None:
        profile = resolve_agent_profile({"version": 1}, "main_executor")

        self.assertEqual(profile["adapter"], "current-host")
        self.assertEqual(profile["model"], "host-default")

    def test_resolve_agent_profile_preserves_project_override(self) -> None:
        config = {
            "agent_profiles": {
                "quality_reviewer": {
                    "adapter": "codex",
                    "credential_source": "codex-auth",
                    "config_source": "codex-config",
                    "model": "oca/gpt-5.5",
                    "reasoning": "high",
                }
            }
        }

        merged = merged_runtime_config(config)
        profile = resolve_agent_profile(config, "quality_reviewer")

        self.assertEqual(profile["model"], "oca/gpt-5.5")
        self.assertEqual(merged["agent_profiles"]["main_executor"]["model"], "host-default")

    def test_test_eval_reviewer_model_override_is_independent_of_executor(self) -> None:
        config = {
            "agent_profiles": {
                "main_executor": {"adapter": "current-host", "model": "host-default"},
                "test_eval_reviewer": {
                    "adapter": "codex",
                    "credential_source": "codex-auth",
                    "config_source": "codex-config",
                    "model": "oca/gpt5.3-codex",
                    "reasoning": "high",
                },
            },
            "supervised_runs": {
                "quality_reviewer_profile": "test_eval_reviewer",
            },
        }

        executor = resolve_agent_profile(config, "main_executor")
        evaluator = resolve_agent_profile(config, "test_eval_reviewer")

        self.assertEqual(executor["model"], "host-default")
        self.assertEqual(evaluator["model"], "oca/gpt5.3-codex")


if __name__ == "__main__":
    unittest.main()
