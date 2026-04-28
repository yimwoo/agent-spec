"""Tests that `agentspec compile` preserves DCR-originated artifacts and fails
loudly on reconcile-impossible collisions.

Covers R-131, R-132 (DCR-0003).
"""

import json
import tempfile
import unittest
from pathlib import Path

from agentspec.compile import compile_project
from agentspec.init import init_project
from agentspec.ingest import ingest_source


SAMPLE_DESIGN = """# Test Design

## 1. Executive Summary

AgentSpec must convert Markdown design documents into source-backed artifacts.

## 3. Product Goals

1. Support sectionizing markdown documents.

## 30. Open Questions

1. Should the schema format be YAML or JSON?
"""


def _seed_with_ingest(root: Path) -> None:
    init_project(root)
    src = root / "design.md"
    src.write_text(SAMPLE_DESIGN, encoding="utf-8")
    ingest_source(root, src)


def _write_existing_requirements(root: Path, entries: list[dict]) -> None:
    (root / "docs" / "traceability" / "requirements.yml").write_text(
        json.dumps(entries), encoding="utf-8"
    )


def _write_existing_questions(root: Path, entries: list[dict]) -> None:
    (root / "docs" / "discovery" / "open-questions.yml").write_text(
        json.dumps(entries), encoding="utf-8"
    )


def _dcr_requirement(req_id: str) -> dict:
    return {
        "id": req_id,
        "title": "DCR-originated requirement",
        "description": "test.",
        "source_sections": ["D-01"],
        "priority": "P0",
        "status": "proposed-pending-acceptance",
        "confidence": "high",
        "originating_dcr": "DCR-0099",
        "acceptance": ["test"],
        "code_targets": [],
        "test_targets": [],
    }


def _dcr_question(q_id: str) -> dict:
    return {
        "id": q_id,
        "question": "DCR-originated open question.",
        "status": "open",
        "impact": ["test"],
        "source_sections": ["D-01"],
        "raised_by": "DCR-0099",
    }


class CompilePreservesDCRMaterialTests(unittest.TestCase):
    def test_dcr_originated_requirement_survives_compile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_with_ingest(root)
            _write_existing_requirements(root, [_dcr_requirement("R-099")])

            compile_project(root)

            reqs = json.loads(
                (root / "docs" / "traceability" / "requirements.yml").read_text()
            )
            preserved = [r for r in reqs if r["id"] == "R-099"]
            self.assertEqual(len(preserved), 1)
            self.assertEqual(preserved[0].get("originating_dcr"), "DCR-0099")
            self.assertEqual(
                preserved[0].get("status"), "proposed-pending-acceptance"
            )

    def test_dcr_originated_question_survives_compile(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_with_ingest(root)
            _write_existing_questions(root, [_dcr_question("Q-099")])

            compile_project(root)

            qs = json.loads(
                (root / "docs" / "discovery" / "open-questions.yml").read_text()
            )
            preserved = [q for q in qs if q["id"] == "Q-099"]
            self.assertEqual(len(preserved), 1)
            self.assertEqual(preserved[0].get("raised_by"), "DCR-0099")

    def test_id_collision_raises_with_dcr_and_id_in_message(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_with_ingest(root)
            # Force a collision: source-derived requirements start at R-001.
            _write_existing_requirements(root, [_dcr_requirement("R-001")])

            with self.assertRaises(ValueError) as ctx:
                compile_project(root)
            message = str(ctx.exception)
            self.assertIn("DCR-0099", message)
            self.assertIn("R-001", message)

    def test_compile_without_dcr_material_unchanged(self) -> None:
        """Regression guard: a workspace with no DCR material behaves exactly
        as the existing compile flow."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_with_ingest(root)
            _write_existing_requirements(root, [])
            _write_existing_questions(root, [])

            compile_project(root)

            reqs = json.loads(
                (root / "docs" / "traceability" / "requirements.yml").read_text()
            )
            qs = json.loads(
                (root / "docs" / "discovery" / "open-questions.yml").read_text()
            )

            self.assertGreater(len(reqs), 0, "compile should produce some requirements")
            self.assertFalse(
                any(r.get("status") == "proposed-pending-acceptance" for r in reqs),
                "no DCR material seeded, so no proposed-pending-acceptance entries",
            )
            self.assertFalse(any(q.get("raised_by") for q in qs))


if __name__ == "__main__":
    unittest.main()
