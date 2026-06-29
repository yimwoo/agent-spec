import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import write_data
from agentspec.outcome import (
    OUTCOME_OBSERVATION_SCHEMA,
    OUTCOME_STATUS_SCHEMA,
    OUTCOME_VERDICT_SCHEMA,
    OUTCOME_VERDICTS_SCHEMA,
    build_outcome_status,
    format_outcome_status,
    record_outcome_observation,
    write_outcome_verdicts,
)
from agentspec.status import build_project_status


class OutcomeCliTests(unittest.TestCase):
    def test_typed_outcome_checks_cover_all_evidence_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            checks = [
                ("C-command", "command", {"exit_code": 0}),
                ("C-browser", "browser_ui", {"journeys_total": 3, "journeys_passed": 3}),
                ("C-slo", "slo", {"compliant": True, "window": "30d"}),
                ("C-api", "api_compatibility", {"breaking_changes": 0}),
                ("C-deploy", "deployment", {"healthy": True, "environment": "production"}),
                ("C-release", "release", {"ready": True, "artifact": "dist/app.whl"}),
            ]
            _write_typed_outcomes(root, checks=[(check_id, kind) for check_id, kind, _ in checks])
            for check_id, kind, facts in checks:
                recorded = record_outcome_observation(
                    root,
                    {
                        "outcome_id": "O-typed",
                        "gate_id": "G-proof",
                        "check_id": check_id,
                        "kind": kind,
                        "observed_at": "2026-06-29T20:00:00Z",
                        "source": {
                            "type": "external_adapter",
                            "adapter": f"test-{kind}",
                            "run_id": f"run-{check_id}",
                        },
                        "facts": facts,
                    },
                )
                self.assertEqual(recorded["schema"], OUTCOME_OBSERVATION_SCHEMA)

            status = build_outcome_status(root, evaluated_at="2026-06-29T20:30:00Z")

            self.assertEqual(status["readiness"], "ready")
            gate = status["outcomes"][0]["gates"][0]
            self.assertEqual(gate["status"], "passed")
            self.assertEqual({item["kind"] for item in gate["verdicts"]}, {item[1] for item in checks})
            self.assertTrue(all(item["schema"] == OUTCOME_VERDICT_SCHEMA for item in gate["verdicts"]))
            self.assertTrue(all(item["status"] == "passed" for item in gate["verdicts"]))
            self.assertEqual(status["evidence_contract"]["adapter_role"], "observation_only")

            persisted = write_outcome_verdicts(root)
            self.assertEqual(persisted["schema"], OUTCOME_VERDICTS_SCHEMA)
            self.assertEqual(persisted["policy_authority"], "agentspec.outcome")
            self.assertTrue((root / persisted["path"]).is_file())

    def test_typed_outcomes_report_missing_stale_failed_and_malformed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_typed_outcomes(
                root,
                checks=[
                    ("C-missing", "command"),
                    ("C-stale", "browser_ui"),
                    ("C-failed", "slo"),
                    ("C-malformed", "api_compatibility"),
                ],
            )
            _write_observation(root, "OBS-stale", "C-stale", "browser_ui", {"journeys_total": 1, "journeys_passed": 1}, "2026-06-27T00:00:00Z")
            _write_observation(root, "OBS-failed", "C-failed", "slo", {"compliant": False}, "2026-06-29T20:00:00Z")
            _write_observation(root, "OBS-malformed", "C-malformed", "api_compatibility", {"breaking_changes": "none"}, "2026-06-29T20:00:00Z")

            status = build_outcome_status(root, evaluated_at="2026-06-29T20:30:00Z")

            verdicts = status["outcomes"][0]["gates"][0]["verdicts"]
            by_id = {verdict["check_id"]: verdict for verdict in verdicts}
            self.assertEqual(by_id["C-missing"]["status"], "missing")
            self.assertEqual(by_id["C-stale"]["status"], "stale")
            self.assertEqual(by_id["C-failed"]["status"], "failed")
            self.assertEqual(by_id["C-malformed"]["status"], "malformed")
            self.assertEqual(status["readiness"], "blocked")
            self.assertIn("Run the command adapter", status["next_actions"][0])
            self.assertIn("Typed Evidence Verdicts:", format_outcome_status(status))

    def test_model_or_task_self_report_cannot_prove_production_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_typed_outcomes(root, checks=[("C-release", "release")])
            _write_observation(
                root,
                "OBS-self-report",
                "C-release",
                "release",
                {"ready": True},
                "2026-06-29T20:00:00Z",
                source_type="model_self_report",
            )

            status = build_outcome_status(root, evaluated_at="2026-06-29T20:30:00Z")

            verdict = status["outcomes"][0]["gates"][0]["verdicts"][0]
            self.assertEqual(verdict["status"], "untrusted")
            self.assertIn("not production outcome evidence", verdict["reason"])
            self.assertEqual(status["readiness"], "blocked")

    def test_observation_cli_records_facts_but_rejects_adapter_verdicts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            observation = {
                "outcome_id": "O-typed",
                "gate_id": "G-proof",
                "check_id": "C-command",
                "kind": "command",
                "observed_at": "2026-06-29T20:00:00Z",
                "source": {"type": "ci", "adapter": "github-actions", "run_id": "123"},
                "facts": {"exit_code": 0},
            }
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "outcome",
                        "observe",
                        "--input-json",
                        json.dumps(observation),
                        "--json",
                    ]
                )
            self.assertEqual(code, 0)
            recorded = json.loads(output.getvalue())
            self.assertEqual(recorded["source"]["adapter"], "github-actions")
            self.assertNotIn("status", recorded)

            with self.assertRaisesRegex(ValueError, "policy fields are forbidden"):
                record_outcome_observation(root, {**observation, "status": "passed"})

    def test_outcome_status_reports_blocked_gates_and_next_actions(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_blocked_outcomes(root)

            status = build_outcome_status(root)

            self.assertEqual(status["schema"], OUTCOME_STATUS_SCHEMA)
            self.assertEqual(status["readiness"], "blocked")
            self.assertEqual(status["score"], 50)
            self.assertEqual(status["counts"]["outcomes"], 1)
            self.assertEqual(status["counts"]["required_gates"], 2)
            self.assertEqual(status["counts"]["ready_required_gates"], 1)
            self.assertEqual(status["counts"]["blocked_required_gates"], 1)
            self.assertEqual(status["blockers"][0]["gate_id"], "G-002")
            self.assertIn("Wire real Run Detail to SSE", status["next_actions"])

            text = format_outcome_status(status)
            self.assertIn("Readiness: blocked", text)
            self.assertIn("Required gates are evidence checks", text)
            self.assertIn("Ready Required Gates:", text)
            self.assertIn("O-001/G-001: Backend run API works", text)
            self.assertIn("Not Ready Required Gates:", text)
            self.assertIn("O-001/G-002: Live per-step UI status works [blocked]", text)
            self.assertIn("O-001/G-002", text)
            self.assertIn("Wire real Run Detail to SSE", text)

    def test_outcome_cli_json_and_human_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_blocked_outcomes(root)

            json_output = io.StringIO()
            with redirect_stdout(json_output):
                code = main(["--root", str(root), "outcome", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(json_output.getvalue())
            self.assertEqual(payload["schema"], OUTCOME_STATUS_SCHEMA)
            self.assertEqual(payload["readiness"], "blocked")

            human_output = io.StringIO()
            with redirect_stdout(human_output):
                code = main(["--root", str(root), "outcome"])

            self.assertEqual(code, 0)
            self.assertIn("AgentSpec Product Outcomes", human_output.getvalue())
            self.assertIn("required gates 1/2", human_output.getvalue())

    def test_ready_outcome_still_points_to_next_lifecycle_action(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_ready_outcomes(root)

            status = build_outcome_status(root)

            self.assertEqual(status["readiness"], "ready")
            self.assertEqual(
                status["next_actions"],
                ["No outcome gate action is required; run `aspec status` to choose the next lifecycle action."],
            )
            self.assertEqual(
                status["agent_next_actions"],
                ["No outcome gate action is required; choose the next lifecycle action from project status."],
            )
            self.assertNotIn("aspec", "\n".join(status["agent_next_actions"]).lower())

            text = format_outcome_status(status)
            self.assertIn("Next Actions:", text)
            self.assertIn("aspec status", text)

    def test_status_includes_outcome_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_blocked_outcomes(root)
            write_data(root / "docs" / "traceability" / "requirements.yml", [])
            write_data(root / "docs" / "discovery" / "readiness.yml", {"score": 100, "mode": "normal-implementation"})

            status = build_project_status(root)

            self.assertIn("outcomes", status)
            self.assertEqual(status["outcomes"]["schema"], OUTCOME_STATUS_SCHEMA)
            self.assertEqual(status["outcomes"]["readiness"], "blocked")


def _write_blocked_outcomes(root: Path) -> None:
    write_data(
        root / "agent" / "outcomes.yml",
        {
            "schema": "agentspec.outcomes.v0",
            "outcomes": [
                {
                    "id": "O-001",
                    "title": "Run existing YAML testcase E2E",
                    "gates": [
                        {
                            "id": "G-001",
                            "title": "Backend run API works",
                            "status": "passed",
                            "required": True,
                            "evidence": [{"kind": "pytest", "path": "tests/test_run.py"}],
                        },
                        {
                            "id": "G-002",
                            "title": "Live per-step UI status works",
                            "status": "blocked",
                            "required": True,
                            "next_action": "Wire real Run Detail to SSE",
                        },
                    ],
                }
            ],
        },
    )


def _write_ready_outcomes(root: Path) -> None:
    write_data(
        root / "agent" / "outcomes.yml",
        {
            "schema": "agentspec.outcomes.v0",
            "outcomes": [
                {
                    "id": "O-001",
                    "title": "Run existing YAML testcase E2E",
                    "gates": [
                        {
                            "id": "G-001",
                            "title": "Backend run API works",
                            "status": "passed",
                            "required": True,
                            "evidence": [{"kind": "pytest", "path": "tests/test_run.py"}],
                        }
                    ],
                }
            ],
        },
    )


def _write_typed_outcomes(root: Path, *, checks: list[tuple[str, str]]) -> None:
    write_data(
        root / "agent" / "outcomes.yml",
        {
            "schema": "agentspec.outcomes.v0",
            "outcomes": [
                {
                    "id": "O-typed",
                    "title": "Production outcome",
                    "gates": [
                        {
                            "id": "G-proof",
                            "title": "Externally observed readiness",
                            "required": True,
                            "checks": [
                                {
                                    "id": check_id,
                                    "kind": kind,
                                    "max_age_seconds": 3600,
                                    "repair": f"Run the {kind.replace('_', ' ')} adapter for {check_id}.",
                                }
                                for check_id, kind in checks
                            ],
                        }
                    ],
                }
            ],
        },
    )


def _write_observation(
    root: Path,
    observation_id: str,
    check_id: str,
    kind: str,
    facts: dict[str, object],
    observed_at: str,
    *,
    source_type: str = "external_adapter",
) -> None:
    write_data(
        root / "agent" / "outcome-evidence" / "observations" / f"{observation_id}.yml",
        {
            "schema": OUTCOME_OBSERVATION_SCHEMA,
            "id": observation_id,
            "outcome_id": "O-typed",
            "gate_id": "G-proof",
            "check_id": check_id,
            "kind": kind,
            "observed_at": observed_at,
            "recorded_at": observed_at,
            "source": {"type": source_type, "adapter": f"fixture-{kind}", "run_id": observation_id},
            "facts": facts,
        },
    )


if __name__ == "__main__":
    unittest.main()
