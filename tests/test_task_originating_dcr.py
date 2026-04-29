"""Tests that DCR-derived task context packs cite the DCR and require an
implementation-eligible state.

Covers R-123 (DCR-0002).
"""

import json
import tempfile
import unittest
from pathlib import Path

from agentspec.task import create_task_context_pack


def _write_dcr(path: Path, classification: str, status: str = "classified") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# DCR-0099: Test DCR

| Field | Value |
|---|---|
| Status | {status} |
| Classification | {classification} |
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


def _seed_workspace(root: Path) -> None:
    """Minimal artifact set so create_task_context_pack can run."""
    for sub in [
        "docs/source",
        "docs/traceability",
        "docs/discovery",
        "docs/change-requests",
        "agent/context-packs",
    ]:
        (root / sub).mkdir(parents=True, exist_ok=True)

    src = root / "docs" / "source" / "design.md"
    src.write_text("## 3. Goals\n\nGoal text.\n", encoding="utf-8")
    (root / "docs" / "source" / "sources.yml").write_text(
        json.dumps([{"id": "SRC-0001", "uri": "docs/source/design.md"}]),
        encoding="utf-8",
    )
    (root / "docs" / "source" / "sections.yml").write_text(
        json.dumps(
            [
                {
                    "id": "D-03",
                    "source_id": "SRC-0001",
                    "title": "3. Goals",
                    "heading_path": ["3. Goals"],
                    "parent": None,
                    "children": [],
                    "start_line": 1,
                    "end_line": 3,
                    "content_hash": "sha256:test",
                }
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs" / "traceability" / "requirements.yml").write_text(
        json.dumps(
            [
                {
                    "id": "R-121",
                    "title": "DCR-derived requirement",
                    "description": "test.",
                    "source_sections": ["D-03"],
                    "priority": "P0",
                    "status": "proposed-pending-acceptance",
                    "confidence": "high",
                    "originating_dcr": "DCR-0099",
                    "acceptance": ["test"],
                    "code_targets": [],
                    "test_targets": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    (root / "docs" / "discovery" / "assumptions.yml").write_text(
        json.dumps([]), encoding="utf-8"
    )
    (root / "docs" / "discovery" / "readiness.yml").write_text(
        json.dumps({"score": 100, "mode": "normal-implementation"}), encoding="utf-8"
    )


class TaskOriginatingDCRTests(unittest.TestCase):
    def test_pack_with_implement_now_dcr_succeeds_and_cites_dcr(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _write_dcr(
                root / "docs" / "change-requests" / "DCR-0099-test.md", "implement-now"
            )

            path = create_task_context_pack(
                root, requirement_id="R-121", originating_dcr="DCR-0099"
            )
            self.assertTrue(path.exists())
            text = path.read_text(encoding="utf-8")
            self.assertIn("DCR-0099", text)

    def test_pack_with_defer_dcr_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            _write_dcr(
                root / "docs" / "change-requests" / "DCR-0099-test.md", "defer"
            )

            with self.assertRaises(ValueError) as ctx:
                create_task_context_pack(
                    root, requirement_id="R-121", originating_dcr="DCR-0099"
                )
            self.assertIn("DCR-0099", str(ctx.exception))

    def test_pack_with_missing_dcr_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            # No DCR file written.

            with self.assertRaises(ValueError) as ctx:
                create_task_context_pack(
                    root, requirement_id="R-121", originating_dcr="DCR-9999"
                )
            self.assertIn("DCR-9999", str(ctx.exception))


class PackTitleTruncationTests(unittest.TestCase):
    """R-141: pack titles truncate on word boundaries; full goal preserved."""

    def test_pack_title_truncates_on_word_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for sub in ["docs/source", "docs/traceability", "docs/discovery", "agent/context-packs"]:
                (root / sub).mkdir(parents=True, exist_ok=True)

            src = root / "docs" / "source" / "design.md"
            src.write_text("## 3. Goals\n\nGoal text.\n", encoding="utf-8")
            (root / "docs" / "source" / "sources.yml").write_text(
                json.dumps([{"id": "SRC-0001", "uri": "docs/source/design.md"}]),
                encoding="utf-8",
            )
            (root / "docs" / "source" / "sections.yml").write_text(
                json.dumps([{
                    "id": "D-03", "source_id": "SRC-0001", "title": "3. Goals",
                    "heading_path": ["3. Goals"], "parent": None, "children": [],
                    "start_line": 1, "end_line": 3, "content_hash": "sha256:test",
                }]),
                encoding="utf-8",
            )
            # Long requirement: 100+ chars description ending mid-word at the 96-char cut.
            long_description = (
                "Implement repository-aware code and test target inference based on "
                "language signals collected from the package configuration fixtures and tests"
            )
            (root / "docs" / "traceability" / "requirements.yml").write_text(
                json.dumps([{
                    "id": "R-200",
                    "title": long_description[:96],   # how compile would truncate today
                    "description": long_description,  # full text
                    "source_sections": ["D-03"],
                    "priority": "P0",
                    "status": "accepted",
                    "confidence": "high",
                    "acceptance": ["test"],
                    "code_targets": [],
                    "test_targets": [],
                }]),
                encoding="utf-8",
            )
            (root / "docs" / "discovery").mkdir(exist_ok=True)
            (root / "docs" / "discovery" / "assumptions.yml").write_text(json.dumps([]), encoding="utf-8")
            (root / "docs" / "discovery" / "readiness.yml").write_text(
                json.dumps({"score": 100, "mode": "normal-implementation"}), encoding="utf-8"
            )

            path = create_task_context_pack(root, requirement_id="R-200")
            text = path.read_text(encoding="utf-8")

            # Heading line: should not end mid-word with a partial token.
            heading = text.splitlines()[0]
            words = heading.rstrip(".:").rstrip("…").split()
            last_word = words[-1] if words else ""
            self.assertGreaterEqual(
                len(last_word), 4,
                f"title appears mid-word truncated: heading={heading!r}",
            )
            # Goal section preserves the full description.
            self.assertIn(long_description.split()[-1], text,
                          "full description (including last word) must appear in pack body")


if __name__ == "__main__":
    unittest.main()
