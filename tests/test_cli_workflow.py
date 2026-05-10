import contextlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.io import load_data


DESIGN_DOC = """# AgentSpec Product Design

**Working title:** AgentSpec

## 1. Executive Summary

AgentSpec must convert product requirements and architecture notes into an agent-ready engineering workspace.

## 3. Product Goals and Non-Goals

### 3.1 Goals for V1

1. Convert a Markdown design document into canonical source sections with stable IDs and content hashes.
2. Generate draft project canvas, spec shards, requirements, assumptions, open questions, and task context pack templates.
3. Provide a CLI that can run locally and in CI.

### 3.4 Non-Goals for V1

1. AgentSpec will not implement a general-purpose autonomous coding agent.

## 4. Success Criteria

- Generated requirements have source section references.
- Task context packs include explicit source sections.

## 10. Product Surface

### 10.2 CLI

The CLI is the primary V1 interface.

## 12. Core Runtime Components

### 12.4 Sectionizer

The sectionizer must parse heading hierarchy and compute content hashes.

## 23. Security and Governance

Task context packs must delimit source content and must not treat retrieved text as instructions.

## 28. Rollout Plan

### Phase 1: Local Artifact Scaffold

Deliverables:

- agentspec init
- artifact layout
- generated AGENTS.md / CLAUDE.md

## 29. Recommended Initial Implementation Tasks

1. Implement `agentspec init`.
2. Implement Markdown sectionizer.
3. Implement task context pack builder.
4. Implement AGENTS.md and CLAUDE.md emitters.

## 30. Open Questions

1. Should the first implementation language be Python, TypeScript, or a split architecture?
"""


@contextlib.contextmanager
def pushd(path: Path):
    old = Path.cwd()
    try:
        import os

        os.chdir(path)
        yield
    finally:
        os.chdir(old)


class CliWorkflowTests(unittest.TestCase):
    def test_first_milestone_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            design = project / "design.md"
            design.write_text(DESIGN_DOC, encoding="utf-8")

            with pushd(project):
                self.assertEqual(main(["init"]), 0)
                self.assertTrue((project / ".agentspec" / "config.yml").exists())
                self.assertTrue((project / "agent" / "context-packs" / "template.md").exists())
                self.assertTrue((project / "agent" / "outcomes.yml").exists())

                self.assertEqual(main(["ingest", str(design)]), 0)
                sections = load_data(project / "docs" / "source" / "sections.yml")
                self.assertGreaterEqual(len(sections), 8)
                self.assertTrue(all(section["source_id"] == "SRC-0001" for section in sections))

                self.assertEqual(main(["compile"]), 0)
                requirements = load_data(project / "docs" / "traceability" / "requirements.yml")
                self.assertGreaterEqual(len(requirements), 6)
                self.assertTrue(all(req["source_sections"] for req in requirements))

                readiness = load_data(project / "docs" / "discovery" / "readiness.yml")
                self.assertGreaterEqual(readiness["score"], 60)

                first_requirement = requirements[0]["id"]
                self.assertEqual(main(["task", "create", "--requirement", first_requirement]), 0)
                packs = list((project / "agent" / "context-packs").glob("T-*.md"))
                self.assertEqual(len(packs), 1)
                pack_text = packs[0].read_text(encoding="utf-8")
                self.assertIn(first_requirement, pack_text)
                self.assertIn("UNTRUSTED SOURCE CONTENT", pack_text)

                self.assertEqual(main(["emit", "--target", "agents-md,claude,codex"]), 0)
                self.assertTrue((project / "AGENTS.md").exists())
                agents_text = (project / "AGENTS.md").read_text(encoding="utf-8")
                self.assertIn("aspec compile", agents_text)
                self.assertIn("Before final commit or task completion", agents_text)
                self.assertIn("Requirements:", agents_text)
                self.assertIn("Product outcomes:", agents_text)
                self.assertIn("aspec outcome", agents_text)
                self.assertIn("Next action:", agents_text)
                self.assertTrue((project / "CLAUDE.md").exists())
                self.assertTrue((project / ".claude" / "agents" / "agentspec-spec-reviewer.md").exists())
                self.assertTrue((project / ".claude" / "agents" / "agentspec-quality-gc-reviewer.md").exists())
                self.assertTrue((project / ".codex" / "agents" / "spec-reviewer.toml").exists())
                self.assertTrue((project / ".codex" / "agents" / "quality-gc-reviewer.toml").exists())

                self.assertEqual(main(["doctor"]), 0)
                self.assertTrue((project / "reports" / "doctor" / "repo-scan.yml").exists())
                scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
                self.assertEqual(scan["agent_context"]["status"], "fresh")
                self.assertEqual(scan["project_invariants"]["status"], "not_configured")

                status_output = io.StringIO()
                with redirect_stdout(status_output):
                    self.assertEqual(main(["status", "--json"]), 0)
                status_payload = json.loads(status_output.getvalue())
                self.assertIn("outcomes", status_payload)
                self.assertEqual(status_payload["outcomes"]["readiness"], "not_configured")

                self.assertEqual(main(["drift"]), 0)
                self.assertTrue((project / "reports" / "drift" / "latest.md").exists())

                self.assertEqual(main(["quality"]), 0)
                self.assertTrue((project / "reports" / "quality" / "latest.yml").exists())
                self.assertTrue((project / "reports" / "quality" / "latest.md").exists())

    def test_doctor_warns_when_agent_context_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            _write_agent_context_sources(project)

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            warnings = scan["agent_context"]["warnings"]
            self.assertEqual(scan["agent_context"]["status"], "warning")
            self.assertTrue(
                any(warning["kind"] == "missing" and warning["path"] == "AGENTS.md" for warning in warnings),
                warnings,
            )
            self.assertTrue(
                all(warning["recovery_command"] == "aspec emit --target claude,codex" for warning in warnings),
                warnings,
            )
            report = (project / "reports" / "doctor" / "agent-readiness.md").read_text(encoding="utf-8")
            self.assertIn("aspec emit --target claude,codex", report)

    def test_doctor_warns_when_codex_agent_context_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            _write_agent_context_sources(project)
            (project / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
            (project / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
            (project / ".codex" / "agents").mkdir(parents=True)

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            warnings = scan["agent_context"]["warnings"]
            self.assertEqual(scan["agent_context"]["status"], "warning")
            self.assertIn(".codex/agents/*.toml", scan["agent_context"]["checked_artifacts"])
            self.assertTrue(
                any(
                    warning["kind"] == "missing" and warning["path"] == ".codex/agents/*.toml"
                    for warning in warnings
                ),
                warnings,
            )

    def test_doctor_warns_when_agent_context_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            _write_agent_context_sources(project)
            _write_agent_context_outputs(project)
            old_time = 1_700_000_000_000_000_000
            new_time = old_time + 1_000_000_000
            for relative in ["AGENTS.md", "CLAUDE.md", ".codex/agents/spec-reviewer.toml"]:
                _set_mtime(project / relative, old_time)
            _set_mtime(project / "docs" / "traceability" / "requirements.yml", new_time)

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            stale_paths = {
                warning["path"]
                for warning in scan["agent_context"]["warnings"]
                if warning["kind"] == "stale"
            }
            self.assertEqual(scan["agent_context"]["status"], "warning")
            self.assertIn("AGENTS.md", stale_paths)
            self.assertIn("CLAUDE.md", stale_paths)
            self.assertIn(".codex/agents/spec-reviewer.toml", stale_paths)

    def test_doctor_accepts_fresh_agent_context(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            _write_agent_context_sources(project)
            _write_agent_context_outputs(project)
            old_time = 1_700_000_000_000_000_000
            new_time = old_time + 1_000_000_000
            _set_mtime(project / "docs" / "traceability" / "requirements.yml", old_time)
            _set_mtime(project / "docs" / "discovery" / "readiness.yml", old_time)
            _set_mtime(project / "agent" / "task-ledger.yml", old_time)
            for relative in ["AGENTS.md", "CLAUDE.md", ".codex/agents/spec-reviewer.toml"]:
                _set_mtime(project / relative, new_time)

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            self.assertEqual(scan["agent_context"]["status"], "fresh")
            self.assertEqual(scan["agent_context"]["warnings"], [])

    def test_doctor_reports_missing_project_invariant_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            self.assertEqual(scan["project_invariants"]["status"], "not_configured")
            self.assertEqual(scan["project_invariants"]["path"], "agent/policies/invariants.yml")
            report = (project / "reports" / "doctor" / "agent-readiness.md").read_text(encoding="utf-8")
            self.assertIn("## Project Invariants", report)

    def test_doctor_reports_passing_project_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
            _write_json(
                project / "agent" / "policies" / "invariants.yml",
                [
                    {
                        "id": "INV-001",
                        "kind": "required_path",
                        "path": "AGENTS.md",
                        "description": "Agent instructions exist.",
                        "severity": "error",
                    },
                    {
                        "id": "INV-002",
                        "kind": "forbidden_path",
                        "pattern": "dist/**/*.js",
                        "description": "Generated JS is not committed.",
                        "severity": "warning",
                    },
                ],
            )

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            self.assertEqual(scan["project_invariants"]["status"], "passed")
            self.assertTrue(all(result["status"] == "passed" for result in scan["project_invariants"]["results"]))

    def test_doctor_reports_failing_project_invariants(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "dist").mkdir(parents=True)
            (project / "dist" / "app.js").write_text("console.log('built');\n", encoding="utf-8")
            _write_json(
                project / "agent" / "policies" / "invariants.yml",
                [
                    {
                        "id": "INV-001",
                        "kind": "required_path",
                        "path": "AGENTS.md",
                        "severity": "error",
                    },
                    {
                        "id": "INV-002",
                        "kind": "forbidden_path",
                        "pattern": "dist/**/*.js",
                        "severity": "warning",
                    },
                ],
            )

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            results = {result["id"]: result for result in scan["project_invariants"]["results"]}
            self.assertEqual(scan["project_invariants"]["status"], "failed")
            self.assertEqual(results["INV-001"]["status"], "failed")
            self.assertEqual(results["INV-001"]["severity"], "error")
            self.assertIn("AGENTS.md", results["INV-001"]["message"])
            self.assertEqual(results["INV-002"]["status"], "failed")
            self.assertEqual(results["INV-002"]["matches"], ["dist/app.js"])

    def test_doctor_reports_invalid_project_invariant_config_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            _write_json(project / "agent" / "policies" / "invariants.yml", {"id": "INV-001"})

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            self.assertEqual(scan["project_invariants"]["status"], "invalid_config")
            self.assertEqual(scan["project_invariants"]["results"][0]["status"], "invalid")
            report = (project / "reports" / "doctor" / "agent-readiness.md").read_text(encoding="utf-8")
            self.assertIn("invalid_config", report)

    def test_doctor_reports_invalid_invariant_entries_without_hiding_valid_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            (project / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
            _write_json(
                project / "agent" / "policies" / "invariants.yml",
                [
                    {
                        "id": "INV-001",
                        "kind": "required_path",
                        "path": "AGENTS.md",
                        "severity": "error",
                    },
                    {"id": "INV-002", "kind": "not_supported", "severity": "warning"},
                ],
            )

            self.assertEqual(main(["--root", str(project), "doctor"]), 0)

            scan = load_data(project / "reports" / "doctor" / "repo-scan.yml")
            results = {result["id"]: result for result in scan["project_invariants"]["results"]}
            self.assertEqual(scan["project_invariants"]["status"], "invalid_config")
            self.assertEqual(results["INV-001"]["status"], "passed")
            self.assertEqual(results["INV-002"]["status"], "invalid")
            self.assertIn("Unknown project invariant kind", results["INV-002"]["message"])

    def test_emit_agents_md_includes_latest_handoff_command(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            _write_agent_context_sources(project)
            _write_json(
                project / "agent" / "handoff.yml",
                {
                    "schema": "agentspec.project_handoff.v0",
                    "updated_at": "2026-05-05T00:00:00Z",
                    "root": ".",
                    "last_completed_task": {
                        "id": "T-080",
                        "context_pack": "agent/context-packs/T-080-test.md",
                    },
                    "next_action": {
                        "kind": "start_task",
                        "command": "aspec run loop agent/context-packs/T-081-test.md",
                    },
                },
            )

            self.assertEqual(main(["--root", str(project), "emit", "--target", "agents-md"]), 0)

            agents_text = (project / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Handoff: agent/handoff.yml last_completed=T-080", agents_text)
            self.assertIn(
                "Next action: start_task -> `aspec run loop agent/context-packs/T-081-test.md`",
                agents_text,
            )

    def test_drift_maps_diff_to_requirements_context_pack_and_tests(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            _write_json(
                project / "docs" / "traceability" / "requirements.yml",
                [
                    {
                        "id": "R-010",
                        "title": "Detect design drift in a code diff",
                        "description": "Detect design drift in a code diff by comparing changed files against requirements, ADRs, and task context packs.",
                        "source_sections": ["D-03"],
                        "priority": "P0",
                        "status": "accepted",
                        "confidence": "medium",
                        "acceptance": [],
                        "code_targets": ["agentspec/drift.py"],
                        "test_targets": ["tests/test_cli_workflow.py"],
                    },
                    {
                        "id": "R-083",
                        "title": "Compare diffs against requirements, ADRs, allowed paths, tests, and security policy",
                        "description": "Responsible for comparing diffs against requirements, ADRs, allowed paths, tests, and security policy.",
                        "source_sections": ["D-12"],
                        "priority": "P0",
                        "status": "accepted",
                        "confidence": "medium",
                        "acceptance": [],
                        "code_targets": ["agentspec/drift.py"],
                        "test_targets": ["tests/test_cli_workflow.py"],
                    },
                    {
                        "id": "R-999",
                        "title": "Emit agent configs",
                        "description": "Generate agent config files.",
                        "source_sections": ["D-10"],
                        "priority": "P1",
                        "status": "accepted",
                        "confidence": "medium",
                        "acceptance": [],
                        "code_targets": ["agentspec/emit.py"],
                        "test_targets": ["tests/test_emit.py"],
                    },
                ],
            )
            _write_json(
                project / "docs" / "source" / "sections.yml",
                [
                    {"id": "D-03", "heading_path": ["3. Product Goals and Non-Goals"]},
                    {"id": "D-12", "heading_path": ["12. Core Runtime Components"]},
                ],
            )
            (project / "docs" / "adr").mkdir(parents=True)
            (project / "docs" / "adr" / "0001-initial-architecture.md").write_text("Status: accepted\n", encoding="utf-8")
            (project / "agent" / "context-packs").mkdir(parents=True)
            (project / "agent" / "context-packs" / "T-001-drift-review.md").write_text(
                """# T-001: Drift Review

## Requirements

- `R-010` Detect design drift in a code diff
- `R-083` Compare diffs against requirements, ADRs, allowed paths, tests, and security policy

## Allowed Paths

- `agentspec/drift.py`
- `tests/test_cli_workflow.py`
""",
                encoding="utf-8",
            )
            diff = project / "drift.patch"
            diff.write_text(
                """diff --git a/agentspec/drift.py b/agentspec/drift.py
--- a/agentspec/drift.py
+++ b/agentspec/drift.py
@@ -1 +1,2 @@
-def run_drift(root):
+def run_drift(root):
+    return "semantic drift requirement analyzer"
diff --git a/tests/test_cli_workflow.py b/tests/test_cli_workflow.py
--- a/tests/test_cli_workflow.py
+++ b/tests/test_cli_workflow.py
@@ -1 +1,2 @@
-def test_old():
+def test_drift_maps_requirement_impact():
+    assert True
""",
                encoding="utf-8",
            )

            self.assertEqual(main(["--root", str(project), "drift", "--diff", str(diff)]), 0)

            report = (project / "reports" / "drift" / "latest.md").read_text(encoding="utf-8")
            self.assertIn("approve", report)
            # R-126: drift table now carries a DCRs column. The fixture
            # pack has no Originating DCR header, so the cell is `-`.
            self.assertIn("| `agentspec/drift.py` | aligned | `R-010`, `R-083` | `T-001` | - |", report)
            self.assertIn("| `tests/test_cli_workflow.py` | aligned | `R-010`, `R-083` | `T-001` | - |", report)
            self.assertIn("| `R-999` | not-impacted |", report)
            self.assertNotIn("Drift skeleton does not yet perform semantic impact analysis", report)

    def test_drift_flags_unmapped_files_outside_context_pack_scope(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            _write_json(
                project / "docs" / "traceability" / "requirements.yml",
                [
                    {
                        "id": "R-010",
                        "title": "Detect design drift in a code diff",
                        "description": "Detect design drift in a code diff by comparing changed files against requirements, ADRs, and task context packs.",
                        "source_sections": ["D-03"],
                        "priority": "P0",
                        "status": "accepted",
                        "confidence": "medium",
                        "acceptance": [],
                        "code_targets": ["agentspec/drift.py"],
                        "test_targets": ["tests/test_cli_workflow.py"],
                    }
                ],
            )
            _write_json(project / "docs" / "source" / "sections.yml", [])
            (project / "agent" / "context-packs").mkdir(parents=True)
            (project / "agent" / "context-packs" / "T-001-drift-review.md").write_text(
                """# T-001: Drift Review

## Requirements

- `R-010` Detect design drift in a code diff

## Allowed Paths

- `agentspec/drift.py`
""",
                encoding="utf-8",
            )
            diff = project / "unmapped.patch"
            diff.write_text(
                """diff --git a/agentspec/unknown.py b/agentspec/unknown.py
--- a/agentspec/unknown.py
+++ b/agentspec/unknown.py
@@ -0,0 +1 @@
+def unrelated_helper():
""",
                encoding="utf-8",
            )

            self.assertEqual(main(["--root", str(project), "drift", "--diff", str(diff)]), 0)

            report = (project / "reports" / "drift" / "latest.md").read_text(encoding="utf-8")
            self.assertIn("approve-with-comments", report)
            self.assertIn("No accepted requirement maps to this file or diff terms.", report)
            self.assertIn("No task context pack allows this file.", report)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_agent_context_sources(project: Path) -> None:
    _write_json(project / "docs" / "traceability" / "requirements.yml", [])
    _write_json(project / "docs" / "discovery" / "readiness.yml", {"score": 100, "mode": "normal-implementation"})
    _write_json(project / "agent" / "task-ledger.yml", {"schema": "agentspec.task_ledger.v0", "tasks": {}})


def _write_agent_context_outputs(project: Path) -> None:
    (project / "AGENTS.md").write_text("# AGENTS.md\n", encoding="utf-8")
    (project / "CLAUDE.md").write_text("# CLAUDE.md\n", encoding="utf-8")
    codex_agent = project / ".codex" / "agents" / "spec-reviewer.toml"
    codex_agent.parent.mkdir(parents=True, exist_ok=True)
    codex_agent.write_text('name = "spec-reviewer"\n', encoding="utf-8")


def _set_mtime(path: Path, ns: int) -> None:
    os.utime(path, ns=(ns, ns))


if __name__ == "__main__":
    unittest.main()
