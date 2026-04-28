"""Tests for agentspec.dcr — parsing and classification of DCR documents.

Covers R-121, R-122, R-123 (DCR-0002).
"""

import tempfile
import unittest
from pathlib import Path

from agentspec.dcr import DCRSchemaError, is_implementation_eligible, parse_dcr


VALID_DCR = """# DCR-0099: Test DCR

| Field | Value |
|---|---|
| Status | classified |
| Classification | **implement-now (some commentary)** with required ADR-9999 |
| Submitted | 2026-04-28 |
| Submitted by | tester |
| Decided by | tester |
| Decided on | 2026-04-28 |
| Confidence | high |

## Summary

Body content.
"""


class DCRSchemaTests(unittest.TestCase):
    def _write(self, text: str) -> Path:
        td = tempfile.mkdtemp()
        path = Path(td) / "DCR-0099-test.md"
        path.write_text(text, encoding="utf-8")
        return path

    def test_parse_valid_dcr_returns_canonical_classification(self) -> None:
        dcr = parse_dcr(self._write(VALID_DCR))
        self.assertEqual(dcr["id"], "DCR-0099")
        self.assertEqual(dcr["classification"], "implement-now")
        self.assertEqual(dcr["status"], "classified")
        self.assertEqual(dcr["confidence"], "high")

    def test_unknown_classification_raises(self) -> None:
        text = VALID_DCR.replace("implement-now", "ship-it")
        with self.assertRaises(DCRSchemaError) as ctx:
            parse_dcr(self._write(text))
        self.assertIn("classification", str(ctx.exception).lower())

    def test_missing_required_field_raises(self) -> None:
        # Strip the Classification row entirely.
        text = "\n".join(
            line for line in VALID_DCR.splitlines() if "Classification" not in line
        )
        with self.assertRaises(DCRSchemaError) as ctx:
            parse_dcr(self._write(text))
        self.assertIn("Classification", str(ctx.exception))

    def test_unknown_status_raises(self) -> None:
        text = VALID_DCR.replace("| Status | classified |", "| Status | maybe-someday |")
        with self.assertRaises(DCRSchemaError):
            parse_dcr(self._write(text))

    def test_implement_now_classified_is_eligible(self) -> None:
        dcr = parse_dcr(self._write(VALID_DCR))
        self.assertTrue(is_implementation_eligible(dcr))

    def test_defer_is_not_eligible(self) -> None:
        text = VALID_DCR.replace("implement-now", "defer")
        dcr = parse_dcr(self._write(text))
        self.assertFalse(is_implementation_eligible(dcr))

    def test_spike_is_not_eligible(self) -> None:
        text = VALID_DCR.replace("implement-now", "spike")
        dcr = parse_dcr(self._write(text))
        self.assertFalse(is_implementation_eligible(dcr))

    def test_needs_adr_eligible_only_when_dcr_accepted(self) -> None:
        text = VALID_DCR.replace("implement-now", "needs-adr")
        # Status: classified — NOT eligible until ADR is accepted, which the
        # protocol expresses by promoting the DCR itself to accepted.
        dcr_classified = parse_dcr(self._write(text))
        self.assertFalse(is_implementation_eligible(dcr_classified))

        text_accepted = text.replace("| Status | classified |", "| Status | accepted |")
        dcr_accepted = parse_dcr(self._write(text_accepted))
        self.assertTrue(is_implementation_eligible(dcr_accepted))

    def test_real_repo_dcrs_round_trip(self) -> None:
        """Sanity check: the actual DCRs filed in this repo parse correctly."""
        repo_root = Path(__file__).resolve().parent.parent
        cases = [
            ("DCR-0001-supervised-runs.md", "spike"),
            ("DCR-0002-design-change-management.md", "implement-now"),
            ("DCR-0003-compile-must-preserve-dcr-material.md", "implement-now"),
        ]
        for filename, expected_classification in cases:
            path = repo_root / "docs" / "change-requests" / filename
            if not path.exists():
                self.skipTest(f"{filename} not present in working tree")
            dcr = parse_dcr(path)
            self.assertEqual(
                dcr["classification"],
                expected_classification,
                f"{filename}: parser returned {dcr['classification']!r}",
            )


if __name__ == "__main__":
    unittest.main()
