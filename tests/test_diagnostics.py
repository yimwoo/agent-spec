from __future__ import annotations

import io
import json
import logging
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from agentspec.cli import main
from agentspec.diagnostics import configure_diagnostics, get_logger


class DiagnosticsTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_diagnostics({})

    def test_diagnostics_are_disabled_by_default(self) -> None:
        logger = configure_diagnostics({})

        self.assertFalse(logger.handlers)
        self.assertGreaterEqual(logger.level, logging.CRITICAL)

    def test_text_diagnostics_go_to_stderr_when_enabled(self) -> None:
        stream = io.StringIO()
        logger = configure_diagnostics(
            {"ASPEC_LOG_LEVEL": "debug", "ASPEC_LOG_FORMAT": "text"},
            stream=stream,
        )

        logger.debug("debug token sk-proj-AbCdEf123456789012345678")

        output = stream.getvalue()
        self.assertIn("DEBUG agentspec: debug token", output)
        self.assertIn("[REDACTED_CREDENTIAL]", output)
        self.assertNotIn("sk-proj-AbCdEf123456789012345678", output)

    def test_json_diagnostics_are_redacted(self) -> None:
        stream = io.StringIO()
        logger = configure_diagnostics(
            {"ASPEC_LOG_LEVEL": "info", "ASPEC_LOG_FORMAT": "json"},
            stream=stream,
        )

        logger.info("model output included sk-proj-AbCdEf123456789012345678")

        payload = json.loads(stream.getvalue())
        self.assertEqual(payload["schema"], "agentspec.diagnostic_log.v0")
        self.assertEqual(payload["level"], "INFO")
        self.assertEqual(payload["logger"], "agentspec")
        self.assertIn("[REDACTED_CREDENTIAL]", payload["message"])
        self.assertNotIn("sk-proj-AbCdEf123456789012345678", payload["message"])

    def test_log_file_receives_diagnostics_without_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            log_path = Path(td) / "agentspec.log"
            stderr = io.StringIO()

            logger = configure_diagnostics(
                {
                    "ASPEC_LOG_LEVEL": "warning",
                    "ASPEC_LOG_FORMAT": "text",
                    "ASPEC_LOG_FILE": str(log_path),
                },
                stream=stderr,
            )
            logger.warning("stored diagnostic")

            self.assertEqual(stderr.getvalue(), "")
            self.assertIn("stored diagnostic", log_path.read_text(encoding="utf-8"))

    def test_cli_json_stdout_stays_parseable_when_diagnostics_enabled(self) -> None:
        secret = "sk-proj-AbCdEf123456789012345678"
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.dict(
            os.environ,
            {"ASPEC_LOG_LEVEL": "error", "ASPEC_LOG_FORMAT": "json"},
            clear=False,
        ):
            with tempfile.TemporaryDirectory() as td:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = main(
                        [
                            "--root",
                            td,
                            "run",
                            "prompt",
                            secret,
                            "--json",
                        ]
                    )

        self.assertEqual(code, 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["schema"], "agentspec.cli_error.v0")
        diagnostic = json.loads(stderr.getvalue())
        self.assertEqual(diagnostic["schema"], "agentspec.diagnostic_log.v0")
        self.assertIn("[REDACTED_CREDENTIAL]", diagnostic["message"])
        self.assertNotIn(secret, stderr.getvalue())

    def test_package_logger_is_reusable(self) -> None:
        self.assertIs(get_logger(), logging.getLogger("agentspec"))


if __name__ == "__main__":
    unittest.main()
