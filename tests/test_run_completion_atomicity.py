"""Tests for R-146 / DCR-0024: atomic completion + research-mode ledger guard."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentspec.init import init_project
from agentspec.io import load_data
from agentspec.run import resume_run, start_research_run, start_run
from agentspec.run_transitions import (
    MODEL_REVIEW_UNAVAILABLE_FLAG,
    halted_run_accepts_corrected_evidence,
    is_model_review_unavailable_pause,
    next_action_for_status,
    status_for_decision,
)


def _seed_implementation_pack(root: Path, slug: str = "T-996-atomicity-fixture") -> Path:
    init_project(root)
    pack_dir = root / "agent" / "context-packs"
    pack_dir.mkdir(parents=True, exist_ok=True)
    pack = pack_dir / f"{slug}.md"
    (root / "agentspec").mkdir(exist_ok=True)
    (root / "agentspec" / "fixture_target.py").write_text("", encoding="utf-8")
    pack.write_text(
        "# T-996: Fixture\n\nType: `implementation`\n\n"
        "## Allowed Paths\n\n- `agentspec/fixture_target.py`\n",
        encoding="utf-8",
    )
    return pack


def _ledger_path(root: Path) -> Path:
    return root / "agent" / "task-ledger.yml"


def _ledger_tasks(root: Path) -> dict:
    if not _ledger_path(root).exists():
        return {}
    data = load_data(_ledger_path(root), {}) or {}
    return data.get("tasks", {})


class RunTransitionBoundaryTests(unittest.TestCase):
    """R-146/DCR-0087: transition helpers stay readable and deterministic."""

    def test_status_for_decision_uses_safe_paused_default(self) -> None:
        self.assertEqual(status_for_decision("auto_continue"), "running")
        self.assertEqual(status_for_decision("pause_for_human"), "paused")
        self.assertEqual(status_for_decision("halt"), "halted")
        self.assertEqual(status_for_decision("complete"), "complete")
        self.assertEqual(status_for_decision("unknown"), "paused")

    def test_next_action_for_status_uses_safe_human_default(self) -> None:
        self.assertEqual(next_action_for_status("started"), "continue_executor")
        self.assertEqual(next_action_for_status("running"), "continue_executor")
        self.assertEqual(next_action_for_status("paused"), "await_human")
        self.assertEqual(next_action_for_status("complete"), "complete")
        self.assertEqual(next_action_for_status("halted"), "stop")
        self.assertEqual(next_action_for_status("aborted"), "stop")
        self.assertEqual(next_action_for_status("unknown"), "await_human")

    def test_halted_research_run_accepts_infrastructure_correction(self) -> None:
        self.assertTrue(
            halted_run_accepts_corrected_evidence(
                {"mode": "research"},
                [{"kind": "autonomous_infrastructure_block"}],
            )
        )

    def test_quality_review_halt_accepts_corrected_evidence(self) -> None:
        self.assertTrue(
            halted_run_accepts_corrected_evidence(
                {"mode": "autonomous"},
                [
                    {
                        "kind": "autonomous_pause_to_dcr",
                        "reason": "Quality reviewer rejected autonomous-mode complete: missing evidence",
                    }
                ],
            )
        )

    def test_later_reviewer_halt_blocks_corrected_evidence(self) -> None:
        self.assertFalse(
            halted_run_accepts_corrected_evidence(
                {"mode": "autonomous", "infrastructure_blocker": {"kind": "model"}},
                [{"kind": "reviewer_verdict", "decision": "halt"}],
            )
        )

    def test_supervised_run_never_accepts_corrected_halt_evidence(self) -> None:
        self.assertFalse(
            halted_run_accepts_corrected_evidence(
                {"mode": "supervised", "infrastructure_blocker": {"kind": "model"}},
                [{"kind": "autonomous_infrastructure_block"}],
            )
        )

    def test_model_review_unavailable_pause_uses_policy_flag(self) -> None:
        review = mock.Mock(policy_flags=[MODEL_REVIEW_UNAVAILABLE_FLAG])

        self.assertTrue(is_model_review_unavailable_pause(review))


class ResearchModeLedgerGuardTests(unittest.TestCase):
    """R-146: research-mode `complete` does not modify agent/task-ledger.yml."""

    def test_research_run_complete_does_not_pollute_task_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            init_project(root)
            ledger_before = _ledger_tasks(root)

            start_research_run(root, run_id="r-research-complete")
            result = resume_run(
                root,
                "r-research-complete",
                executor_output=(
                    "All acceptance criteria are met. Findings recorded; verification passed."
                ),
                # Research mode requires writes inside the research-allowed
                # surface (reports/dogfood/**, docs/discovery/open-questions.yml,
                # docs/change-requests/**) — anything else trips the policy gate.
                touched_paths=["reports/dogfood/finding.md"],
                test_status="passed",
            )
            state = result["state"]

            # Pre-condition: the run actually reached `complete`.
            self.assertEqual(state["mode"], "research")
            self.assertEqual(state["status"], "complete")
            self.assertEqual(state["last_decision"], "complete")

            # Acceptance: ledger has no entry for the research sentinel and
            # is unchanged from before the run.
            ledger_after = _ledger_tasks(root)
            self.assertNotIn("<research-mode>", ledger_after)
            self.assertEqual(ledger_after, ledger_before)


class ImplementationCompleteLedgerRegressionTests(unittest.TestCase):
    """R-146 regression guard: implementation `complete` still writes ledger."""

    def test_implementation_run_complete_records_pack_in_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_implementation_pack(root)
            start_run(root, pack, run_id="r-impl-complete")
            resume_run(
                root,
                "r-impl-complete",
                executor_output=(
                    "All acceptance criteria are met. Verification passed; tests are green."
                ),
                touched_paths=["agentspec/fixture_target.py"],
                test_status="passed",
            )

            tasks = _ledger_tasks(root)
            pack_key = "agent/context-packs/T-996-atomicity-fixture.md"
            self.assertIn(pack_key, tasks)
            self.assertEqual(tasks[pack_key]["status"], "complete")


class CompletionWriteOrderingTests(unittest.TestCase):
    """R-146: ledger write must precede state finalization on `complete`."""

    def test_state_file_unchanged_when_ledger_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = _seed_implementation_pack(root, slug="T-995-ordering-fixture")
            start_run(root, pack, run_id="r-impl-order")

            state_path = root / "agent" / "runs" / "r-impl-order" / "state.yml"
            pre_state = load_data(state_path)

            with mock.patch(
                "agentspec.task.record_task_ledger_status",
                side_effect=OSError("simulated ledger write failure"),
            ):
                with self.assertRaises(OSError):
                    resume_run(
                        root,
                        "r-impl-order",
                        executor_output=(
                            "All acceptance criteria are met. Verification passed."
                        ),
                        touched_paths=["agentspec/fixture_target.py"],
                        test_status="passed",
                    )

            # Acceptance: ledger-first ordering means the state file must
            # not have been advanced to `complete`. Anything other than
            # `started`/its initial last_decision implies the state file
            # was finalized before the ledger write was attempted.
            post_state = load_data(state_path)
            self.assertNotEqual(post_state.get("status"), "complete")
            self.assertNotEqual(post_state.get("last_decision"), "complete")
            self.assertEqual(post_state.get("status"), pre_state.get("status"))
            self.assertEqual(
                post_state.get("last_decision"), pre_state.get("last_decision")
            )


if __name__ == "__main__":
    unittest.main()
