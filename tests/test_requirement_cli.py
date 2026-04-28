"""Tests for `agentspec requirement accept` — single-requirement acceptance.

Covers R-134 (DCR-0004).
"""

import contextlib
import io
import json
import os
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


def _seed_workspace(root: Path) -> None:
    (root / "docs" / "change-requests").mkdir(parents=True, exist_ok=True)
    (root / "docs" / "traceability").mkdir(parents=True, exist_ok=True)


def _write_dcr(root: Path, dcr_id: str, status: str = "accepted") -> None:
    path = root / "docs" / "change-requests" / f"{dcr_id}-test.md"
    path.write_text(
        f"""# {dcr_id}: Test DCR

| Field | Value |
|---|---|
| Status | {status} |
| Classification | implement-now |
| Submitted | 2026-04-28 |
| Submitted by | tester |
| Decided by | tester |
| Decided on | 2026-04-28 |
| Confidence | high |

## Summary
Test.
""",
        encoding="utf-8",
    )


def _write_requirements(root: Path, entries: list[dict]) -> None:
    (root / "docs" / "traceability" / "requirements.yml").write_text(
        json.dumps(entries), encoding="utf-8"
    )


def _ppa_requirement(req_id: str, originating_dcr: str | None = None) -> dict:
    record = {
        "id": req_id,
        "title": f"Test {req_id}",
        "description": "test.",
        "source_sections": ["D-03"],
        "priority": "P0",
        "status": "proposed-pending-acceptance",
        "confidence": "high",
        "acceptance": ["test"],
        "code_targets": [],
        "test_targets": [],
    }
    if originating_dcr:
        record["originating_dcr"] = originating_dcr
    return record


class RequirementAcceptHappyPathTests(unittest.TestCase):
    def test_accept_with_accepted_originating_dcr_flips_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _write_dcr(root, "DCR-0001", status="accepted")
            _write_requirements(root, [_ppa_requirement("R-200", originating_dcr="DCR-0001")])

            with pushd(root):
                rc = main(["requirement", "accept", "R-200"])
            self.assertEqual(rc, 0)

            reqs = json.loads(
                (root / "docs" / "traceability" / "requirements.yml").read_text()
            )
            self.assertEqual(reqs[0]["status"], "accepted")

    def test_accept_without_originating_dcr_flips_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _write_requirements(root, [_ppa_requirement("R-200")])

            with pushd(root):
                rc = main(["requirement", "accept", "R-200"])
            self.assertEqual(rc, 0)

            reqs = json.loads(
                (root / "docs" / "traceability" / "requirements.yml").read_text()
            )
            self.assertEqual(reqs[0]["status"], "accepted")


class RequirementAcceptRefusalTests(unittest.TestCase):
    def _silent_main(self, argv: list[str]) -> int:
        with contextlib.redirect_stderr(io.StringIO()):
            return main(argv)

    def test_unknown_requirement_id_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _write_requirements(root, [])

            with pushd(root):
                rc = self._silent_main(["requirement", "accept", "R-999"])
            self.assertEqual(rc, 1)

    def test_already_accepted_requirement_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            req = _ppa_requirement("R-200")
            req["status"] = "accepted"
            _write_requirements(root, [req])

            with pushd(root):
                rc = self._silent_main(["requirement", "accept", "R-200"])
            self.assertEqual(rc, 1)

    def test_originating_dcr_not_accepted_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _write_dcr(root, "DCR-0001", status="classified")  # not yet accepted
            _write_requirements(root, [_ppa_requirement("R-200", originating_dcr="DCR-0001")])

            with pushd(root):
                rc = self._silent_main(["requirement", "accept", "R-200"])
            self.assertEqual(rc, 1)

            # Status untouched.
            reqs = json.loads(
                (root / "docs" / "traceability" / "requirements.yml").read_text()
            )
            self.assertEqual(reqs[0]["status"], "proposed-pending-acceptance")


if __name__ == "__main__":
    unittest.main()
