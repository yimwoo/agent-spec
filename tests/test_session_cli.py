import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from agentspec.cli import main
from agentspec.io import load_data, write_data
from agentspec import session as session_module
from agentspec.session import build_session_preflight


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

    def test_session_status_marks_cleanup_eligible_after_merge_and_clean_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, worktree = _seed_cleanup_git_repo(Path(temp_dir), "feature/cleanup")
            pack = _write_pack(root, "T-013-cleanup.md")
            _write_task_closure(root, pack, "REVIEW-0001")
            _finish_cleanup_session(root, worktree, "S-cleanup", disposition="merge")

            list_payload = _run_json(root, ["session", "list", "--json"])
            archived = list_payload["archived"][0]
            eligibility = archived["cleanup_eligibility"]

            self.assertTrue(eligibility["eligible"])
            self.assertEqual(eligibility["status"], "eligible")
            self.assertEqual(eligibility["reasons"], [])
            self.assertEqual(eligibility["closures"]["task"]["status"], "closed")
            self.assertEqual(eligibility["closures"]["delivery"]["status"], "closed")
            self.assertEqual(eligibility["closures"]["local_resources"]["status"], "eligible")
            self.assertEqual(eligibility["resources"]["worktree"]["status"], "eligible")
            self.assertEqual(eligibility["resources"]["branch"]["status"], "eligible_after_worktree")
            self.assertIn("remove_worktree_first", eligibility["resources"]["branch"]["reasons"])
            self.assertEqual(list_payload["cleanup"]["counts"]["eligible"], 1)
            self.assertEqual(list_payload["cleanup"]["eligible"][0]["session_id"], "S-cleanup")

    def test_session_status_marks_keep_disposition_as_not_cleanup_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, worktree = _seed_cleanup_git_repo(Path(temp_dir), "feature/keep")
            pack = _write_pack(root, "T-014-keep.md")
            _write_task_closure(root, pack, "REVIEW-0001")
            _finish_cleanup_session(root, worktree, "S-keep", task="T-014", disposition="keep")

            list_payload = _run_json(root, ["session", "list", "--json"])
            eligibility = list_payload["archived"][0]["cleanup_eligibility"]

            self.assertFalse(eligibility["eligible"])
            self.assertEqual(eligibility["status"], "kept")
            self.assertIn("disposition_keep", eligibility["reasons"])
            self.assertEqual(eligibility["closures"]["delivery"]["status"], "kept")

    def test_session_status_blocks_cleanup_when_active_write_session_uses_same_resources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, worktree = _seed_cleanup_git_repo(Path(temp_dir), "feature/active-block")
            pack = _write_pack(root, "T-015-active-block.md")
            _write_task_closure(root, pack, "REVIEW-0001")
            _finish_cleanup_session(root, worktree, "S-finished", task="T-015", disposition="merge")
            _write_pack(root, "T-016-active.md")

            _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-016",
                    "--owner",
                    "codex",
                    "--branch",
                    "feature/active-block",
                    "--worktree",
                    str(worktree),
                    "--session-id",
                    "S-active",
                    "--json",
                ],
            )

            list_payload = _run_json(root, ["session", "list", "--json"])
            finished = next(record for record in list_payload["archived"] if record["session_id"] == "S-finished")
            eligibility = finished["cleanup_eligibility"]

            self.assertFalse(eligibility["eligible"])
            self.assertEqual(eligibility["status"], "blocked")
            self.assertIn("active_session_same_branch", eligibility["reasons"])
            self.assertIn("active_session_same_worktree", eligibility["reasons"])

    def test_session_status_blocks_cleanup_for_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, worktree = _seed_cleanup_git_repo(Path(temp_dir), "feature/dirty")
            pack = _write_pack(root, "T-017-dirty.md")
            _write_task_closure(root, pack, "REVIEW-0001")
            (worktree / "untracked.txt").write_text("dirty\n", encoding="utf-8")
            _finish_cleanup_session(root, worktree, "S-dirty", task="T-017", disposition="merge")

            list_payload = _run_json(root, ["session", "list", "--json"])
            eligibility = list_payload["archived"][0]["cleanup_eligibility"]

            self.assertFalse(eligibility["eligible"])
            self.assertEqual(eligibility["status"], "blocked")
            self.assertIn("worktree_dirty", eligibility["reasons"])
            self.assertIn("worktree:worktree_dirty", eligibility["reasons"])
            self.assertEqual(eligibility["resources"]["worktree"]["status"], "blocked")

    def test_session_status_blocks_cleanup_when_worktree_status_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = _seed_merged_branch_repo(Path(temp_dir), "feature/nongit")
            nongit_worktree = Path(temp_dir) / "not-a-git-worktree"
            nongit_worktree.mkdir()
            pack = _write_pack(root, "T-018-nongit.md")
            _write_task_closure(root, pack, "REVIEW-0001")
            _finish_cleanup_session(
                root,
                nongit_worktree,
                "S-nongit",
                task="T-018",
                disposition="merge",
                branch="feature/nongit",
            )

            list_payload = _run_json(root, ["session", "list", "--json"])
            eligibility = list_payload["archived"][0]["cleanup_eligibility"]

            self.assertFalse(eligibility["eligible"])
            self.assertEqual(eligibility["status"], "blocked")
            self.assertIn("worktree:worktree_status_unavailable", eligibility["reasons"])
            self.assertEqual(eligibility["resources"]["worktree"]["status"], "blocked")
            self.assertEqual(
                eligibility["resources"]["worktree"]["reasons"],
                ["worktree_status_unavailable"],
            )

    def test_session_status_blocks_cleanup_when_worktree_status_times_out(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, worktree = _seed_cleanup_git_repo(Path(temp_dir), "feature/timeout")
            pack = _write_pack(root, "T-018-timeout.md")
            _write_task_closure(root, pack, "REVIEW-0001")
            _finish_cleanup_session(root, worktree, "S-timeout", task="T-018", disposition="merge")

            original_run = subprocess.run
            worktree_root = str(worktree.resolve())

            def status_timeout(command: list[str], *args: object, **kwargs: object) -> subprocess.CompletedProcess:
                if command == ["git", "-C", worktree_root, "status", "--porcelain"]:
                    raise subprocess.TimeoutExpired(command, timeout=kwargs.get("timeout"))
                return original_run(command, *args, **kwargs)

            with patch.object(session_module.subprocess, "run", side_effect=status_timeout):
                list_payload = _run_json(root, ["session", "list", "--json"])

            eligibility = list_payload["archived"][0]["cleanup_eligibility"]

            self.assertFalse(eligibility["eligible"])
            self.assertEqual(eligibility["status"], "blocked")
            self.assertIn("worktree:worktree_status_unavailable", eligibility["reasons"])

    def test_session_status_blocks_cleanup_for_released_session(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, worktree = _seed_cleanup_git_repo(Path(temp_dir), "feature/release")
            _write_pack(root, "T-018-release-cleanup.md")
            _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-018",
                    "--owner",
                    "codex",
                    "--branch",
                    "feature/release",
                    "--worktree",
                    str(worktree),
                    "--session-id",
                    "S-release-cleanup",
                    "--json",
                ],
            )
            _run_json(root, ["session", "release", "S-release-cleanup", "--reason", "handoff", "--json"])

            list_payload = _run_json(root, ["session", "list", "--json"])
            eligibility = list_payload["archived"][0]["cleanup_eligibility"]

            self.assertFalse(eligibility["eligible"])
            self.assertEqual(eligibility["status"], "released")
            self.assertIn("released_without_delivery_closure", eligibility["reasons"])
            self.assertIn("released_without_task_closure", eligibility["reasons"])

    def test_session_status_blocks_cleanup_without_task_writeback_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root, worktree = _seed_cleanup_git_repo(Path(temp_dir), "feature/missing-evidence")
            _write_pack(root, "T-019-missing-evidence.md")
            _finish_cleanup_session(root, worktree, "S-missing-evidence", task="T-019", disposition="merge")

            list_payload = _run_json(root, ["session", "list", "--json"])
            eligibility = list_payload["archived"][0]["cleanup_eligibility"]

            self.assertFalse(eligibility["eligible"])
            self.assertEqual(eligibility["status"], "blocked")
            self.assertIn("task_writeback_missing", eligibility["reasons"])
            self.assertEqual(eligibility["closures"]["task"]["status"], "blocked")

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

    def test_session_start_infers_git_branch_and_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_git_repo(root, "codex/session-a")
            _write_pack(root, "T-005-git-context.md")

            start_payload = _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-005",
                    "--owner",
                    "codex",
                    "--session-id",
                    "S-inferred",
                    "--json",
                ],
            )

            self.assertEqual(start_payload["branch"], "codex/session-a")
            self.assertEqual(start_payload["worktree"], str(root.resolve()))

    def test_session_start_rejects_parallel_write_lease_on_same_branch_or_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pack(root, "T-006-first.md")
            _write_pack(root, "T-007-second.md")

            _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-006",
                    "--owner",
                    "codex",
                    "--branch",
                    "feature/shared",
                    "--worktree",
                    "../shared",
                    "--session-id",
                    "S-first",
                    "--json",
                ],
            )

            conflict = _run_json_error(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-007",
                    "--owner",
                    "codex",
                    "--branch",
                    "feature/shared",
                    "--worktree",
                    "../other",
                    "--session-id",
                    "S-conflict",
                    "--json",
                ],
            )

            self.assertEqual(conflict["error"]["type"], "ValueError")
            self.assertIn("already leases branch feature/shared", conflict["error"]["message"])
            self.assertFalse((root / "agent" / "sessions" / "active" / "S-conflict.yml").exists())

            observer = _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-007",
                    "--mode",
                    "observer",
                    "--branch",
                    "feature/shared",
                    "--worktree",
                    "../shared",
                    "--session-id",
                    "S-observer",
                    "--json",
                ],
            )
            self.assertEqual(observer["status"], "active")
            self.assertEqual(observer["mode"], "observer")

            shared = _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-007",
                    "--branch",
                    "feature/shared",
                    "--worktree",
                    "../shared",
                    "--allow-shared",
                    "--session-id",
                    "S-shared",
                    "--json",
                ],
            )
            self.assertEqual(shared["status"], "active")

    def test_simultaneous_owner_starts_do_not_share_write_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pack(root, "T-008-race.md")

            base = [
                sys.executable,
                "-m",
                "agentspec.cli",
                "--root",
                str(root),
                "session",
                "start",
                "--task",
                "T-008",
                "--mode",
                "owner",
                "--branch",
                "feature/race",
                "--worktree",
                str(root / "race-worktree"),
                "--json",
            ]
            env = _subprocess_env()
            first = subprocess.Popen(
                [*base, "--owner", "first", "--session-id", "S-race-first"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            second = subprocess.Popen(
                [*base, "--owner", "second", "--session-id", "S-race-second"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            first_stdout, _first_stderr = first.communicate()
            second_stdout, _second_stderr = second.communicate()

            results = [
                (first.returncode, json.loads(first_stdout)),
                (second.returncode, json.loads(second_stdout)),
            ]
            self.assertEqual([0, 1], sorted(returncode for returncode, _payload in results))
            conflict_payload = next(payload for returncode, payload in results if returncode == 1)
            self.assertEqual(conflict_payload["error"]["type"], "ValueError")
            self.assertIn("already leases branch feature/race", conflict_payload["error"]["message"])

            list_payload = _run_json(root, ["session", "list", "--json"])
            owner_sessions = [record for record in list_payload["active"] if record["mode"] == "owner"]
            self.assertEqual(1, len(owner_sessions))

    def test_session_start_clears_stale_start_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pack(root, "T-009-stale-lock.md")
            lock_path = root / "agent" / "sessions" / "active" / ".session-start.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path.write_text("12345\n", encoding="utf-8")

            with patch.object(session_module, "_process_exists", return_value=False):
                start_payload = _run_json(
                    root,
                    [
                        "session",
                        "start",
                        "--task",
                        "T-009",
                        "--owner",
                        "codex",
                        "--session-id",
                        "S-stale-lock",
                        "--json",
                    ],
                )

            self.assertEqual(start_payload["status"], "active")
            self.assertFalse(lock_path.exists())

    def test_session_preflight_requires_active_write_lease_with_branch_and_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pack(root, "T-010-preflight.md")

            missing = build_session_preflight(root, task_selector="T-010")

            self.assertEqual(missing["status"], "missing")
            self.assertTrue(missing["required"])
            self.assertIn("session start", missing["recommended_command"])

            _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-010",
                    "--mode",
                    "observer",
                    "--branch",
                    "feature/preflight",
                    "--worktree",
                    str(root),
                    "--session-id",
                    "S-observer-preflight",
                    "--json",
                ],
            )

            observer_only = build_session_preflight(root, task_selector="T-010")
            self.assertEqual(observer_only["status"], "missing")

            _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-010",
                    "--owner",
                    "codex",
                    "--branch",
                    "feature/preflight-owner",
                    "--worktree",
                    str(root / "owner-worktree"),
                    "--session-id",
                    "S-owner-preflight",
                    "--json",
                ],
            )

            satisfied = build_session_preflight(root, task_selector="T-010")
            self.assertEqual(satisfied["status"], "satisfied")
            self.assertEqual(satisfied["active_session"]["session_id"], "S-owner-preflight")
            self.assertEqual(satisfied["active_session"]["branch"], "feature/preflight-owner")

    def test_session_preflight_refreshes_changed_context_pack_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = _write_pack(root, "T-010-refresh.md")
            _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-010",
                    "--owner",
                    "codex",
                    "--branch",
                    "feature/refresh",
                    "--worktree",
                    str(root / "refresh-worktree"),
                    "--session-id",
                    "S-refresh",
                    "--json",
                ],
            )
            original = load_data(root / "agent" / "sessions" / "active" / "S-refresh.yml")

            _append_allowed_path(pack, "docs/traceability/requirements.yml")
            refreshed = build_session_preflight(root, task_selector="T-010")

            active = refreshed["active_session"]
            self.assertEqual(refreshed["status"], "satisfied")
            self.assertIn("docs/traceability/requirements.yml", active["allowed_paths"])
            self.assertNotEqual(original["context_pack_sha256"], active["context_pack_sha256"])
            self.assertEqual(active["context_pack_original_sha256"], original["context_pack_sha256"])
            self.assertEqual(active["allowed_paths_original"], original["allowed_paths"])
            self.assertEqual(active["history"][-1]["action"], "context_pack_refreshed")

            persisted = load_data(root / "agent" / "sessions" / "active" / "S-refresh.yml")
            self.assertEqual(persisted["allowed_paths"], active["allowed_paths"])

    def test_session_finish_refreshes_changed_context_pack_metadata_before_archiving(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = _write_pack(root, "T-010-finish-refresh.md")
            _run_json(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-010",
                    "--owner",
                    "codex",
                    "--branch",
                    "feature/finish-refresh",
                    "--worktree",
                    str(root / "finish-refresh-worktree"),
                    "--session-id",
                    "S-finish-refresh",
                    "--json",
                ],
            )
            original = load_data(root / "agent" / "sessions" / "active" / "S-finish-refresh.yml")
            _append_allowed_path(pack, "docs/traceability/requirements.yml")

            finished = _run_json(
                root,
                [
                    "session",
                    "finish",
                    "S-finish-refresh",
                    "--disposition",
                    "keep",
                    "--json",
                ],
            )

            self.assertIn("docs/traceability/requirements.yml", finished["allowed_paths"])
            self.assertEqual(finished["context_pack_original_sha256"], original["context_pack_sha256"])
            self.assertEqual(finished["allowed_paths_original"], original["allowed_paths"])
            self.assertEqual(finished["history"][-2]["action"], "context_pack_refreshed")

    def test_session_preflight_blocks_protected_implementation_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = _write_pack(root, "T-010-main-branch.md")
            text = pack.read_text(encoding="utf-8")
            pack.write_text(text.replace("Type: `implementation`", "Type: `implementation`\nBranch: `main`"), encoding="utf-8")

            blocked = build_session_preflight(root, task_selector="T-010")

            self.assertEqual(blocked["status"], "blocked")
            self.assertEqual(blocked["blocker"]["type"], "protected_branch")
            self.assertIn("protected branch", blocked["message"])
            self.assertIn("--branch codex/t-010-implementation", blocked["recommended_command"])

    def test_session_start_rejects_protected_implementation_branch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_pack(root, "T-010-start-main.md")

            payload = _run_json_error(
                root,
                [
                    "session",
                    "start",
                    "--task",
                    "T-010",
                    "--owner",
                    "codex",
                    "--branch",
                    "main",
                    "--worktree",
                    str(root),
                    "--session-id",
                    "S-main-blocked",
                    "--json",
                ],
            )

            self.assertEqual(payload["error"]["type"], "ValueError")
            self.assertIn("protected branch", payload["error"]["message"])

    def test_session_preflight_recommends_context_pack_when_task_id_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            selected = _write_pack(root, "T-010-selected-task.md")
            _write_pack(root, "T-010-historical-task.md")

            missing = build_session_preflight(
                root,
                context_pack=str(selected.relative_to(root)),
                task_id="T-010",
            )

            self.assertEqual(missing["status"], "missing")
            self.assertIn(
                "--task agent/context-packs/T-010-selected-task.md",
                missing["recommended_command"],
            )
            self.assertNotIn("--task T-010 ", missing["recommended_command"])

    def test_session_preflight_allows_explicit_host_worktree_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pack = root / "agent" / "context-packs" / "T-011-host-worktree.md"
            pack.parent.mkdir(parents=True, exist_ok=True)
            pack.write_text(
                """# T-011: Host Worktree Escape Hatch

Type: `implementation`
Host Worktree Execution: `explicit`

## Allowed Paths

- `agentspec/session.py`
""",
                encoding="utf-8",
            )

            preflight = build_session_preflight(root, task_selector="T-011")

            self.assertEqual(preflight["status"], "satisfied")
            self.assertEqual(preflight["satisfied_by"], "explicit_host_worktree")
            self.assertEqual(preflight["host_worktree_execution"], "explicit")
            self.assertIsNone(preflight["active_session"])
            self.assertIn("host-worktree", preflight["message"])

    def test_session_preflight_reads_host_worktree_escape_from_linked_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workflow = root / "agent" / "workflows" / "W-011-host-worktree.md"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(
                """---
workflow_id: W-011
branch: feature/workflow-branch
worktree: /tmp/workflow-worktree
host_worktree_execution: explicit
---

# Workflow
""",
                encoding="utf-8",
            )
            pack = root / "agent" / "context-packs" / "T-012-workflow-host.md"
            pack.parent.mkdir(parents=True, exist_ok=True)
            pack.write_text(
                """# T-012: Workflow Host Worktree Escape Hatch

Type: `implementation`
Branch: `unassigned`
Workflow: `agent/workflows/W-011-host-worktree.md`

## Allowed Paths

- `agentspec/session.py`
""",
                encoding="utf-8",
            )

            preflight = build_session_preflight(root, task_selector="T-012")

            self.assertEqual(preflight["status"], "satisfied")
            self.assertEqual(preflight["satisfied_by"], "explicit_host_worktree")
            self.assertEqual(preflight["branch"], "feature/workflow-branch")
            self.assertEqual(preflight["worktree"], "/tmp/workflow-worktree")


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


def _run_json_error(root: Path, args: list[str]) -> dict:
    output = io.StringIO()
    with redirect_stdout(output):
        result = main(["--root", str(root), *args])
    payload = json.loads(output.getvalue())
    if result == 0:
        raise AssertionError(f"Command unexpectedly succeeded: {output.getvalue()}")
    return payload


def _init_git_repo(root: Path, branch: str) -> None:
    subprocess.run(["git", "init"], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    subprocess.run(
        ["git", "checkout", "-b", branch],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def _seed_cleanup_git_repo(base: Path, branch: str) -> tuple[Path, Path]:
    root = _seed_merged_branch_repo(base, branch)
    worktree = base / "cleanup-worktree"
    _git(root, "worktree", "add", str(worktree), branch)
    return root, worktree


def _seed_merged_branch_repo(base: Path, branch: str) -> Path:
    root = base / "repo"
    root.mkdir(parents=True)
    init = subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if init.returncode != 0:
        _git(root, "init")
        _git(root, "checkout", "-b", "main")
    _git(root, "config", "user.email", "agentspec@example.com")
    _git(root, "config", "user.name", "AgentSpec Test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    _git(root, "add", "README.md")
    _git(root, "commit", "-m", "base")
    _git(root, "checkout", "-b", branch)
    (root / "feature.txt").write_text(f"{branch}\n", encoding="utf-8")
    _git(root, "add", "feature.txt")
    _git(root, "commit", "-m", "feature")
    _git(root, "checkout", "main")
    _git(root, "merge", "--no-ff", branch, "-m", f"merge {branch}")
    return root


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )


def _write_task_closure(root: Path, pack: Path, review_id: str) -> None:
    context_pack = str(pack.relative_to(root))
    write_data(
        root / "agent" / "reviews" / f"{review_id}.yml",
        {
            "schema": "agentspec.code_review.v0",
            "id": review_id,
            "task": {"selector": context_pack, "context_pack": context_pack},
            "verdict": "ready",
            "summary": "No blocking findings.",
            "reviewer": "codex",
            "range": "worktree",
            "created_at": "2026-05-12T00:00:00Z",
        },
    )
    write_data(
        root / "agent" / "task-ledger.yml",
        {
            "schema": "agentspec.task_ledger.v0",
            "tasks": {
                context_pack: {
                    "status": "complete",
                    "run_id": f"complete-{pack.stem.split('-', 2)[0].lower()}",
                    "updated_at": "2026-05-12T00:00:00Z",
                    "verification": {"status": "passed"},
                    "code_review": {"id": review_id, "verdict": "ready"},
                }
            },
        },
    )


def _finish_cleanup_session(
    root: Path,
    worktree: Path,
    session_id: str,
    *,
    task: str = "T-013",
    disposition: str,
    branch: str | None = None,
) -> None:
    branch = branch or _git_stdout(root, worktree, "rev-parse", "--abbrev-ref", "HEAD")
    _run_json(
        root,
        [
            "session",
            "start",
            "--task",
            task,
            "--owner",
            "codex",
            "--branch",
            branch,
            "--worktree",
            str(worktree),
            "--session-id",
            session_id,
            "--json",
        ],
    )
    _run_json(
        root,
        [
            "session",
            "finish",
            session_id,
            "--disposition",
            disposition,
            "--test-status",
            "passed",
            "--review",
            "REVIEW-0001",
            "--json",
        ],
    )


def _git_stdout(root: Path, cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    repo_root = str(Path(__file__).resolve().parent.parent)
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = repo_root if not existing else f"{repo_root}{os.pathsep}{existing}"
    return env


def _write_pack(root: Path, name: str) -> Path:
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
    return path


def _append_allowed_path(path: Path, allowed_path: str) -> None:
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            "- `tests/test_session_cli.py`\n",
            f"- `tests/test_session_cli.py`\n- `{allowed_path}`\n",
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
