import tempfile
import unittest
from pathlib import Path

from agentspec.io import write_data
from agentspec.status import build_project_status


class LifecycleSkillGateTests(unittest.TestCase):
    def test_skill_gates_are_disabled_by_default_without_findings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)

            lifecycle = build_project_status(root)["lifecycle"]
            skill_gates = lifecycle["skill_gates"]

            self.assertFalse(skill_gates["enabled"])
            self.assertEqual(skill_gates["readiness"], "disabled")
            self.assertEqual(skill_gates["findings"], [])
            self.assertFalse((root / ".agentspec" / "hooks").exists())
            self.assertFalse((root / "agent" / "evidence").exists())

    def test_enabled_required_gates_emit_repairable_findings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            write_data(
                root / ".agentspec" / "config.yml",
                {"lifecycle": {"skill_gates": {"enabled": True, "required": ["design", "plan"]}}},
            )

            lifecycle = build_project_status(root)["lifecycle"]
            skill_gates = lifecycle["skill_gates"]
            gate_findings = [
                finding for finding in lifecycle["warnings"]
                if finding["type"] == "skill_gate_missing"
            ]

            self.assertTrue(skill_gates["enabled"])
            self.assertEqual(skill_gates["readiness"], "needs_attention")
            self.assertEqual(skill_gates["counts"]["required"], 2)
            self.assertEqual(skill_gates["counts"]["missing_required"], 2)
            self.assertEqual({finding["gate"] for finding in gate_findings}, {"design", "plan"})
            self.assertTrue(all(finding.get("repair") for finding in gate_findings))

    def test_gate_projection_reports_existing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            write_data(
                root / ".agentspec" / "config.yml",
                {"lifecycle": {"skill_gates": {"enabled": True, "required": ["design"]}}},
            )
            (root / "docs" / "designs").mkdir(parents=True)
            (root / "docs" / "designs" / "2026-05-11-test-design.md").write_text(
                "---\ndesign_type: phase\n---\n\n# Test Design\n",
                encoding="utf-8",
            )

            lifecycle = build_project_status(root)["lifecycle"]
            skill_gates = lifecycle["skill_gates"]
            design_gate = next(gate for gate in skill_gates["gates"] if gate["id"] == "design")

            self.assertEqual(skill_gates["readiness"], "ready")
            self.assertEqual(design_gate["status"], "passed")
            self.assertEqual(design_gate["evidence"], ["docs/designs/2026-05-11-test-design.md"])
            self.assertFalse(
                any(finding["type"] == "skill_gate_missing" for finding in lifecycle["warnings"])
            )

    def test_strict_lifecycle_promotes_skill_gate_findings_to_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_minimal(root)
            write_data(
                root / ".agentspec" / "config.yml",
                {
                    "lifecycle": {
                        "enforcement": "strict",
                        "skill_gates": {"enabled": True, "required": ["design"]},
                    }
                },
            )

            lifecycle = build_project_status(root)["lifecycle"]
            blockers = [
                finding for finding in lifecycle["blocking"]
                if finding["type"] == "skill_gate_missing"
            ]

            self.assertEqual(lifecycle["readiness"], "blocked")
            self.assertEqual(len(blockers), 1)
            self.assertEqual(blockers[0]["gate"], "design")
            self.assertEqual(blockers[0]["severity"], "blocking")
            self.assertTrue(blockers[0]["blocks_strict"])
            self.assertIn("docs/designs", blockers[0]["repair"])


def _seed_minimal(root: Path) -> None:
    (root / "agent" / "context-packs").mkdir(parents=True)
    (root / "docs" / "traceability").mkdir(parents=True)
    write_data(root / "docs" / "traceability" / "requirements.yml", [])


if __name__ == "__main__":
    unittest.main()
