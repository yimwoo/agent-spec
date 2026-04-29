"""Tests for `aspec dogfood record` — optional CLI from R-139."""

import contextlib
import os
import re
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import main


@contextlib.contextmanager
def pushd(path: Path):
    old = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old)


class DogfoodRecordTests(unittest.TestCase):
    def test_dogfood_record_writes_stub(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "reports" / "dogfood").mkdir(parents=True)
            with pushd(root):
                rc = main([
                    "dogfood", "record",
                    "--title", "Pilot run on agentracing",
                    "--slug", "agentracing-pilot",
                ])
            self.assertEqual(rc, 0)

            files = list((root / "reports" / "dogfood").glob("*-agentracing-pilot.md"))
            self.assertEqual(len(files), 1, f"expected one file, got: {files}")

            text = files[0].read_text(encoding="utf-8")
            self.assertIn("Pilot run on agentracing", text)
            # Filename starts with an ISO date.
            self.assertTrue(re.match(r"^\d{4}-\d{2}-\d{2}-", files[0].name))


if __name__ == "__main__":
    unittest.main()
