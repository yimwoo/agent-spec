"""Integrity checks for public controlled-evaluation assets."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentspec.eval import load_evaluation_manifest
from agentspec.io import load_data


ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "benchmarks" / "controlled-evals" / "EXP-lifecycle-pilot"


def _load_runner_module():
    spec = importlib.util.spec_from_file_location("agentspec_pilot_runner", PILOT / "run_provider.py")
    if spec is None or spec.loader is None:
        raise AssertionError("Could not load controlled-evaluation runner.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


RUNNER = _load_runner_module()


class EvaluationAssetTests(unittest.TestCase):
    def test_pilot_manifest_pins_public_task_and_hidden_oracle_digests(self) -> None:
        manifest = load_evaluation_manifest(PILOT / "manifest.yml")
        task = manifest["tasks"][0]

        self.assertEqual(manifest["id"], "EXP-lifecycle-pilot")
        self.assertEqual({provider["id"] for provider in manifest["providers"]}, {"codex", "claude"})
        self.assertEqual({condition["agentspec"] for condition in manifest["conditions"]}, {True, False})
        self.assertEqual(task["revision"], _sha256(ROOT / task["source"]))
        self.assertEqual(task["oracle"]["revision"], _sha256(PILOT / "oracle" / "identifier_oracle.py"))

    def test_budget_runner_v2_is_new_and_preserves_original_evidence(self) -> None:
        original = PILOT / "manifest.yml"
        revised = PILOT / "manifest-v2.yml"
        manifest = load_evaluation_manifest(revised)

        self.assertEqual(
            _sha256(original),
            "sha256:54d0c5517ca0553f68a2641f58a77a6877025714ddae0f3956182e5df8deeb83",
        )
        self.assertEqual(
            _sha256(PILOT / "evidence" / "runs" / "EVALRUN-codex-control-r1.yml"),
            "sha256:bde739778b832b4d7621e78087a4a434b99646f3d71d0efa42432ecb7fd4e45f",
        )
        self.assertEqual(
            _sha256(PILOT / "evidence" / "runs" / "EVALRUN-codex-with-agentspec-r1.yml"),
            "sha256:8743736898bf6945f73d97b0e4f505d2403b011390460a5e6574e0fd3dcaa939",
        )
        self.assertEqual(manifest["id"], "EXP-lifecycle-pilot-v2")
        self.assertEqual(
            manifest["limits"]["policies"]["max_tokens"]["enforcement"],
            "post_run",
        )
        self.assertEqual(
            next(item for item in manifest["providers"] if item["id"] == "claude")["budget"][
                "enforcement"
            ],
            "provider",
        )

    def test_fixture_starts_with_passing_public_tests_and_failing_hidden_oracle(self) -> None:
        fixture = PILOT / "fixture"
        public = subprocess.run(
            ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
            cwd=fixture,
            check=False,
            text=True,
            capture_output=True,
        )
        environment = {**os.environ, "PYTHONPATH": str(fixture / "src")}
        oracle = subprocess.run(
            ["python", str(PILOT / "oracle" / "identifier_oracle.py")],
            cwd=fixture,
            env=environment,
            check=False,
            text=True,
            capture_output=True,
        )

        self.assertEqual(public.returncode, 0, public.stdout + public.stderr)
        self.assertNotEqual(oracle.returncode, 0, oracle.stdout + oracle.stderr)
        self.assertIn("creme-brulee", oracle.stdout + oracle.stderr)

    def test_workspace_preparer_isolates_agentspec_treatment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            control = base / "control"
            treatment = base / "with-agentspec"
            environment = {**os.environ, "PYTHONPATH": str(ROOT)}
            for destination, condition in [
                (control, "control"),
                (treatment, "with-agentspec"),
            ]:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(PILOT / "prepare_workspace.py"),
                        str(destination),
                        "--condition",
                        condition,
                    ],
                    cwd=ROOT,
                    env=environment,
                    check=False,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue((destination / ".git").is_dir())

            self.assertFalse((control / ".agentspec").exists())
            self.assertFalse((control / "agent").exists())
            self.assertTrue((treatment / ".agentspec" / "config.yml").is_file())
            self.assertTrue(
                (treatment / "agent" / "context-packs" / "T-001-normalize-identifiers.md").is_file()
            )
            self.assertEqual(
                load_data(treatment / "docs" / "discovery" / "readiness.yml")["score"],
                100,
            )

    def test_public_pilot_report_is_limitation_forward_for_partial_execution(self) -> None:
        report = (ROOT / "docs" / "evaluations" / "EXP-lifecycle-pilot.md").read_text(encoding="utf-8")

        self.assertIn("partial execution; Codex pair recorded, Claude transport blocked", report)
        self.assertIn("Expected cells: 4", report)
        self.assertIn("Recorded cells: 2", report)
        self.assertIn("not a causal or general AgentSpec performance claim", report)
        self.assertIn("enforce a token stop", report)
        self.assertIn("Actual cost reported | unavailable", report)

    def test_recorded_codex_pair_preserves_protocol_deviations(self) -> None:
        run_dir = PILOT / "evidence" / "runs"
        runs = [
            load_data(run_dir / "EVALRUN-codex-control-r1.yml"),
            load_data(run_dir / "EVALRUN-codex-with-agentspec-r1.yml"),
        ]

        self.assertEqual({run["condition_id"] for run in runs}, {"control", "with-agentspec"})
        for run in runs:
            self.assertTrue(run["metrics"]["completed"])
            self.assertEqual(run["metrics"]["regressions"], 0)
            self.assertEqual(run["metrics"]["escaped_defects"], 0)
            self.assertGreater(run["metrics"]["tokens"]["total"], run["limits"]["max_tokens"])
            self.assertIn("did not enforce a token stop", run["provenance"]["protocol_deviations"][0])
            self.assertFalse(run["provenance"]["raw_transcript_committed"])

        generated = load_data(PILOT / "evidence" / "comparison.yml")
        self.assertEqual(generated["expected_run_count"], 4)
        self.assertEqual(generated["recorded_run_count"], 2)
        self.assertEqual(generated["classifications"], {"valid": 0, "limited": 2, "invalid": 0})

    def test_runner_derives_models_and_provider_budget_from_manifest(self) -> None:
        manifest = _runner_manifest()
        workspace = Path("/tmp/eval-workspace")
        output_dir = Path("/tmp/eval-output")

        codex = RUNNER._provider_command("codex", "control", workspace, output_dir, manifest)
        claude = RUNNER._provider_command("claude", "control", workspace, output_dir, manifest)

        self.assertEqual(codex[codex.index("--model") + 1], "codex-test-model")
        self.assertEqual(claude[claude.index("--model") + 1], "claude-test-model")
        self.assertEqual(claude[claude.index("--max-budget-usd") + 1], "2.5")

    def test_runner_watchdog_terminates_a_duration_overrun(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = RUNNER._run_process(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                cwd=Path(td),
                prompt="",
                timeout_seconds=0.05,
                termination_grace_seconds=0.05,
            )

        self.assertTrue(result.timed_out)
        self.assertNotEqual(result.return_code, 0)
        self.assertIn(result.termination_signal, {"SIGTERM", "SIGKILL", "terminate"})

    def test_runner_extracts_codex_usage_and_rejects_token_overrun(self) -> None:
        stdout = "\n".join(
            [
                json.dumps({"type": "turn.started"}),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 80,
                            "output_tokens": 10,
                        },
                    }
                ),
            ]
        )

        usage = RUNNER._extract_usage("codex", stdout)
        outcomes = RUNNER._evaluate_limit_outcomes(
            _runner_manifest(),
            provider="codex",
            usage=usage,
            cost_usd=None,
            duration_seconds=1.0,
            retries=0,
            timed_out=False,
        )

        self.assertEqual(usage, {"input": 100, "cached": 80, "output": 10, "total": 110})
        self.assertEqual(outcomes["max_tokens"]["status"], "exceeded")
        self.assertEqual(outcomes["max_cost_usd"]["status"], "unavailable")

    def test_runner_writes_separate_provider_and_protocol_outcomes(self) -> None:
        event = json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 100,
                    "cached_input_tokens": 80,
                    "output_tokens": 10,
                },
            }
        )
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output_dir = root / "raw"
            with mock.patch.object(
                RUNNER,
                "_provider_command",
                return_value=[sys.executable, "-c", f"print({event!r})"],
            ):
                code = RUNNER.run_cell(
                    "codex",
                    "control",
                    root,
                    output_dir,
                    PILOT / "manifest-v2.yml",
                )
            execution = load_data(output_dir / "execution.json")

        self.assertEqual(code, 0)
        self.assertEqual(execution["schema"], "agentspec.provider_execution.v1")
        self.assertEqual(execution["provider_return_code"], 0)
        self.assertEqual(execution["runner_return_code"], 0)
        self.assertEqual(execution["stop_reason"], "completed")
        self.assertEqual(execution["usage"]["total"], 110)
        self.assertEqual(execution["limit_outcomes"]["max_tokens"]["status"], "passed")
        self.assertEqual(
            execution["effective_limits"]["provider_budget"]["enforcement"],
            "unavailable",
        )

    def test_runner_detects_semantic_provider_failures_with_zero_exit_code(self) -> None:
        claude = json.dumps(
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "api_error_status": 401,
                "result": "Failed to authenticate.",
            }
        )
        codex = "\n".join(
            [
                json.dumps({"type": "turn.started"}),
                json.dumps({"type": "turn.failed", "error": {"message": "model unavailable"}}),
            ]
        )

        self.assertEqual(
            RUNNER._provider_failure("claude", claude),
            "Claude result reported is_error=true (api_error_status=401).",
        )
        self.assertEqual(
            RUNNER._provider_failure("codex", codex),
            "Codex emitted turn.failed: model unavailable",
        )


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _runner_manifest() -> dict[str, object]:
    return {
        "providers": [
            {
                "id": "codex",
                "model": "codex-test-model",
                "budget": {
                    "max_cost_usd": None,
                    "unit": "usd",
                    "enforcement": "unavailable",
                    "observation_required": False,
                },
            },
            {
                "id": "claude",
                "model": "claude-test-model",
                "budget": {
                    "max_cost_usd": 2.5,
                    "unit": "usd",
                    "enforcement": "provider",
                    "observation_required": True,
                },
            },
        ],
        "limits": {
            "max_duration_seconds": 60,
            "max_tokens": 100,
            "max_retries": 0,
            "policies": {
                "max_duration_seconds": {
                    "unit": "seconds",
                    "enforcement": "runner",
                    "observation_required": True,
                },
                "max_tokens": {
                    "unit": "tokens",
                    "enforcement": "post_run",
                    "observation_required": True,
                },
                "max_retries": {
                    "unit": "attempts",
                    "enforcement": "runner",
                    "observation_required": True,
                },
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
