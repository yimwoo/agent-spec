import contextlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data


class MaturityCliTests(unittest.TestCase):
    def test_missing_maturity_config_defaults_to_lightweight(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            payload = _run_json(root, ["maturity", "status", "--json"])

            self.assertEqual(payload["schema"], "agentspec.maturity_status.v0")
            self.assertFalse(payload["configured"])
            self.assertEqual(payload["level"], "lightweight")
            self.assertEqual(payload["enforcement"], "warn")
            self.assertEqual(payload["readiness"], "needs_attention")
            self.assertEqual(payload["counts"]["checks"], 4)
            self.assertEqual(payload["counts"]["warnings"], 4)
            self.assertEqual(payload["counts"]["blocking"], 0)

    def test_init_writes_selected_maturity_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            self.assertEqual(
                main(
                    [
                        "--root",
                        str(root),
                        "init",
                        "--maturity",
                        "governed-implementation",
                        "--maturity-enforcement",
                        "block",
                    ]
                ),
                0,
            )

            config = load_data(root / "agent" / "maturity.yml")
            self.assertEqual(config["schema"], "agentspec.maturity.v1")
            self.assertEqual(config["level"], "governed-implementation")
            self.assertEqual(config["enforcement"], "block")

            status = _run_json(root, ["maturity", "status", "--json"])
            self.assertTrue(status["configured"])
            self.assertEqual(status["level"], "governed-implementation")
            self.assertEqual(status["enforcement"], "block")
            self.assertGreater(status["counts"]["checks"], 4)

    def test_maturity_set_updates_profile_and_reports_blocking_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            payload = _run_json(
                root,
                [
                    "maturity",
                    "set",
                    "production-readiness",
                    "--enforcement",
                    "block",
                    "--json",
                ],
            )

            self.assertEqual(payload["level"], "production-readiness")
            self.assertEqual(payload["enforcement"], "block")
            self.assertEqual(payload["readiness"], "blocked")
            self.assertGreater(payload["counts"]["blocking"], 0)
            self.assertEqual(payload["counts"]["warnings"], 0)
            config = load_data(root / "agent" / "maturity.yml")
            self.assertEqual(config["level"], "production-readiness")
            self.assertEqual(config["enforcement"], "block")

    def test_status_includes_maturity_payload_and_human_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.assertEqual(main(["--root", str(root), "init"]), 0)

            payload = _run_json(root, ["status", "--json"])
            self.assertIn("maturity", payload)
            self.assertEqual(payload["maturity"]["level"], "lightweight")
            self.assertTrue(payload["maturity"]["configured"])

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--root", str(root), "status"]), 0)
            self.assertIn("Maturity: lightweight", output.getvalue())

    def test_maturity_check_reports_same_shape_as_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            payload = _run_json(root, ["maturity", "check", "--json"])

            self.assertEqual(payload["schema"], "agentspec.maturity_status.v0")
            self.assertIn("checks", payload)
            self.assertIn("missing", payload)
            self.assertIn("warnings", payload)
            self.assertIn("blocking", payload)

    def test_production_readiness_accepts_rollback_plan_from_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = root / "agent" / "context-packs" / "T-001-production.md"
            pack.parent.mkdir(parents=True, exist_ok=True)
            pack.write_text(
                """# T-001: Production Gate

## Allowed Paths

- `agentspec/maturity.py`

## Rollback Plan

Revert the release commit.
""",
                encoding="utf-8",
            )

            payload = _run_json(
                root,
                [
                    "maturity",
                    "set",
                    "production-readiness",
                    "--enforcement",
                    "block",
                    "--json",
                ],
            )

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["rollback_plan"]["status"], "passed")
            self.assertEqual(
                checks["rollback_plan"]["evidence"],
                ["agent/context-packs/T-001-production.md"],
            )

    def test_production_readiness_rejects_placeholder_security_and_ci_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "reports" / "security").mkdir(parents=True)
            (root / "reports" / "eval").mkdir(parents=True)
            (root / "reports" / "eval" / ".gitkeep").write_text("", encoding="utf-8")
            workflow = root / ".github" / "workflows" / "agentspec-drift.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "name: Drift\njobs:\n  drift:\n    steps:\n      - run: python -m agentspec.cli drift\n",
                encoding="utf-8",
            )

            payload = _run_json(
                root,
                [
                    "maturity",
                    "set",
                    "production-readiness",
                    "--enforcement",
                    "block",
                    "--json",
                ],
            )

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["security_review"]["status"], "missing")
            self.assertEqual(checks["security_review"]["evidence"], [])
            self.assertEqual(checks["ci_e2e_evidence"]["status"], "missing")
            self.assertEqual(checks["ci_e2e_evidence"]["evidence"], [])

    def test_production_readiness_accepts_concrete_security_and_ci_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            security_report = root / "reports" / "security" / "latest.md"
            security_report.parent.mkdir(parents=True)
            security_report.write_text("# Security Review\n\nNo blocking findings.\n", encoding="utf-8")
            workflow = root / ".github" / "workflows" / "tests.yml"
            workflow.parent.mkdir(parents=True)
            workflow.write_text(
                "name: Tests\njobs:\n  test:\n    steps:\n      - run: pytest -q\n",
                encoding="utf-8",
            )

            payload = _run_json(
                root,
                [
                    "maturity",
                    "set",
                    "production-readiness",
                    "--enforcement",
                    "block",
                    "--json",
                ],
            )

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["security_review"]["status"], "passed")
            self.assertEqual(checks["security_review"]["evidence"], ["reports/security/latest.md"])
            self.assertEqual(checks["ci_e2e_evidence"]["status"], "passed")
            self.assertEqual(checks["ci_e2e_evidence"]["evidence"], [".github/workflows/tests.yml"])


def _run_json(root: Path, args: list[str]) -> dict:
    output = io.StringIO()
    with redirect_stdout(output):
        result = main(["--root", str(root), *args])
    with contextlib.suppress(json.JSONDecodeError):
        payload = json.loads(output.getvalue())
        if result != 0:
            raise AssertionError(payload)
        return payload
    raise AssertionError(f"Command failed with result={result}: {output.getvalue()}")


if __name__ == "__main__":
    unittest.main()
