import contextlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agentspec.cli import main
from agentspec.io import load_data
from agentspec import session as session_module


class SessionCliTests(unittest.TestCase):
    def test_session_lifecycle_start_list_inspect_finish(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pack(root, "T-001-demo.md")

            start_payload = _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-001",
                    "--owner",
                    "codex",
                    "--branch",
                    "feature/demo",
                    "--worktree",
                    "../demo-worktree",
                    "--session-id",
                    "S-demo",
                    "--json",
                ],
            )

            self.assertEqual(start_payload["schema"], "agentspec.session_lease.v0")
            self.assertEqual(start_payload["session_id"], "S-demo")
            self.assertEqual(start_payload["status"], "active")
            self.assertEqual(start_payload["mode"], "owner")
            self.assertEqual(start_payload["owner"], "codex")
            self.assertEqual(start_payload["context_pack"], "agent/context-packs/T-001-demo.md")
            self.assertEqual(start_payload["task_id"], "T-001")
            self.assertEqual(start_payload["requirements"], ["R-001"])
            self.assertEqual(start_payload["allowed_paths"], ["agentspec/session.py", "tests/test_session_cli.py"])
            self.assertEqual(start_payload["branch"], "feature/demo")
            self.assertEqual(start_payload["worktree"], "../demo-worktree")
            self.assertTrue((root / "agent" / "sessions" / "active" / "S-demo.yml").exists())

            list_payload = _run_json(root, ["session", "list", "--json"])
            self.assertEqual(list_payload["schema"], "agentspec.session_list.v0")
            self.assertEqual(list_payload["counts"], {"active": 1, "archived": 0})
            self.assertEqual(list_payload["active"][0]["session_id"], "S-demo")

            inspect_payload = _run_json(root, ["session", "inspect", "S-demo", "--json"])
            self.assertEqual(inspect_payload["session_id"], "S-demo")
            self.assertEqual(inspect_payload["path"], "agent/sessions/active/S-demo.yml")

            finish_payload = _run_json(
                root,
                [
                    "session",
                    "finish",
                    "S-demo",
                    "--disposition",
                    "keep",
                    "--test-status",
                    "passed",
                    "--review",
                    "REVIEW-0001",
                    "--json",
                ],
            )

            self.assertEqual(finish_payload["status"], "finished")
            self.assertTrue(finish_payload["terminal"])
            self.assertEqual(finish_payload["disposition"], "keep")
            self.assertEqual(finish_payload["test_status"], "passed")
            self.assertEqual(finish_payload["review_id"], "REVIEW-0001")
            self.assertFalse((root / "agent" / "sessions" / "active" / "S-demo.yml").exists())
            archived_path = root / "agent" / "sessions" / "archived" / "S-demo.yml"
            self.assertTrue(archived_path.exists())
            archived = load_data(archived_path)
            self.assertEqual(archived["status"], "finished")

            list_after_finish = _run_json(root, ["session", "list", "--json"])
            self.assertEqual(list_after_finish["counts"], {"active": 0, "archived": 1})
            self.assertEqual(list_after_finish["archived"][0]["session_id"], "S-demo")

    def test_session_release_archives_without_review_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pack(root, "T-002-release.md")

            _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "agent/context-packs/T-002-release.md",
                    "--mode",
                    "observer",
                    "--session-id",
                    "S-release",
                    "--json",
                ],
            )
            release_payload = _run_json(
                root,
                [
                    "session",
                    "release",
                    "S-release",
                    "--reason",
                    "handoff to another agent",
                    "--json",
                ],
            )

            self.assertEqual(release_payload["status"], "released")
            self.assertTrue(release_payload["terminal"])
            self.assertEqual(release_payload["release_reason"], "handoff to another agent")
            self.assertFalse((root / "agent" / "sessions" / "active" / "S-release.yml").exists())
            self.assertTrue((root / "agent" / "sessions" / "archived" / "S-release.yml").exists())

    def test_status_reports_active_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pack(root, "T-003-status.md")
            _run_json(root, ["session", "start", "--task", "T-003", "--session-id", "S-status", "--json"])

            status_payload = _run_json(root, ["status", "--json"])

            self.assertIn("sessions", status_payload)
            self.assertEqual(status_payload["sessions"]["counts"], {"active": 1, "archived": 0})
            self.assertEqual(status_payload["sessions"]["active"][0]["session_id"], "S-status")
            self.assertEqual(
                status_payload["sessions"]["active"][0]["context_pack"],
                "agent/context-packs/T-003-status.md",
            )

    def test_default_session_ids_are_unique_when_timestamp_matches(self) -> None:
        class FixedDatetime:
            @classmethod
            def now(cls, tz: timezone | None = None) -> datetime:
                return datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(session_module, "datetime", FixedDatetime):
                first = session_module._default_session_id(root, "T-004")
                second = session_module._default_session_id(root, "T-004")

            self.assertNotEqual(first, second)
            self.assertRegex(first, r"^S-20260510T120000000000Z-t-004-[a-f0-9]{8}$")
            self.assertRegex(second, r"^S-20260510T120000000000Z-t-004-[a-f0-9]{8}$")

    def test_session_record_write_preserves_existing_file_on_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "agent" / "sessions" / "active" / "S-collision.yml"
            existing = {
                "schema": "agentspec.session_lease.v0",
                "session_id": "S-collision",
                "status": "active",
                "owner": "first",
            }
            replacement = {
                "schema": "agentspec.session_lease.v0",
                "session_id": "S-collision",
                "status": "active",
                "owner": "second",
            }

            session_module._write_new_session(path, existing)
            with self.assertRaises(FileExistsError):
                session_module._write_new_session(path, replacement)

            self.assertEqual(load_data(path)["owner"], "first")


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


def _write_pack(root: Path, name: str) -> None:
    path = root / "agent" / "context-packs" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    task_id = name.split("-", 2)[0] + "-" + name.split("-", 2)[1]
    path.write_text(
        f"""# {task_id}: Demo Session Task

Type: `implementation`
Originating DCR: `DCR-0001`

## Requirements

- `R-001` Demo requirement

## Allowed Paths

- `agentspec/session.py`
- `tests/test_session_cli.py`
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
