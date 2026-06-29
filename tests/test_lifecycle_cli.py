import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.lifecycle import (
    LIFECYCLE_CONTRACT_SCHEMA,
    build_execution_strategy,
    build_lifecycle_contract,
    format_lifecycle_contract,
)


class LifecycleCliTests(unittest.TestCase):
    def test_lifecycle_contract_describes_native_operating_contract(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            contract = build_lifecycle_contract(root)

            self.assertEqual(contract["schema"], LIFECYCLE_CONTRACT_SCHEMA)
            self.assertEqual(contract["root"], str(root.resolve()))
            self.assertEqual(contract["counts"], {"stages": 10, "available": 3, "partial": 6, "planned": 1})
            self.assertEqual(
                [
                    "brainstorm",
                    "design",
                    "plan",
                    "branch_start",
                    "execute",
                    "delegate",
                    "verify",
                    "review",
                    "branch_finish",
                    "handoff_recovery",
                ],
                [stage["id"] for stage in contract["stages"]],
            )

            owners = contract["adapter_boundary"]["agent_spec_owns"]
            adapters = contract["adapter_boundary"]["adapters_provide"]
            self.assertIn("task context packs", owners)
            self.assertIn("verification evidence", owners)
            self.assertIn("finish write-back", owners)
            self.assertIn("host-specific model invocation", adapters)
            self.assertIn("subagent process spawning", adapters)
            self.assertEqual(
                contract["post_artifact_guidance"]["schema"],
                "agentspec.post_artifact_guidance.v0",
            )
            self.assertFalse(contract["post_artifact_guidance"]["agent_display"]["show_terminal_commands"])
            execution = contract["execution"]
            self.assertEqual(execution["selected"]["mode"], "provider_native")
            self.assertEqual(execution["selected"]["provider"], "current-host")
            self.assertEqual(execution["selected"]["availability"], "unverified")
            self.assertEqual(execution["fallback"]["mode"], "agentspec_generic_fallback")
            self.assertIn("aspec run package", execution["fallback"]["commands"])
            self.assertIn("aspec run result", execution["fallback"]["commands"])

            inspiration = " ".join(source["value"] for source in contract["source_inspirations"])
            self.assertIn("idea refinement", inspiration)
            self.assertIn("planning", inspiration)
            self.assertIn("migration", inspiration)
            self.assertIn("launch", inspiration)

    def test_lifecycle_cli_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", td, "lifecycle", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], LIFECYCLE_CONTRACT_SCHEMA)
            self.assertEqual(payload["counts"]["stages"], 10)
            by_id = {stage["id"]: stage for stage in payload["stages"]}
            self.assertEqual(by_id["plan"]["status"], "available")
            self.assertIn("aspec plan", by_id["plan"]["native_commands"])
            self.assertIn("aspec guidance <artifact> --json", by_id["plan"]["native_commands"])
            self.assertEqual(by_id["delegate"]["status"], "planned")
            self.assertEqual(by_id["delegate"]["native_commands"], [])
            self.assertIn("delegate-work", by_id["delegate"]["skill_names"])
            self.assertIn("aspec finish", by_id["branch_finish"]["native_commands"])
            self.assertEqual(by_id["execute"]["preferred_execution"], "provider_native")
            self.assertEqual(by_id["execute"]["fallback_execution"], "agentspec_generic_fallback")

    def test_execution_strategy_reports_provider_capability_and_fallback(self) -> None:
        codex = build_execution_strategy(
            Path("/tmp/agentspec-lifecycle-test"),
            provider="codex",
            capabilities={"codex_goal_or_workflow": True},
        )
        self.assertEqual(codex["selected"]["provider"], "codex")
        self.assertEqual(codex["selected"]["mechanism"], "goal_or_workflow")
        self.assertEqual(codex["unavailable_capabilities"], [])

        unavailable = build_execution_strategy(
            Path("/tmp/agentspec-lifecycle-test"),
            provider="claude",
            capabilities={"claude_loop_or_dynamic_workflow": False},
        )
        self.assertEqual(unavailable["selected"]["mode"], "agentspec_generic_fallback")
        self.assertEqual(
            unavailable["unavailable_capabilities"][0]["id"],
            "claude_loop_or_dynamic_workflow",
        )
        self.assertIn("aspec run loop", unavailable["fallback"]["compatibility_commands"])

    def test_lifecycle_cli_human_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["--root", td, "lifecycle"])

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("AgentSpec Lifecycle Operating Contract", text)
            self.assertIn("Brainstorm And Frame [partial]", text)
            self.assertIn("Plan Workflow [available]", text)
            self.assertIn("Delegate Work [planned]", text)
            self.assertIn("Finish Branch [partial]", text)
            self.assertIn("Commands: aspec task create, aspec plan", text)
            self.assertIn("Skills: finish-branch, finish-work", text)

    def test_lifecycle_formatter_uses_statuses_and_native_commands(self) -> None:
        contract = build_lifecycle_contract(Path("/tmp/agentspec-lifecycle-test"))

        text = format_lifecycle_contract(contract)

        self.assertIn("1. Brainstorm And Frame [partial]", text)
        self.assertIn("6. Delegate Work [planned]", text)
        self.assertIn("Commands: -", text)
        self.assertIn("Next: Add aspec run delegate", text)


if __name__ == "__main__":
    unittest.main()
