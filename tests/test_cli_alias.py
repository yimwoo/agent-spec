import importlib
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

    def test_entry_point_targets_resolve_to_callables(self) -> None:
        """Each `[project.scripts]` entry must point at a real callable.

        This catches typos in the spec string without requiring `pip install`.
        """
        data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

        for name, spec in data["project"]["scripts"].items():
            module_name, _, func_name = spec.partition(":")
            self.assertTrue(module_name and func_name, f"{name}: malformed spec {spec!r}")

            module = importlib.import_module(module_name)
            target = getattr(module, func_name, None)
            self.assertTrue(callable(target), f"{name}: {spec} did not resolve to a callable")

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
