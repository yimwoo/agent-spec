"""Provider-neutral AgentSpec hook policy and native adapter tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from agentspec.cli import main
from agentspec.hooks import (
    HOOK_DECISION_SCHEMA,
    HOOK_EVALUATION_SCHEMA,
    HOOK_EVIDENCE_SCHEMA,
    evaluate_native_hook,
)
from agentspec.io import write_data


class HookAdapterTests(unittest.TestCase):
    def test_pre_execution_fails_closed_without_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            result = evaluate_native_hook(
                root,
                provider="codex",
                event="pre-execution",
                native_input=_tool_input("Write", {"file_path": "src/app.py"}),
            )

            self.assertEqual(result["schema"], HOOK_EVALUATION_SCHEMA)
            self.assertEqual(result["decision"]["schema"], HOOK_DECISION_SCHEMA)
            self.assertEqual(result["decision"]["outcome"], "deny")
            self.assertIn("missing_session_lease", result["decision"]["flags"])
            native = result["native_output"]["hookSpecificOutput"]
            self.assertEqual(native["permissionDecision"], "deny")
            self.assertEqual(native["hookEventName"], "PreToolUse")
            self.assertTrue(result["evidence"]["recorded"])

    def test_allowed_pre_execution_preserves_host_permission_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_active_session(root, allowed_paths=["src/**"])

            result = evaluate_native_hook(
                root,
                provider="claude",
                event="pre-execution",
                native_input=_tool_input("Edit", {"file_path": str(root / "src" / "app.py")}),
            )

            self.assertEqual(result["decision"]["outcome"], "allow")
            self.assertTrue(result["decision"]["preserves_host_permissions"])
            native = result["native_output"]["hookSpecificOutput"]
            self.assertNotIn("permissionDecision", native)
            self.assertIn("AgentSpec scope check passed", native["additionalContext"])

    def test_out_of_scope_write_returns_scope_expansion_decision(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_active_session(root, allowed_paths=["src/**"])

            result = evaluate_native_hook(
                root,
                provider="codex",
                event="pre-execution",
                native_input=_tool_input("apply_patch", {"patch": "*** Add File: docs/new.md\n+new\n"}),
            )

            decision = result["decision"]
            self.assertEqual(decision["outcome"], "scope_expansion_required")
            self.assertEqual(decision["requested_paths"], ["docs/new.md"])
            self.assertIn("scope_expansion_required", decision["flags"])
            self.assertEqual(
                result["native_output"]["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

    def test_destructive_command_reuses_core_policy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_active_session(root, allowed_paths=["src/**"])

            result = evaluate_native_hook(
                root,
                provider="claude",
                event="pre-execution",
                native_input=_tool_input("Bash", {"command": "git reset --hard HEAD~1"}),
            )

            self.assertEqual(result["decision"]["outcome"], "deny")
            self.assertIn("destructive_git", result["decision"]["flags"])
            self.assertEqual(result["decision"]["policy_source"], "agentspec.policy.evaluate_policy")

    def test_malformed_blocking_input_fails_closed_with_structured_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = evaluate_native_hook(
                Path(td),
                provider="codex",
                event="pre-execution",
                native_input=["not", "an", "object"],
            )

            self.assertEqual(result["decision"]["outcome"], "deny")
            self.assertEqual(result["error"]["schema"], "agentspec.hook_error.v0")
            self.assertEqual(result["error"]["code"], "ASPEC_HOOK_INPUT_INVALID")
            self.assertEqual(
                result["native_output"]["hookSpecificOutput"]["permissionDecision"],
                "deny",
            )

    def test_stop_verification_blocks_completion_without_finish_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            context_pack = _seed_active_session(root, allowed_paths=["src/**"])
            native_input = {
                "hook_event_name": "Stop",
                "session_id": "native-session",
                "completion_requested": True,
            }

            blocked = evaluate_native_hook(
                root,
                provider="claude",
                event="stop-verification",
                native_input=native_input,
            )
            self.assertEqual(blocked["decision"]["outcome"], "deny")
            self.assertEqual(blocked["native_output"]["decision"], "block")
            self.assertIn("verification_evidence_missing", blocked["decision"]["flags"])

            write_data(
                root / "agent" / "task-ledger.yml",
                {
                    "schema": "agentspec.task_ledger.v0",
                    "tasks": {
                        context_pack: {
                            "status": "complete",
                            "run_id": "complete-t001",
                            "verification": {"status": "passed"},
                            "code_review": {"id": "REVIEW-0001", "verdict": "ready"},
                            "updated_at": "2026-06-29T00:00:00Z",
                        }
                    },
                },
            )
            allowed = evaluate_native_hook(
                root,
                provider="claude",
                event="stop-verification",
                native_input=native_input,
            )
            self.assertEqual(allowed["decision"]["outcome"], "allow")
            self.assertEqual(allowed["native_output"], {})

    def test_finish_evidence_records_provenance_without_blocking_host(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_active_session(root, allowed_paths=["src/**"])

            result = evaluate_native_hook(
                root,
                provider="codex",
                event="finish-evidence",
                native_input={
                    **_tool_input("Bash", {"command": "aspec finish T-001 --test-status passed"}),
                    "tool_response": {"exit_code": 0},
                },
            )

            self.assertEqual(result["decision"]["outcome"], "record")
            self.assertEqual(result["native_output"], {})
            self.assertEqual(result["evidence"]["schema"], HOOK_EVIDENCE_SCHEMA)
            evidence_path = root / result["evidence"]["path"]
            entries = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(entries[-1]["provider"], "codex")
            self.assertEqual(entries[-1]["event"], "finish-evidence")
            self.assertEqual(entries[-1]["decision"]["outcome"], "record")

    def test_cli_native_mode_reads_stdin_and_emits_host_decision(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = io.StringIO()
            native_input = _tool_input("Write", {"file_path": "src/app.py"})

            with mock.patch("sys.stdin", io.StringIO(json.dumps(native_input))):
                with redirect_stdout(output):
                    code = main(
                        [
                            "--root",
                            str(root),
                            "hook",
                            "evaluate",
                            "--provider",
                            "codex",
                            "--event",
                            "pre-execution",
                            "--native",
                        ]
                    )

            self.assertEqual(code, 0)
            native = json.loads(output.getvalue())
            self.assertEqual(native["hookSpecificOutput"]["permissionDecision"], "deny")


def _tool_input(tool_name: str, tool_input: dict[str, object]) -> dict[str, object]:
    return {
        "hook_event_name": "PreToolUse",
        "session_id": "native-session",
        "cwd": "/tmp/project",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }


def _seed_active_session(root: Path, *, allowed_paths: list[str]) -> str:
    context_pack = "agent/context-packs/T-001-hook-task.md"
    pack_path = root / context_pack
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    rendered_allowed_paths = "\n".join(f"- `{path}`" for path in allowed_paths)
    pack_path.write_text(
        f"""# T-001: Hook Task

Type: `implementation`

## Requirements

- `R-001` Hook adapters

## Allowed Paths

{rendered_allowed_paths}
""",
        encoding="utf-8",
    )
    write_data(
        root / "agent" / "sessions" / "active" / "S-hook.yml",
        {
            "schema": "agentspec.session_lease.v0",
            "session_id": "S-hook",
            "status": "active",
            "owner": "codex",
            "mode": "owner",
            "context_pack": context_pack,
            "context_pack_title": "Hook Task",
            "task_id": "T-001",
            "task_type": "implementation",
            "requirements": ["R-001"],
            "allowed_paths": allowed_paths,
            "branch": "feature/hook-task",
            "worktree": str(root),
            "created_at": "2026-06-29T00:00:00Z",
            "updated_at": "2026-06-29T00:00:00Z",
        },
    )
    return context_pack


if __name__ == "__main__":
    unittest.main()
