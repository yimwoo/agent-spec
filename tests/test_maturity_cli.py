import contextlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data, write_data


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

    def test_governed_maturity_accepts_public_release_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_governed_project(root)
            write_data(
                root / "docs" / "release" / "evidence.yml",
                {
                    "schema": "agentspec.release_evidence.v0",
                    "updated_at": "2026-06-29T00:00:00Z",
                    "tasks": {
                        "agent/context-packs/T-013-task.md": {
                            "task_id": "T-013",
                            "context_pack": "agent/context-packs/T-013-task.md",
                            "status": "complete",
                            "run_id": "complete-t013",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001", "verdict": "ready"},
                            "updated_at": "2026-06-29T00:00:00Z",
                        }
                    },
                },
            )

            payload = _run_json(root, ["maturity", "status", "--json"])

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["review_evidence"]["status"], "passed")
            self.assertEqual(
                checks["review_evidence"]["evidence"],
                ["docs/release/evidence.yml", "agent/context-packs/T-013-task.md"],
            )
            self.assertEqual(checks["test_evidence"]["status"], "passed")
            self.assertEqual(
                checks["test_evidence"]["evidence"],
                ["docs/release/evidence.yml", "agent/context-packs/T-013-task.md"],
            )

    def test_governed_maturity_rejects_unsupported_public_evidence_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_governed_project(root)
            evidence = _public_release_evidence()
            evidence["schema"] = "agentspec.release_evidence.future"
            write_data(root / "docs" / "release" / "evidence.yml", evidence)

            payload = _run_json(root, ["maturity", "status", "--json"])

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["review_evidence"]["status"], "missing")
            self.assertEqual(checks["test_evidence"]["status"], "missing")

    def test_governed_maturity_rejects_empty_public_review(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_governed_project(root)
            evidence = _public_release_evidence()
            evidence["tasks"]["agent/context-packs/T-013-task.md"]["code_review"] = {}
            write_data(root / "docs" / "release" / "evidence.yml", evidence)

            payload = _run_json(root, ["maturity", "status", "--json"])

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["review_evidence"]["status"], "missing")
            self.assertEqual(checks["test_evidence"]["status"], "missing")

    def test_governed_maturity_uses_latest_public_review_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_governed_project(root)
            evidence = _public_release_evidence(verdict="not-ready", review_id="REVIEW-0002")
            evidence["tasks"]["agent/context-packs/T-013-task.md"]["reviews"] = [
                {"id": "REVIEW-0001", "verdict": "ready"},
                {"id": "REVIEW-0002", "verdict": "not-ready"},
            ]
            write_data(root / "docs" / "release" / "evidence.yml", evidence)

            payload = _run_json(root, ["maturity", "status", "--json"])

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["review_evidence"]["status"], "missing")
            self.assertEqual(checks["test_evidence"]["status"], "passed")

    def test_public_evidence_survives_private_context_pack_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _seed_governed_project(root)
            write_data(
                root / "docs" / "release" / "evidence.yml",
                _public_release_evidence(),
            )
            (root / "agent" / "context-packs" / "T-013-task.md").unlink()

            payload = _run_json(root, ["maturity", "status", "--json"])

            checks = {check["id"]: check for check in payload["checks"]}
            self.assertEqual(checks["task_context_pack"]["status"], "missing")
            self.assertEqual(checks["allowed_paths"]["status"], "missing")
            self.assertEqual(checks["review_evidence"]["status"], "passed")
            self.assertEqual(checks["test_evidence"]["status"], "passed")

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


def _seed_governed_project(root: Path) -> None:
    (root / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    write_data(root / ".agentspec" / "config.yml", {"schema": "agentspec.config.v1"})
    write_data(root / "agent" / "maturity.yml", {"schema": "agentspec.maturity.v1", "level": "governed-implementation", "enforcement": "warn"})
    write_data(root / "docs" / "traceability" / "requirements.yml", [])
    (root / "docs" / "designs").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "designs" / "README.md").write_text("# Designs\n", encoding="utf-8")
    pack = root / "agent" / "context-packs" / "T-013-task.md"
    pack.parent.mkdir(parents=True, exist_ok=True)
    pack.write_text("# T-013: Task\n\n## Allowed Paths\n\n- `agentspec/maturity.py`\n", encoding="utf-8")
    (root / "agent" / "sessions" / "active").mkdir(parents=True, exist_ok=True)
    (root / "agent" / "sessions" / "archived").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "drift").mkdir(parents=True, exist_ok=True)
    (root / "reports" / "drift" / "latest.md").write_text("# Drift\n", encoding="utf-8")


def _public_release_evidence(
    *,
    verdict: str = "ready",
    review_id: str = "REVIEW-0001",
) -> dict:
    context_pack = "agent/context-packs/T-013-task.md"
    return {
        "schema": "agentspec.release_evidence.v0",
        "updated_at": "2026-06-29T00:00:00Z",
        "tasks": {
            context_pack: {
                "task_id": "T-013",
                "context_pack": context_pack,
                "status": "complete",
                "run_id": "complete-t013",
                "verification": {"status": "passed"},
                "code_review": {"id": review_id, "verdict": verdict},
                "updated_at": "2026-06-29T00:00:00Z",
            }
        },
    }


if __name__ == "__main__":
    unittest.main()
