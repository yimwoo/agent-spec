"""Controlled cross-agent evaluation manifest, evidence, and report tests."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from agentspec.cli import main
from agentspec.eval import (
    EVALUATION_MANIFEST_SCHEMA,
    EVALUATION_REPORT_SCHEMA,
    EVALUATION_RUN_SCHEMA,
    build_evaluation_report,
    format_evaluation_report,
    load_evaluation_manifest,
    record_evaluation_run,
    validate_evaluation_manifest,
    write_evaluation_report,
)
from agentspec.io import load_data, write_data


class EvaluationCliTests(unittest.TestCase):
    def test_manifest_pins_cross_agent_corpus_conditions_and_oracles(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            manifest_path = _write_manifest(Path(td))

            manifest = load_evaluation_manifest(manifest_path)

            self.assertEqual(manifest["schema"], EVALUATION_MANIFEST_SCHEMA)
            self.assertEqual({item["id"] for item in manifest["providers"]}, {"codex", "claude"})
            self.assertEqual({item["agentspec"] for item in manifest["conditions"]}, {True, False})
            self.assertEqual(manifest["tasks"][0]["oracle"]["revision"], "oracle-v1")
            self.assertEqual(manifest["environment"]["revision"], "image-sha-123")
            self.assertFalse(manifest["authority"]["executes_provider"])
            self.assertFalse(manifest["authority"]["expands_task_scope"])

    def test_manifest_validation_requires_both_providers_and_oracle_metadata(self) -> None:
        payload = _manifest_payload()
        payload["providers"] = [{"id": "codex", "model": "gpt-5.5"}]
        with self.assertRaisesRegex(ValueError, "both codex and claude"):
            validate_evaluation_manifest(payload)

        payload = _manifest_payload()
        del payload["tasks"][0]["oracle"]["revision"]
        with self.assertRaisesRegex(ValueError, "revision"):
            validate_evaluation_manifest(payload)

    def test_paired_report_aggregates_requested_metrics_and_raw_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = _write_manifest(root)
            for provider in ("codex", "claude"):
                _record(
                    root,
                    manifest_path,
                    run_id=f"{provider}-with",
                    provider=provider,
                    condition="with-agentspec",
                    completed=True,
                    regressions=0,
                    retries=0,
                    interventions=0,
                    tokens=900,
                    cost=0.9,
                    duration=60,
                    findings=0,
                    escaped=0,
                )
                _record(
                    root,
                    manifest_path,
                    run_id=f"{provider}-control",
                    provider=provider,
                    condition="control",
                    completed=False,
                    regressions=2,
                    retries=2,
                    interventions=1,
                    tokens=1200,
                    cost=1.2,
                    duration=100,
                    findings=1,
                    escaped=1,
                )

            report = build_evaluation_report(root, manifest_path)

            self.assertEqual(report["schema"], EVALUATION_REPORT_SCHEMA)
            self.assertEqual(report["expected_run_count"], 4)
            self.assertEqual(report["recorded_run_count"], 4)
            self.assertEqual(report["classifications"], {"valid": 2, "limited": 0, "invalid": 0})
            self.assertEqual(report["deltas"]["completion_rate"], 1.0)
            self.assertEqual(report["deltas"]["regressions_average"], -2.0)
            self.assertEqual(report["deltas"]["retries_average"], -2.0)
            self.assertEqual(report["deltas"]["human_interventions_average"], -1.0)
            self.assertEqual(report["deltas"]["tokens_average"], -300.0)
            self.assertEqual(report["deltas"]["cost_usd_average"], -0.3)
            self.assertEqual(report["deltas"]["escaped_defects_average"], -1.0)
            self.assertEqual(report["runs"][0]["provenance"]["evidence"], ["ci/run.json"])
            self.assertIn("descriptive evidence", format_evaluation_report(report))

    def test_incompatible_model_is_invalid_and_does_not_enter_paired_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = _write_manifest(root)
            _record(root, manifest_path, run_id="codex-with", provider="codex", condition="with-agentspec")
            _record(
                root,
                manifest_path,
                run_id="codex-control",
                provider="codex",
                condition="control",
                model="different-model",
            )

            report = build_evaluation_report(root, manifest_path)

            codex_pair = next(pair for pair in report["pairs"] if pair["provider"] == "codex")
            self.assertEqual(codex_pair["classification"], "invalid")
            self.assertFalse(codex_pair["comparable"])
            self.assertIn("model does not match", "\n".join(codex_pair["reasons"]))
            self.assertEqual(report["paired_metrics"]["with-agentspec"]["run_count"], 0)
            self.assertIsNone(report["deltas"]["completion_rate"])

    def test_partial_evidence_is_limited_but_preserves_known_denominators(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = _write_manifest(root)
            _record(
                root,
                manifest_path,
                run_id="codex-with",
                provider="codex",
                condition="with-agentspec",
                metrics={"completed": True},
            )
            _record(
                root,
                manifest_path,
                run_id="codex-control",
                provider="codex",
                condition="control",
                metrics={"completed": False},
            )

            first = build_evaluation_report(root, manifest_path)
            second = build_evaluation_report(root, manifest_path)

            self.assertEqual(first, second)
            codex_pair = next(pair for pair in first["pairs"] if pair["provider"] == "codex")
            self.assertEqual(codex_pair["classification"], "limited")
            self.assertTrue(codex_pair["comparable"])
            self.assertEqual(first["paired_metrics"]["with-agentspec"]["completion"]["known"], 1)
            self.assertEqual(first["paired_metrics"]["with-agentspec"]["regressions"]["known"], 0)
            self.assertEqual(first["deltas"]["completion_rate"], 1.0)
            self.assertIsNone(first["deltas"]["regressions_average"])

    def test_cli_validates_records_and_writes_deterministic_reports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = _write_manifest(root)

            validation = _run_json(
                ["--root", str(root), "eval", "validate", str(manifest_path), "--json"]
            )
            self.assertEqual(validation["id"], "EXP-agent-lifecycle")

            run_payload = _run_payload(
                run_id="codex-with",
                provider="codex",
                condition="with-agentspec",
            )
            recorded = _run_json(
                [
                    "--root",
                    str(root),
                    "eval",
                    "record",
                    str(manifest_path),
                    "--input-json",
                    json.dumps(run_payload),
                    "--json",
                ]
            )
            self.assertEqual(recorded["schema"], EVALUATION_RUN_SCHEMA)
            self.assertFalse(recorded["authority"]["grants_external_service_access"])

            report = _run_json(
                ["--root", str(root), "eval", "report", str(manifest_path), "--json"]
            )
            self.assertEqual(report["schema"], EVALUATION_REPORT_SCHEMA)
            machine = root / report["report_paths"]["machine"]
            markdown = root / report["report_paths"]["markdown"]
            first_machine = machine.read_text(encoding="utf-8")
            first_markdown = markdown.read_text(encoding="utf-8")
            _run_json(["--root", str(root), "eval", "report", str(manifest_path), "--json"])
            self.assertEqual(machine.read_text(encoding="utf-8"), first_machine)
            self.assertEqual(markdown.read_text(encoding="utf-8"), first_markdown)
            self.assertEqual(load_data(machine)["schema"], EVALUATION_REPORT_SCHEMA)
            self.assertIn("not a causal claim", first_markdown)

    def test_run_evidence_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            manifest_path = _write_manifest(root)
            payload = _run_payload(run_id="codex-with", provider="codex", condition="with-agentspec")
            record_evaluation_run(root, manifest_path, payload)

            with self.assertRaisesRegex(ValueError, "immutable"):
                record_evaluation_run(root, manifest_path, payload)


def _manifest_payload() -> dict[str, object]:
    return {
        "schema": EVALUATION_MANIFEST_SCHEMA,
        "id": "EXP-agent-lifecycle",
        "title": "AgentSpec lifecycle A/B",
        "tasks": [
            {
                "id": "TASK-fix",
                "source": "corpus/fix-bug.md",
                "revision": "sha256:task-123",
                "oracle": {"id": "oracle-tests", "type": "command", "revision": "oracle-v1"},
            }
        ],
        "conditions": [
            {"id": "with-agentspec", "agentspec": True},
            {"id": "control", "agentspec": False},
        ],
        "providers": [
            {"id": "codex", "model": "gpt-5.5"},
            {"id": "claude", "model": "claude-opus-4.8"},
        ],
        "environment": {"id": "ubuntu", "revision": "image-sha-123"},
        "limits": {"max_duration_seconds": 1800, "max_tokens": 100000, "max_retries": 3},
        "replicates": 1,
    }


def _write_manifest(root: Path) -> Path:
    path = root / "agent" / "evals" / "EXP-agent-lifecycle" / "manifest.yml"
    write_data(path, _manifest_payload())
    return path


def _record(
    root: Path,
    manifest_path: Path,
    *,
    run_id: str,
    provider: str,
    condition: str,
    model: str | None = None,
    completed: bool = True,
    regressions: int = 0,
    retries: int = 0,
    interventions: int = 0,
    tokens: int = 1000,
    cost: float = 1.0,
    duration: float = 90,
    findings: int = 0,
    escaped: int = 0,
    metrics: dict[str, object] | None = None,
) -> dict[str, object]:
    payload = _run_payload(
        run_id=run_id,
        provider=provider,
        condition=condition,
        model=model,
        metrics=metrics
        if metrics is not None
        else {
            "completed": completed,
            "regressions": regressions,
            "retries": retries,
            "human_interventions": interventions,
            "tokens": {"input": tokens // 2, "output": tokens // 2, "cached": 0, "total": tokens},
            "cost_usd": cost,
            "duration_seconds": duration,
            "review_findings": findings,
            "escaped_defects": escaped,
        },
    )
    return record_evaluation_run(root, manifest_path, payload)


def _run_payload(
    *,
    run_id: str,
    provider: str,
    condition: str,
    model: str | None = None,
    metrics: dict[str, object] | None = None,
) -> dict[str, object]:
    expected_model = "gpt-5.5" if provider == "codex" else "claude-opus-4.8"
    return {
        "schema": EVALUATION_RUN_SCHEMA,
        "id": run_id,
        "experiment_id": "EXP-agent-lifecycle",
        "task_id": "TASK-fix",
        "condition_id": condition,
        "provider": provider,
        "replicate": 1,
        "task_revision": "sha256:task-123",
        "model": model or expected_model,
        "environment": {"id": "ubuntu", "revision": "image-sha-123"},
        "limits": {"max_duration_seconds": 1800, "max_tokens": 100000, "max_retries": 3},
        "oracle": {"id": "oracle-tests", "type": "command", "revision": "oracle-v1"},
        "started_at": "2026-06-29T20:00:00Z",
        "completed_at": "2026-06-29T20:02:00Z",
        "metrics": metrics or {
            "completed": True,
            "regressions": 0,
            "retries": 0,
            "human_interventions": 0,
            "tokens": {"input": 500, "output": 500, "cached": 0, "total": 1000},
            "cost_usd": 1.0,
            "duration_seconds": 90,
            "review_findings": 0,
            "escaped_defects": 0,
        },
        "provenance": {
            "native_run_id": f"native-{run_id}",
            "evidence": ["ci/run.json"],
            "provider_log_digest": f"sha256:{run_id}",
        },
    }


def _run_json(args: list[str]) -> dict[str, object]:
    output = io.StringIO()
    with redirect_stdout(output):
        code = main(args)
    if code != 0:
        raise AssertionError(f"CLI failed with {code}: {args}\n{output.getvalue()}")
    return json.loads(output.getvalue())


if __name__ == "__main__":
    unittest.main()
