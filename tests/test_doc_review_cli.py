import contextlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentspec import review as review_module
from agentspec.cli import main


def _write_dcr(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# DCR-0099: Test document review

| Field | Value |
|---|---|
| Status | accepted |
| Classification | implement-now |
| Submitted | 2026-05-11 |
| Submitted by | tester |
| Decided by | tester |
| Decided on | 2026-05-11 |
| Confidence | medium |

## Summary

Test summary.

## Motivation

Test motivation.

## Proposed Change

Test change.

## Acceptance Criteria

- Test acceptance.
""",
        encoding="utf-8",
    )


def _run_cli(root: Path, argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(["--root", str(root), *argv])
    return code, stdout.getvalue(), stderr.getvalue()


class DocumentReviewCLITests(unittest.TestCase):
    def test_deterministic_review_writes_doc_review_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)

            code, stdout, _ = _run_cli(
                root,
                ["review", "doc", "docs/change-requests/DCR-0099-test.md", "--mode", "deterministic", "--json"],
            )

            self.assertEqual(code, 0)
            payload = json.loads(stdout)
            self.assertEqual(payload["schema"], "agentspec.doc_review.v0")
            self.assertEqual(payload["artifact_path"], "docs/change-requests/DCR-0099-test.md")
            self.assertEqual(payload["artifact_kind"], "dcr")
            self.assertEqual(payload["verdict"], "ready")
            self.assertEqual(payload["reviewer"], "deterministic")
            self.assertIn("DCR-0099", payload["dcr_refs"])
            self.assertTrue(payload["artifact_digest"].startswith("sha256:"))

            review_path = root / "agent" / "doc-reviews" / f"{payload['id']}.yml"
            stored = json.loads(review_path.read_text(encoding="utf-8"))
            self.assertEqual(stored["id"], payload["id"])
            self.assertEqual(stored["normalized_artifact_digest"], payload["normalized_artifact_digest"])

    def test_review_doc_warns_when_review_artifact_is_gitignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text("/agent/\n", encoding="utf-8")
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)

            code, stdout, _ = _run_cli(
                root,
                ["review", "doc", "docs/change-requests/DCR-0099-test.md", "--mode", "deterministic"],
            )

            self.assertEqual(code, 0)
            self.assertIn("Recorded document review DOCREVIEW-0001 (ready).", stdout)
            self.assertIn("Preserve: git add -f -- agent/doc-reviews/DOCREVIEW-0001.yml", stdout)

    def test_review_doc_retries_when_allocated_id_collides(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)
            original_write = review_module._write_data_exclusive
            collided = False

            def collide_once(path: Path, data: object) -> None:
                nonlocal collided
                if not collided:
                    collided = True
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text('{"schema": "collision"}\n', encoding="utf-8")
                    raise FileExistsError(path)
                original_write(path, data)

            with mock.patch.object(review_module, "_write_data_exclusive", side_effect=collide_once):
                code, stdout, _ = _run_cli(
                    root,
                    ["review", "doc", "docs/change-requests/DCR-0099-test.md", "--mode", "deterministic", "--json"],
                )

            self.assertEqual(code, 0)
            payload = json.loads(stdout)
            self.assertEqual(payload["id"], "DOCREVIEW-0002")
            self.assertTrue((root / "agent" / "doc-reviews" / "DOCREVIEW-0001.yml").exists())
            stored = json.loads((root / "agent" / "doc-reviews" / "DOCREVIEW-0002.yml").read_text(encoding="utf-8"))
            self.assertEqual(stored["id"], "DOCREVIEW-0002")

    def test_manual_ready_verdict_and_check_current(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)

            code, stdout, _ = _run_cli(
                root,
                [
                    "review",
                    "doc",
                    "docs/change-requests/DCR-0099-test.md",
                    "--verdict",
                    "ready",
                    "--reviewer",
                    "human",
                    "--summary",
                    "No blocking findings.",
                    "--json",
                ],
            )
            self.assertEqual(code, 0)
            review_payload = json.loads(stdout)
            self.assertEqual(review_payload["verdict"], "ready")
            self.assertEqual(review_payload["reviewer"], "human")

            code, stdout, _ = _run_cli(
                root,
                ["review", "doc", "--check", "docs/change-requests/DCR-0099-test.md", "--json"],
            )

            self.assertEqual(code, 0)
            check_payload = json.loads(stdout)
            self.assertEqual(check_payload["readiness"], "current")
            self.assertTrue(check_payload["current"])
            self.assertEqual(check_payload["latest_review"]["id"], review_payload["id"])
            self.assertEqual(list((root / "agent" / "doc-reviews").glob("DOCREVIEW-*.yml")), [root / "agent" / "doc-reviews" / f"{review_payload['id']}.yml"])

    def test_check_marks_material_edit_stale(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)
            self.assertEqual(
                _run_cli(
                    root,
                    [
                        "review",
                        "doc",
                        "docs/change-requests/DCR-0099-test.md",
                        "--verdict",
                        "ready",
                        "--reviewer",
                        "human",
                        "--summary",
                        "Ready.",
                    ],
                )[0],
                0,
            )
            artifact.write_text(
                artifact.read_text(encoding="utf-8") + "\nMaterial new paragraph.\n",
                encoding="utf-8",
            )

            code, stdout, _ = _run_cli(
                root,
                ["review", "doc", "--check", "docs/change-requests/DCR-0099-test.md", "--json"],
            )

            self.assertEqual(code, 0)
            payload = json.loads(stdout)
            self.assertEqual(payload["readiness"], "stale")
            self.assertFalse(payload["current"])

    def test_check_accepts_normalized_whitespace_only_change(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)
            self.assertEqual(
                _run_cli(
                    root,
                    [
                        "review",
                        "doc",
                        "docs/change-requests/DCR-0099-test.md",
                        "--verdict",
                        "ready",
                        "--reviewer",
                        "human",
                        "--summary",
                        "Ready.",
                    ],
                )[0],
                0,
            )
            artifact.write_text(
                "\n".join(line + "  " for line in artifact.read_text(encoding="utf-8").splitlines()) + "\n",
                encoding="utf-8",
            )

            code, stdout, _ = _run_cli(
                root,
                ["review", "doc", "--check", "docs/change-requests/DCR-0099-test.md", "--json"],
            )

            self.assertEqual(code, 0)
            payload = json.loads(stdout)
            self.assertEqual(payload["readiness"], "current")
            self.assertTrue(payload["current"])

    def test_ambiguous_mode_and_verdict_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)

            code, stdout, _ = _run_cli(
                root,
                [
                    "review",
                    "doc",
                    "docs/change-requests/DCR-0099-test.md",
                    "--mode",
                    "model",
                    "--verdict",
                    "ready",
                    "--reviewer",
                    "human",
                    "--summary",
                    "Ready.",
                    "--json",
                ],
            )

            self.assertEqual(code, 1)
            payload = json.loads(stdout)
            self.assertIn("exactly one", payload["error"]["message"])
            self.assertEqual(list((root / "agent" / "doc-reviews").glob("DOCREVIEW-*.yml")), [])

    def test_check_and_mode_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)

            code, stdout, _ = _run_cli(
                root,
                [
                    "review",
                    "doc",
                    "--check",
                    "docs/change-requests/DCR-0099-test.md",
                    "--mode",
                    "deterministic",
                    "--json",
                ],
            )

            self.assertEqual(code, 1)
            payload = json.loads(stdout)
            self.assertIn("exactly one", payload["error"]["message"])

    def test_manual_verdict_requires_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            artifact = root / "docs" / "change-requests" / "DCR-0099-test.md"
            _write_dcr(artifact)

            code, stdout, _ = _run_cli(
                root,
                [
                    "review",
                    "doc",
                    "docs/change-requests/DCR-0099-test.md",
                    "--verdict",
                    "ready",
                    "--reviewer",
                    "human",
                    "--json",
                ],
            )

            self.assertEqual(code, 1)
            payload = json.loads(stdout)
            self.assertIn("summary", payload["error"]["message"].lower())

    def test_deterministic_workflow_review_reports_missing_scope(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            workflow = root / "agent" / "workflows" / "W-001-test.md"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text("# Workflow W-001: Test\n", encoding="utf-8")

            code, stdout, _ = _run_cli(
                root,
                ["review", "doc", "agent/workflows/W-001-test.md", "--mode", "deterministic", "--json"],
            )

            self.assertEqual(code, 0)
            payload = json.loads(stdout)
            self.assertEqual(payload["artifact_kind"], "workflow")
            self.assertEqual(payload["verdict"], "revise")
            issues = {finding["issue"] for finding in payload["findings"]}
            self.assertIn("Workflow allowed paths are missing.", issues)
            self.assertIn("Workflow verification commands are missing.", issues)


if __name__ == "__main__":
    unittest.main()
