"""Tests for the structured JSON error envelope (T-042 / agentspec.cli_error.v0).

Closes the P1 finding from the T-040 review: when the user passes
`--json`, the top-level handler should emit a stable structured envelope
to stdout instead of plain stderr text.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from agentspec.cli import (
    CLI_ERROR_SCHEMA,
    _build_error_envelope,
    _is_retryable,
    main,
)


class IsRetryableTests(unittest.TestCase):
    """Unit-test the retryability heuristic without triggering real I/O."""

    def test_timeout_error_is_retryable(self) -> None:
        self.assertTrue(_is_retryable(TimeoutError("upstream slow")))

    def test_connection_error_is_retryable(self) -> None:
        self.assertTrue(_is_retryable(ConnectionError("reset by peer")))

    def test_value_error_is_not_retryable(self) -> None:
        self.assertFalse(_is_retryable(ValueError("bad input")))

    def test_file_not_found_is_not_retryable(self) -> None:
        self.assertFalse(_is_retryable(FileNotFoundError("missing")))

    def test_permission_error_is_not_retryable(self) -> None:
        # Permission errors typically reflect environment/config, not
        # transient network failures. Default to non-retryable.
        self.assertFalse(_is_retryable(PermissionError("perms")))


class BuildErrorEnvelopeTests(unittest.TestCase):
    def test_envelope_shape_for_value_error(self) -> None:
        # Build a fake argparse.Namespace by hand — equivalent to what the
        # real handler sees post-parse_args.
        import argparse

        args = argparse.Namespace(command="run", json=True)
        envelope = _build_error_envelope(ValueError("boom"), "agentspec", args)

        self.assertEqual(envelope["schema"], CLI_ERROR_SCHEMA)
        self.assertEqual(envelope["error"]["type"], "ValueError")
        self.assertEqual(envelope["error"]["message"], "boom")
        self.assertFalse(envelope["error"]["retryable"])
        self.assertEqual(envelope["error"]["command"], "agentspec run")


class CLIJsonErrorEnvelopeTests(unittest.TestCase):
    """End-to-end: invoke a failing command via main() and assert envelope."""

    def test_run_prompt_unknown_id_with_json_emits_envelope(self) -> None:
        """A failing --json command writes a structured envelope to stdout."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "prompt",
                        "no-such-run",
                        "--json",
                    ]
                )

            self.assertEqual(code, 1)
            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["schema"], CLI_ERROR_SCHEMA)
            # We don't pin the exact exception type here — the contract is
            # that `error.type` carries *some* class name and `retryable` is
            # a boolean. This keeps the test resilient to refactors of the
            # underlying run-state lookup.
            self.assertIsInstance(payload["error"]["type"], str)
            self.assertTrue(payload["error"]["type"])  # non-empty
            self.assertIsInstance(payload["error"]["retryable"], bool)
            self.assertEqual(payload["error"]["command"], "agentspec run")
            # Stderr must stay empty for the envelope content — harness
            # consumers parse stdout only.
            self.assertEqual(stderr.getvalue(), "")

    def test_run_prompt_unknown_id_without_json_emits_plain_text(self) -> None:
        """Back-compat: non-JSON callers still get plain stderr text."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = main(
                    ["--root", str(root), "run", "prompt", "no-such-run"]
                )

            self.assertEqual(code, 1)
            # No JSON envelope on stdout.
            self.assertEqual(stdout.getvalue(), "")
            # Plain error string on stderr, current behavior.
            self.assertIn("agentspec: error:", stderr.getvalue())
            self.assertIn("no-such-run", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
