"""Public tests for the controlled-evaluation fixture."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from identifier import slugify  # noqa: E402


class SlugifyTests(unittest.TestCase):
    def test_preserves_ascii_behavior(self) -> None:
        self.assertEqual(slugify("Launch Plan 42"), "launch-plan-42")

    def test_collapses_separators_and_uses_fallback(self) -> None:
        self.assertEqual(slugify("  launch___plan  "), "launch-plan")
        self.assertEqual(slugify("---", fallback="untitled"), "untitled")


if __name__ == "__main__":
    unittest.main()
