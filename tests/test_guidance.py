import tempfile
import unittest
import subprocess
from pathlib import Path

from agentspec.guidance import build_post_artifact_guidance
from agentspec.review import record_doc_review


class PostArtifactGuidanceTests(unittest.TestCase):
    def test_dcr_guidance_requires_review_before_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dcr = _write_dcr(root, status="classified")

            guidance = build_post_artifact_guidance(root, "docs/change-requests/DCR-0001-test.md")

            self.assertEqual(guidance["schema"], "agentspec.post_artifact_guidance.v0")
            self.assertEqual(guidance["artifact"]["id"], "DCR-0001")
            self.assertEqual(guidance["artifact"]["kind"], "dcr")
            self.assertEqual(guidance["state"], "review_missing")
            self.assertEqual(guidance["review"]["readiness"], "missing")
            self.assertEqual(guidance["next_actions"][0]["id"], "review_document")
            self.assertIn("Review DCR-0001", guidance["agent_display"]["prompt"])
            self.assertFalse(guidance["agent_display"]["show_terminal_commands"])

    def test_dcr_guidance_offers_acceptance_when_review_is_current(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_dcr(root, status="classified")
            record_doc_review(
                root,
                artifact_selector="docs/change-requests/DCR-0001-test.md",
                verdict="ready",
                reviewer="human",
                summary="Ready.",
            )

            guidance = build_post_artifact_guidance(root, "docs/change-requests/DCR-0001-test.md")

            self.assertEqual(guidance["state"], "review_ready")
            self.assertEqual(guidance["review"]["readiness"], "current")
            self.assertEqual(guidance["next_actions"][0]["id"], "accept_dcr")
            self.assertIn("Accept DCR-0001", guidance["agent_display"]["prompt"])

    def test_dcr_guidance_marks_material_change_stale(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            dcr = _write_dcr(root, status="classified")
            record_doc_review(
                root,
                artifact_selector="docs/change-requests/DCR-0001-test.md",
                verdict="ready",
                reviewer="human",
                summary="Ready.",
            )
            dcr.write_text(dcr.read_text(encoding="utf-8") + "\nMaterial change.\n", encoding="utf-8")

            guidance = build_post_artifact_guidance(root, dcr)

            self.assertEqual(guidance["state"], "review_stale")
            self.assertEqual(guidance["review"]["readiness"], "stale")
            self.assertEqual(guidance["next_actions"][0]["id"], "review_document")

    def test_dcr_guidance_warns_when_durable_artifact_is_gitignored(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _init_git_with_ignore(root, "/docs/change-requests/\n")
            _write_dcr(root, status="classified")

            guidance = build_post_artifact_guidance(root, "docs/change-requests/DCR-0001-test.md")

            preservation = guidance["preservation"]
            self.assertEqual(preservation["ignored_artifacts"], ["docs/change-requests/DCR-0001-test.md"])
            self.assertEqual(
                preservation["preserve_command"],
                "git add -f -- docs/change-requests/DCR-0001-test.md",
            )
            self.assertIn("agent/runs", preservation["agent_display"]["guidance"])

    def test_design_guidance_requires_review_before_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_design(root)

            guidance = build_post_artifact_guidance(root, "docs/designs/test-design.md")

            self.assertEqual(guidance["artifact"]["kind"], "design")
            self.assertEqual(guidance["state"], "review_missing")
            self.assertEqual(guidance["next_actions"][0]["id"], "review_document")
            self.assertIn("before promoting it as source", guidance["agent_display"]["prompt"])
            self.assertFalse(guidance["agent_display"]["show_terminal_commands"])

    def test_reviewed_design_guidance_offers_source_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_design(root)
            record_doc_review(
                root,
                artifact_selector="docs/designs/test-design.md",
                verdict="ready",
                reviewer="human",
                summary="Ready.",
            )

            guidance = build_post_artifact_guidance(root, "docs/designs/test-design.md")

            self.assertEqual(guidance["state"], "review_ready")
            self.assertEqual(guidance["review"]["readiness"], "current")
            self.assertEqual(guidance["next_actions"][0]["id"], "promote_source")
            self.assertIn("aspec ingest docs/designs/test-design.md", guidance["next_actions"][0]["commands"])
            self.assertIn("Promote docs/designs/test-design.md", guidance["agent_display"]["prompt"])

    def test_task_context_pack_guidance_recommends_workflow_planning_first(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_task_context_pack(root, workflow=None)

            guidance = build_post_artifact_guidance(root, "agent/context-packs/T-001-test-task.md")

            self.assertEqual(guidance["artifact"]["kind"], "task_context_pack")
            self.assertEqual(guidance["state"], "task_created_workflow_needed")
            self.assertEqual(guidance["next_actions"][0]["id"], "plan_workflow")
            self.assertEqual(guidance["next_actions"][0]["commands"], ["aspec plan T-001 --json"])
            self.assertIn("Plan workflow for T-001", guidance["agent_display"]["prompt"])

    def test_task_context_pack_guidance_recommends_session_after_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_task_context_pack(root, workflow="agent/workflows/W-001-test-task.md")
            _write_workflow(root)

            guidance = build_post_artifact_guidance(root, "agent/context-packs/T-001-test-task.md")

            self.assertEqual(guidance["state"], "task_created_session_needed")
            self.assertEqual(guidance["next_actions"][0]["id"], "claim_session")
            self.assertIn("aspec session start --task T-001", guidance["next_actions"][0]["commands"][0])
            self.assertEqual(guidance["artifact"]["execution_strategy"]["selected"]["mode"], "provider_native")
            self.assertEqual(
                guidance["artifact"]["execution_strategy"]["fallback"]["mode"],
                "agentspec_generic_fallback",
            )
            self.assertFalse(guidance["agent_display"]["show_terminal_commands"])


def _write_dcr(root: Path, *, status: str) -> Path:
    path = root / "docs" / "change-requests" / "DCR-0001-test.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"""# DCR-0001: Test

| Field | Value |
|---|---|
| Status | {status} |
| Classification | implement-now |
| Submitted | 2026-05-13 |
| Submitted by | tester |
| Decided by | tester |
| Decided on | 2026-05-13 |
| Confidence | medium |

## Summary

Test summary.

## Motivation

Test motivation.

## Proposed Change

Test change.

## Acceptance Criteria

- Test.
""",
        encoding="utf-8",
    )
    return path


def _write_design(root: Path) -> Path:
    path = root / "docs" / "designs" / "test-design.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# Test Design

## Summary

Design summary.

## Proposed Change

Design change.
""",
        encoding="utf-8",
    )
    return path


def _write_task_context_pack(root: Path, *, workflow: str | None) -> Path:
    path = root / "agent" / "context-packs" / "T-001-test-task.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    workflow_line = f"Workflow: `{workflow}`\n" if workflow else ""
    path.write_text(
        f"""# T-001: Test Task

Type: `implementation`
Branch: `codex/t-001-test-task`
{workflow_line}
## Requirements

- `R-001` Test requirement (P0, high)
""",
        encoding="utf-8",
    )
    return path


def _write_workflow(root: Path) -> Path:
    path = root / "agent" / "workflows" / "W-001-test-task.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """---
workflow_id: W-001
task_pack: agent/context-packs/T-001-test-task.md
status: planned
current_stage: planning
branch: codex/t-001-test-task
allowed_paths:
  - agentspec/guidance.py
verification_commands:
  - python -m pytest tests/test_guidance.py -q
---

# Workflow W-001: Test Task
""",
        encoding="utf-8",
    )
    return path


def _init_git_with_ignore(root: Path, ignore_text: str) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    (root / ".gitignore").write_text(ignore_text, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
