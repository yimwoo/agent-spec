"""Tests for R-142: research-mode fallback in autonomous runs."""

import json
import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.dcr import accept_dcr, create_dcr_stub
from agentspec.init import init_project
from agentspec.io import load_data
from agentspec.run import (
    MAX_RESEARCH_FINDINGS_DEFAULT,
    RESEARCH_ALLOWED_PATHS,
    RESEARCH_CONTEXT_PACK_SENTINEL,
    RESEARCH_TASK_PREPARATION_ALLOWED_PATHS,
    build_next_executor_prompt,
    inspect_run,
    loop_run,
    resume_run,
    start_research_run,
)
from agentspec.runner import RUNNER_RESULT_SCHEMA, submit_runner_result


def _seed_workspace(root: Path) -> None:
    init_project(root)


class StartResearchRunTests(unittest.TestCase):
    def test_creates_state_with_research_allowed_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            state = start_research_run(root, run_id="r-research-1")

            self.assertEqual(state["mode"], "research")
            self.assertEqual(state["context_pack"], RESEARCH_CONTEXT_PACK_SENTINEL)
            # Allowed paths are exactly the research findings dirs.
            self.assertEqual(set(state["allowed_paths"]), set(RESEARCH_ALLOWED_PATHS))
            self.assertEqual(state["research_findings_produced"], 0)
            self.assertEqual(
                state["max_research_findings"],
                MAX_RESEARCH_FINDINGS_DEFAULT,
            )

            summary = load_data(root / "agent" / "runs" / "r-research-1" / "summary.yml")
            self.assertEqual(summary["schema"], "agentspec.supervised_run.summary.v0")
            self.assertEqual(summary["mode"], "research")
            self.assertEqual(summary["status"], "started")
            self.assertEqual(summary["event_counts"]["research_run_started"], 1)

    def test_max_research_findings_override(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            state = start_research_run(root, run_id="r-research-2", max_research_findings=2)
            self.assertEqual(state["max_research_findings"], 2)

    def test_task_preparation_paths_are_added_for_taskable_dcrs(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            create_dcr_stub(
                root,
                "Prepare accepted DCR for tasking",
                "implement-now",
                dcr_id="DCR-0099",
            )
            accept_dcr(root, "DCR-0099")

            state = start_research_run(root, run_id="r-research-tasking")

            self.assertEqual(
                set(state["allowed_paths"]),
                set(RESEARCH_ALLOWED_PATHS + RESEARCH_TASK_PREPARATION_ALLOWED_PATHS),
            )
            self.assertIn("agent/doc-reviews/**", state["allowed_paths"])
            self.assertEqual(state["target_write_requirements"], state["allowed_paths"])
            self.assertEqual(state["task_preparation"]["status"], "available")
            self.assertEqual(state["task_preparation"]["dcrs"], ["DCR-0099"])
            self.assertIn("agent/doc-reviews/**", state["task_preparation"]["allowed_paths"])


class ResearchPolicyEnforcementTests(unittest.TestCase):
    def test_writes_outside_findings_dirs_halt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-outside")

            result = resume_run(
                root,
                "r-outside",
                executor_output="Looked at agentspec/cli.py and edited it.",
                touched_paths=["agentspec/cli.py"],  # forbidden in research
                test_status="not_run",
            )
            state = result["state"]
            self.assertEqual(state["status"], "halted")
            review = result["review"]
            self.assertIn("forbidden_path", review.get("policy_flags", []))

    def test_resume_ignores_preexisting_dirty_paths_from_git_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_git_dirty_research_workspace(root)
            start_research_run(root, run_id="r-dirty-baseline")
            research_path = root / "docs" / "change-requests" / "DCR-0099-research.md"
            research_path.parent.mkdir(parents=True, exist_ok=True)
            research_path.write_text("# Research\n", encoding="utf-8")

            result = resume_run(
                root,
                "r-dirty-baseline",
                executor_output="Done.",
                touched_paths=[
                    "src/schema.ts",
                    "docs/change-requests/DCR-0099-research.md",
                ],
                test_status="passed",
                acceptance_evidence=_valid_research_evidence(),
            )

            self.assertEqual(result["state"]["status"], "complete")
            self.assertEqual(result["review"]["decision"], "complete")
            self.assertNotIn("forbidden_path", result["review"].get("policy_flags", []))
            executor_event = _executor_event(root, "r-dirty-baseline")
            self.assertEqual(
                executor_event["touched_paths"],
                ["docs/change-requests/DCR-0099-research.md"],
            )
            self.assertEqual(
                executor_event["reported_touched_paths"],
                ["src/schema.ts", "docs/change-requests/DCR-0099-research.md"],
            )
            self.assertEqual(executor_event["touched_paths_source"], "controller_observed")

    def test_resume_flags_dirty_paths_changed_after_research_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_git_dirty_research_workspace(root)
            start_research_run(root, run_id="r-dirty-changed")
            (root / "src" / "schema.ts").write_text("changed during run\n", encoding="utf-8")
            research_path = root / "docs" / "change-requests" / "DCR-0099-research.md"
            research_path.parent.mkdir(parents=True, exist_ok=True)
            research_path.write_text("# Research\n", encoding="utf-8")

            result = resume_run(
                root,
                "r-dirty-changed",
                executor_output="Done.",
                touched_paths=["docs/change-requests/DCR-0099-research.md"],
                test_status="passed",
                acceptance_evidence=_valid_research_evidence(),
            )

            self.assertEqual(result["state"]["status"], "halted")
            self.assertEqual(result["review"]["decision"], "halt")
            self.assertIn("forbidden_path", result["review"].get("policy_flags", []))
            executor_event = _executor_event(root, "r-dirty-changed")
            self.assertIn("src/schema.ts", executor_event["touched_paths"])

    def test_writes_inside_findings_dirs_count_toward_cap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-inside", max_research_findings=3)

            result = resume_run(
                root,
                "r-inside",
                executor_output="Logged a finding.",
                touched_paths=["reports/dogfood/2026-04-28-something.md"],
                test_status="not_run",
            )
            state = result["state"]
            # Allowed write — counter incremented.
            self.assertEqual(state.get("research_findings_produced"), 1)

    def test_tasking_paths_do_not_halt_when_dcr_is_ready_for_tasking(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            create_dcr_stub(
                root,
                "Prepare accepted DCR for tasking",
                "implement-now",
                dcr_id="DCR-0099",
            )
            accept_dcr(root, "DCR-0099")
            start_research_run(root, run_id="r-tasking-paths")

            result = resume_run(
                root,
                "r-tasking-paths",
                executor_output="Prepared requirement and context-pack artifacts.",
                touched_paths=[
                    "agent/doc-reviews/DOCREVIEW-0001.yml",
                    "docs/traceability/requirements.yml",
                    "agent/context-packs/T-001-prepared-task.md",
                ],
                test_status="not_run",
            )

            self.assertNotEqual(result["state"]["status"], "halted")
            self.assertNotIn("forbidden_path", result["review"].get("policy_flags", []))

    def test_terminates_at_max_research_findings(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-cap", max_research_findings=2)

            resume_run(
                root, "r-cap",
                executor_output="finding 1",
                touched_paths=["reports/dogfood/2026-04-28-a.md"],
                test_status="not_run",
            )
            result = resume_run(
                root, "r-cap",
                executor_output="finding 2",
                touched_paths=["reports/dogfood/2026-04-28-b.md"],
                test_status="not_run",
            )
            state = result["state"]
            # At cap → halt with the structured flag.
            self.assertEqual(state["status"], "halted")
            self.assertIn(
                "research_findings_cap",
                result["review"].get("policy_flags", []),
            )


class ResearchHardLimitsTests(unittest.TestCase):
    """ADR-0004 hard limits also fire in research mode."""

    def test_destructive_git_halts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-git")

            result = resume_run(
                root, "r-git",
                executor_output="ran git push --force origin main",
                touched_paths=[],
                test_status="not_run",
            )
            state = result["state"]
            self.assertEqual(state["status"], "halted")
            self.assertIn("destructive_git", result["review"].get("policy_flags", []))

    def test_policy_halt_remains_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-policy-terminal")

            resume_run(
                root,
                "r-policy-terminal",
                executor_output="ran git push --force origin main",
                touched_paths=[],
                test_status="not_run",
            )

            with self.assertRaisesRegex(ValueError, "already halted"):
                resume_run(
                    root,
                    "r-policy-terminal",
                    executor_output="Done. Acceptance criteria are covered and verification passed.",
                    touched_paths=["docs/change-requests/DCR-0099-research.md"],
                    test_status="passed",
                )

    def test_acceptance_attempt_halts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-accept")

            result = resume_run(
                root, "r-accept",
                executor_output="now I'll run aspec requirement accept R-200",
                touched_paths=[],
                test_status="not_run",
            )
            state = result["state"]
            self.assertEqual(state["status"], "halted")
            self.assertIn("auto_acceptance", result["review"].get("policy_flags", []))

    def test_destructive_git_halts_even_with_acceptance_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-git-evidence")

            package = submit_runner_result(
                root,
                "r-git-evidence",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done. Ran git push --force origin main.",
                    "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                    "test_status": "passed",
                    "acceptance_evidence": _valid_research_evidence(),
                },
            )

            step = package["step"]
            self.assertEqual(step["state"]["status"], "halted")
            self.assertIn("destructive_git", step["review"].get("policy_flags", []))


class ResearchAcceptanceEvidenceTests(unittest.TestCase):
    def test_research_prompt_includes_acceptance_evidence_template(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-prompt-evidence")

            handoff = build_next_executor_prompt(root, "r-prompt-evidence")

            self.assertIn("Research acceptance evidence:", handoff["prompt"])
            self.assertIn("agentspec.research_acceptance_evidence.v0", handoff["prompt"])
            self.assertIn("allowed_path_confirmation", handoff["prompt"])

    def test_inspect_halted_research_evidence_rejection_includes_template(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-inspect-evidence")

            first = resume_run(
                root,
                "r-inspect-evidence",
                executor_output="Done.",
                touched_paths=["docs/change-requests/DCR-0099-research.md"],
                test_status="passed",
            )
            self.assertEqual(first["state"]["status"], "halted")

            info = inspect_run(root, "r-inspect-evidence")

            guidance = info["recovery_guidance"]
            self.assertEqual(guidance["schema"], "agentspec.research_acceptance_recovery.v0")
            self.assertIn("--acceptance-evidence-json", guidance["resume_command"])
            self.assertEqual(
                guidance["acceptance_evidence"]["schema"],
                "agentspec.research_acceptance_evidence.v0",
            )
            self.assertIn("allowed_path_confirmation", guidance["acceptance_evidence"])
            self.assertIn("created_task_context_pack", guidance["acceptance_evidence"])

    def test_cli_resume_accepts_research_acceptance_evidence_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-cli-evidence")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "resume",
                        "r-cli-evidence",
                        "--executor-output",
                        "Created and accepted DCR-0042, then created ready task T-018.",
                        "--touched-path",
                        "docs/change-requests/DCR-0099-research.md",
                        "--test-status",
                        "passed",
                        "--reviewer",
                        "deterministic",
                        "--acceptance-evidence-json",
                        json.dumps(_valid_research_evidence()),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn("complete", output.getvalue())
            state = load_data(root / "agent" / "runs" / "r-cli-evidence" / "state.yml")
            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["last_decision"], "complete")

    def test_cli_resume_explicit_touched_paths_ignore_later_implementation_diff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_git_dirty_research_workspace(root)
            start_research_run(root, run_id="r-cli-explicit")
            (root / "src" / "schema.ts").write_text("changed during implementation\n", encoding="utf-8")
            research_path = root / "docs" / "change-requests" / "DCR-0099-research.md"
            research_path.parent.mkdir(parents=True, exist_ok=True)
            research_path.write_text("# Research\n", encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                code = main(
                    [
                        "--root",
                        str(root),
                        "run",
                        "resume",
                        "r-cli-explicit",
                        "--executor-output",
                        "Converted the research finding into an accepted DCR and completed task.",
                        "--touched-path",
                        "docs/change-requests/DCR-0099-research.md",
                        "--explicit-touched-paths",
                        "--test-status",
                        "passed",
                        "--reviewer",
                        "deterministic",
                        "--acceptance-evidence-json",
                        json.dumps(_valid_research_evidence()),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertIn("complete", output.getvalue())
            state = load_data(root / "agent" / "runs" / "r-cli-explicit" / "state.yml")
            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["last_decision"], "complete")
            executor_event = _executor_event(root, "r-cli-explicit")
            self.assertEqual(executor_event["touched_paths"], ["docs/change-requests/DCR-0099-research.md"])
            self.assertEqual(
                executor_event["reported_touched_paths"], ["docs/change-requests/DCR-0099-research.md"]
            )
            self.assertEqual(executor_event["touched_paths_source"], "executor_reported")
            self.assertNotIn("src/schema.ts", executor_event["touched_paths"])

    def test_halted_research_run_accepts_corrected_quality_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-corrected-evidence")

            first = resume_run(
                root,
                "r-corrected-evidence",
                executor_output="Done.",
                touched_paths=["docs/change-requests/DCR-0099-research.md"],
                test_status="passed",
            )
            self.assertEqual(first["state"]["status"], "halted")
            self.assertEqual(first["review"]["decision"], "pause_for_human")
            self.assertIn("research_acceptance_evidence_rejection", first["state"])
            self.assertNotIn("autonomous_dcr", first["state"])
            self.assertFalse(list((root / "docs" / "change-requests").glob("DCR-*.md")))

            corrected = resume_run(
                root,
                "r-corrected-evidence",
                executor_output="Done. Acceptance criteria are covered by the DCR and verification passed.",
                touched_paths=["docs/change-requests/DCR-0099-research.md"],
                test_status="passed",
            )

            self.assertEqual(corrected["state"]["status"], "complete")
            self.assertEqual(corrected["review"]["decision"], "complete")

            events = _events(root, "r-corrected-evidence")
            self.assertTrue(any(event["kind"] == "research_acceptance_evidence_rejected" for event in events))
            self.assertFalse(any(event["kind"] == "autonomous_pause_to_dcr" for event in events))
            self.assertTrue(any(event["kind"] == "halted_run_reopened" for event in events))

    def test_research_evidence_accepts_created_task_context_pack(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-created-task")
            create_dcr_stub(
                root,
                "Convert research into task",
                "implement-now",
                dcr_id="DCR-0099",
            )
            accept_dcr(root, "DCR-0099")
            (root / "docs" / "traceability" / "requirements.yml").write_text(
                "- id: R-999\n  status: accepted\n",
                encoding="utf-8",
            )
            pack = root / "agent" / "context-packs" / "T-001-converted-research.md"
            pack.write_text("# T-001: Converted research\n", encoding="utf-8")
            evidence = _valid_research_evidence()
            evidence.pop("no_task_context_pack_reason")
            evidence["durable_artifacts"] = [
                "docs/change-requests/DCR-0099-convert-research-into-task.md",
                "docs/traceability/requirements.yml",
                "agent/context-packs/T-001-converted-research.md",
            ]
            evidence["covered_requirements"] = ["R-999"]
            evidence["created_task_context_pack"] = "agent/context-packs/T-001-converted-research.md"

            result = resume_run(
                root,
                "r-created-task",
                executor_output="Created an accepted DCR and ready task context pack.",
                touched_paths=list(evidence["durable_artifacts"]),
                test_status="passed",
                acceptance_evidence=evidence,
            )

            self.assertEqual(result["state"]["status"], "complete")
            self.assertEqual(result["state"]["task_preparation"]["dcrs"], ["DCR-0099"])
            self.assertIn("agent/context-packs/**", result["state"]["allowed_paths"])
            executor_event = _executor_event(root, "r-created-task")
            self.assertEqual(
                executor_event["acceptance_evidence"]["created_task_context_pack"],
                "agent/context-packs/T-001-converted-research.md",
            )

    def test_valid_research_evidence_completes_with_terse_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-evidence")

            package = submit_runner_result(
                root,
                "r-evidence",
                {
                    "schema": RUNNER_RESULT_SCHEMA,
                    "executor_output": "Done.",
                    "touched_paths": ["docs/change-requests/DCR-0099-research.md"],
                    "test_status": "passed",
                    "acceptance_evidence": _valid_research_evidence(),
                },
            )

            step = package["step"]
            self.assertEqual(step["state"]["status"], "complete")
            self.assertEqual(step["review"]["decision"], "complete")
            self.assertIn("acceptance_evidence", step["review"]["evidence_refs"])

            event_path = root / "agent" / "runs" / "r-evidence" / "events.jsonl"
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
            executor_event = next(event for event in events if event["kind"] == "executor_output")
            self.assertEqual(
                executor_event["acceptance_evidence"]["schema"],
                "agentspec.research_acceptance_evidence.v0",
            )

    def test_unclassified_research_pause_without_evidence_still_auto_continues(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-unclear")

            result = resume_run(
                root,
                "r-unclear",
                executor_output="Logged a finding.",
                touched_paths=["reports/dogfood/2026-05-02-finding.md"],
                test_status="not_run",
            )

            self.assertEqual(result["state"]["status"], "running")
            self.assertEqual(result["state"]["last_decision"], "auto_continue")
            self.assertEqual(result["review"]["decision"], "pause_for_human")


class LoopAutonomousFallbackTests(unittest.TestCase):
    def test_loop_autonomous_with_empty_queue_enters_research_mode(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            # No context packs added → task_next returns nothing.

            result = loop_run(root, mode="autonomous", run_id="r-loop-research")
            state = result["state"]
            self.assertTrue(result["started"])
            self.assertEqual(state["mode"], "research")
            self.assertEqual(state["context_pack"], RESEARCH_CONTEXT_PACK_SENTINEL)

    def test_loop_existing_research_run_completes_when_ready_task_exists(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_workspace(root)
            start_research_run(root, run_id="r-converted")
            pack = root / "agent" / "context-packs" / "T-001-prepared-task.md"
            pack.write_text(
                "\n".join(
                    [
                        "# T-001: Prepared task",
                        "",
                        "Type: `implementation`",
                        "",
                        "## Requirements",
                        "",
                        "- `R-142` Autonomous run supports a research fallback.",
                        "",
                        "## Allowed Paths",
                        "",
                        "- `agentspec/run.py`",
                    ]
                ),
                encoding="utf-8",
            )

            result = loop_run(root, mode="autonomous", run_id="r-converted")

            state = result["state"]
            self.assertFalse(result["started"])
            self.assertEqual(result["selected_task"]["id"], "T-001")
            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["last_decision"], "complete")
            self.assertEqual(
                state["completion_reason"],
                "Research conversion completed because a ready task context pack exists.",
            )
            self.assertEqual(state["converted_task"]["context_pack"], "agent/context-packs/T-001-prepared-task.md")
            events = _events(root, "r-converted")
            self.assertTrue(any(event["kind"] == "research_conversion_completed" for event in events))


if __name__ == "__main__":
    unittest.main()


def _valid_research_evidence() -> dict:
    return {
        "schema": "agentspec.research_acceptance_evidence.v0",
        "durable_artifacts": [
            "docs/change-requests/DCR-0099-research.md",
            "docs/discovery/open-questions.yml",
        ],
        "allowed_path_confirmation": True,
        "verification_commands": [
            {"command": "git diff --check", "status": "passed"},
            {"command": "aspec doctor", "status": "passed"},
        ],
        "covered_requirements": ["R-142"],
        "covered_questions": ["Q-024"],
        "source_checks": ["DCR parses with aspec dcr list"],
        "no_task_context_pack_reason": "Research mode intentionally produced proposal artifacts only.",
    }


def _seed_git_dirty_research_workspace(root: Path) -> None:
    _seed_workspace(root)
    (root / ".gitignore").write_text("agent/runs/\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "schema.ts").write_text("seed\n", encoding="utf-8")
    _git(root, "init")
    _git(root, "add", ".")
    _git(
        root,
        "-c",
        "user.email=test@example.com",
        "-c",
        "user.name=AgentSpec Test",
        "commit",
        "-m",
        "seed",
    )
    (root / "src" / "schema.ts").write_text("dirty before run\n", encoding="utf-8")


def _executor_event(root: Path, run_id: str) -> dict:
    events = _events(root, run_id)
    return next(event for event in events if event["kind"] == "executor_output")


def _events(root: Path, run_id: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (root / "agent" / "runs" / run_id / "events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _git(root: Path, *args: str) -> None:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
