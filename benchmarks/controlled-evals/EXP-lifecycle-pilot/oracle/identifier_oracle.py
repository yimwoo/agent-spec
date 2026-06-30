"""Hidden deterministic oracle for the controlled lifecycle pilot."""

from __future__ import annotations

import unittest

from identifier import slugify


class SlugifyOracleTests(unittest.TestCase):
    def test_normalizes_common_accented_latin_text(self) -> None:
        self.assertEqual(slugify("Crème Brûlée"), "creme-brulee")
        self.assertEqual(slugify("Málaga déjà vu"), "malaga-deja-vu")

    def test_preserves_ascii_contract(self) -> None:
        self.assertEqual(slugify("API__Version 2"), "api-version-2")
        self.assertEqual(slugify("***", fallback="missing"), "missing")

    def test_non_latin_only_input_uses_fallback(self) -> None:
        self.assertEqual(slugify("東京", fallback="item"), "item")


if __name__ == "__main__":
    unittest.main()
