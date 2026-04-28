import io
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import build_parser, main


class CliAliasTests(unittest.TestCase):
    def test_pyproject_exposes_long_and_short_console_scripts(self) -> None:
        data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

        scripts = data["project"]["scripts"]
        self.assertEqual(scripts["agentspec"], "agentspec.cli:main")
        self.assertEqual(scripts["aspec"], "agentspec.cli:main")

    def test_parser_can_render_aspec_usage(self) -> None:
        parser = build_parser(prog="aspec")

        self.assertIn("usage: aspec", parser.format_help())

    def test_main_accepts_aspec_prog_override(self) -> None:
        output = io.StringIO()

        with redirect_stdout(output):
            with self.assertRaises(SystemExit) as exit_context:
                main(["--help"], prog="aspec")

        self.assertEqual(exit_context.exception.code, 0)
        self.assertIn("usage: aspec", output.getvalue())
