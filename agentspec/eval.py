"""Controlled cross-agent lifecycle experiment manifests and reports."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from .io import load_data, utc_now_iso, write_data, write_text
from .metrics import aggregate_evaluation_metrics


EVALUATION_MANIFEST_SCHEMA = "agentspec.evaluation_manifest.v0"
EVALUATION_RUN_SCHEMA = "agentspec.evaluation_run.v0"
EVALUATION_REPORT_SCHEMA = "agentspec.evaluation_report.v0"
EVALUATION_REPORT_PATH = Path("reports/eval")
EVALUATION_RUNS_PATH = Path("agent/evals")
REQUIRED_PROVIDERS = frozenset({"codex", "claude"})
COMPARABILITY_FIELDS = ("task_revision", "model", "environment", "limits", "oracle")
CORE_METRICS = (
    "completed",
    "regressions",
    "retries",
    "human_interventions",
    "tokens.total",
    "cost_usd",
    "duration_seconds",
)
OPTIONAL_METRICS = ("review_findings", "escaped_defects")


def load_evaluation_manifest(path: Path) -> dict[str, Any]:
    """Load and validate a versioned evaluation manifest."""

    try:
        payload = load_data(path.resolve(), None)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Could not load evaluation manifest {path}: {exc}") from exc
    manifest = validate_evaluation_manifest(payload)
    return {**manifest, "path": path.as_posix()}


def validate_evaluation_manifest(payload: Any) -> dict[str, Any]:
    """Validate and normalize one controlled A/B experiment manifest."""

    if not isinstance(payload, dict):
        raise ValueError("Evaluation manifest must be an object.")
    if payload.get("schema") != EVALUATION_MANIFEST_SCHEMA:
        raise ValueError(f"Evaluation manifest schema must be {EVALUATION_MANIFEST_SCHEMA}.")
    experiment_id = _required_identifier(payload, "id", "Evaluation manifest")
    tasks = _validate_tasks(payload.get("tasks"))
    conditions = _validate_conditions(payload.get("conditions"))
    providers = _validate_providers(payload.get("providers"))
    environment = _validate_named_revision(payload.get("environment"), "environment")
    limits = _validate_limits(payload.get("limits"))
    replicates = payload.get("replicates", 1)
    if not _positive_int(replicates):
        raise ValueError("Evaluation manifest replicates must be a positive integer.")
    return {
        "schema": EVALUATION_MANIFEST_SCHEMA,
        "id": experiment_id,
        "title": str(payload.get("title") or experiment_id),
        "description": payload.get("description"),
        "tasks": tasks,
        "conditions": conditions,
        "providers": providers,
        "environment": environment,
        "limits": limits,
        "replicates": replicates,
        "authority": {
            "mode": "evidence_only",
            "executes_provider": False,
            "expands_task_scope": False,
            "grants_external_service_access": False,
            "underlying_task_authority_required": True,
        },
    }


def record_evaluation_run(
    root: Path,
    manifest_path: Path,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Record immutable evidence for one externally executed experiment cell."""

    manifest = load_evaluation_manifest(manifest_path)
    if not isinstance(payload, dict):
        raise ValueError("Evaluation run evidence must be an object.")
    if payload.get("schema") not in {None, EVALUATION_RUN_SCHEMA}:
        raise ValueError(f"Evaluation run schema must be {EVALUATION_RUN_SCHEMA}.")
    run_id = str(payload.get("id") or f"EVALRUN-{uuid.uuid4().hex[:12]}")
    if not _safe_identifier(run_id):
        raise ValueError("Evaluation run id contains unsupported characters.")
    if payload.get("experiment_id") not in {None, manifest["id"]}:
        raise ValueError("Evaluation run experiment_id does not match the manifest.")
    task_id = _required_identifier(payload, "task_id", "Evaluation run")
    condition_id = _required_identifier(payload, "condition_id", "Evaluation run")
    provider = _required_identifier(payload, "provider", "Evaluation run")
    task = _find_by_id(manifest["tasks"], task_id, "task")
    _find_by_id(manifest["conditions"], condition_id, "condition")
    _find_by_id(manifest["providers"], provider, "provider")
    replicate = payload.get("replicate", 1)
    if not _positive_int(replicate) or int(replicate) > int(manifest["replicates"]):
        raise ValueError("Evaluation run replicate is outside the manifest replicate range.")
    metrics = _validate_run_metrics(payload.get("metrics"))
    provenance = _validate_provenance(payload.get("provenance"))
    started_at = _optional_timestamp(payload.get("started_at"), "started_at")
    completed_at = _optional_timestamp(payload.get("completed_at"), "completed_at")
    if started_at and completed_at and _parse_datetime(completed_at) < _parse_datetime(started_at):
        raise ValueError("Evaluation run completed_at cannot precede started_at.")
    record = {
        "schema": EVALUATION_RUN_SCHEMA,
        "id": run_id,
        "experiment_id": manifest["id"],
        "task_id": task_id,
        "condition_id": condition_id,
        "provider": provider,
        "replicate": replicate,
        "task_revision": payload.get("task_revision"),
        "model": payload.get("model"),
        "environment": payload.get("environment"),
        "limits": payload.get("limits"),
        "oracle": payload.get("oracle"),
        "started_at": started_at,
        "completed_at": completed_at,
        "recorded_at": utc_now_iso(),
        "metrics": metrics,
        "provenance": provenance,
        "task_source": task["source"],
        "authority": manifest["authority"],
    }
    relative_path = EVALUATION_RUNS_PATH / str(manifest["id"]) / "runs" / f"{run_id}.yml"
    destination = root.resolve() / relative_path
    if destination.exists():
        raise ValueError(f"Evaluation run {run_id} already exists; run evidence is immutable.")
    write_data(destination, record)
    return {**record, "path": relative_path.as_posix()}


def build_evaluation_report(root: Path, manifest_path: Path) -> dict[str, Any]:
    """Build a deterministic comparative report without executing provider work."""

    root = root.resolve()
    manifest = load_evaluation_manifest(manifest_path)
    runs, invalid_records = _load_evaluation_runs(root, str(manifest["id"]))
    pairs = _build_pairs(manifest, runs)
    classifications = Counter(str(pair["classification"]) for pair in pairs)
    conditions = {str(item["id"]): bool(item["agentspec"]) for item in manifest["conditions"]}
    condition_metrics = {
        condition_id: aggregate_evaluation_metrics(
            [run for run in runs if run.get("condition_id") == condition_id]
        )
        for condition_id in sorted(conditions)
    }
    comparable_runs = [
        run
        for pair in pairs
        if pair.get("comparable")
        for run in _pair_runs(pair)
    ]
    paired_metrics = {
        condition_id: aggregate_evaluation_metrics(
            [run for run in comparable_runs if run.get("condition_id") == condition_id]
        )
        for condition_id in sorted(conditions)
    }
    deltas = _comparison_deltas(paired_metrics, conditions)
    limitations = _report_limitations(pairs, invalid_records, paired_metrics)
    return {
        "schema": EVALUATION_REPORT_SCHEMA,
        "experiment_id": manifest["id"],
        "manifest_path": manifest_path.as_posix(),
        "manifest_digest": _digest({key: value for key, value in manifest.items() if key != "path"}),
        "authority": manifest["authority"],
        "expected_run_count": (
            len(manifest["tasks"])
            * len(manifest["conditions"])
            * len(manifest["providers"])
            * int(manifest["replicates"])
        ),
        "recorded_run_count": len(runs),
        "classifications": {
            "valid": classifications.get("valid", 0),
            "limited": classifications.get("limited", 0),
            "invalid": classifications.get("invalid", 0),
        },
        "pairs": pairs,
        "metric_scopes": {
            "condition_metrics": "descriptive aggregation over every recorded run, including invalid cells",
            "paired_metrics": "aggregation over metadata-compatible paired cells only",
            "deltas": "AgentSpec paired metrics minus control paired metrics",
        },
        "condition_metrics": condition_metrics,
        "paired_metrics": paired_metrics,
        "deltas": deltas,
        "runs": runs,
        "invalid_records": invalid_records,
        "conclusions": _report_conclusions(deltas, pairs),
        "limitations": limitations,
    }


def write_evaluation_report(root: Path, manifest_path: Path) -> dict[str, Any]:
    """Write deterministic machine-readable and Markdown evaluation reports."""

    report = build_evaluation_report(root, manifest_path)
    directory = root.resolve() / EVALUATION_REPORT_PATH / str(report["experiment_id"])
    machine_path = directory / "latest.yml"
    markdown_path = directory / "latest.md"
    write_data(machine_path, report)
    write_text(markdown_path, format_evaluation_report(report) + "\n")
    return {
        **report,
        "report_paths": {
            "machine": machine_path.relative_to(root.resolve()).as_posix(),
            "markdown": markdown_path.relative_to(root.resolve()).as_posix(),
        },
    }


def format_evaluation_report(report: dict[str, Any]) -> str:
    """Format a deterministic, limitation-forward controlled-evaluation report."""

    raw_counts = report.get("classifications")
    counts: dict[str, Any] = raw_counts if isinstance(raw_counts, dict) else {}
    lines = [
        f"# AgentSpec Evaluation: {report.get('experiment_id')}",
        "",
        "This report is descriptive evidence, not a causal claim. Valid paired cells share task, provider, model, environment, limits, oracle, and replicate metadata.",
        "",
        "## Coverage",
        "",
        f"- Expected runs: {report.get('expected_run_count', 0)}",
        f"- Recorded runs: {report.get('recorded_run_count', 0)}",
        f"- Valid pairs: {counts.get('valid', 0)}",
        f"- Limited pairs: {counts.get('limited', 0)}",
        f"- Invalid pairs: {counts.get('invalid', 0)}",
        "",
        "## Comparative deltas (AgentSpec - control)",
        "",
    ]
    deltas = report.get("deltas") if isinstance(report.get("deltas"), dict) else {}
    if deltas:
        for name in sorted(deltas):
            lines.append(f"- {name}: {_format_delta(deltas[name])}")
    else:
        lines.append("- No compatible paired measurements are available.")
    lines.extend(["", "## Conclusions", ""])
    conclusions = report.get("conclusions") if isinstance(report.get("conclusions"), list) else []
    if conclusions:
        lines.extend(f"- {item}" for item in conclusions)
    else:
        lines.append("- None.")
    lines.extend(["", "## Limitations", ""])
    limitations = report.get("limitations") if isinstance(report.get("limitations"), list) else []
    if limitations:
        lines.extend(f"- {item}" for item in limitations)
    else:
        lines.append("- None recorded.")
    return "\n".join(lines)


def _validate_tasks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("Evaluation manifest requires a non-empty tasks list.")
    tasks: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("Each evaluation task must be an object.")
        task_id = _required_identifier(raw, "id", "Evaluation task")
        source = _required_text(raw, "source", "Evaluation task")
        revision = _required_text(raw, "revision", "Evaluation task")
        oracle = _validate_named_revision(raw.get("oracle"), "success oracle", require_type=True)
        tasks.append({"id": task_id, "source": source, "revision": revision, "oracle": oracle})
    _require_unique_ids(tasks, "task")
    return tasks


def _validate_conditions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError("Evaluation manifest requires exactly two A/B conditions.")
    conditions: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict) or not isinstance(raw.get("agentspec"), bool):
            raise ValueError("Each condition requires an id and boolean agentspec field.")
        conditions.append(
            {
                "id": _required_identifier(raw, "id", "Evaluation condition"),
                "agentspec": raw["agentspec"],
                "description": raw.get("description"),
            }
        )
    _require_unique_ids(conditions, "condition")
    if {condition["agentspec"] for condition in conditions} != {True, False}:
        raise ValueError("Evaluation conditions must contain one AgentSpec and one control condition.")
    return conditions


def _validate_providers(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("Evaluation manifest requires provider definitions.")
    providers: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("Each provider definition must be an object.")
        providers.append(
            {
                "id": _required_identifier(raw, "id", "Evaluation provider"),
                "model": _required_text(raw, "model", "Evaluation provider"),
            }
        )
    _require_unique_ids(providers, "provider")
    provider_ids = {provider["id"] for provider in providers}
    if not REQUIRED_PROVIDERS.issubset(provider_ids):
        raise ValueError("Controlled cross-agent manifests must include both codex and claude providers.")
    return providers


def _validate_named_revision(value: Any, label: str, *, require_type: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"Evaluation {label} must be an object.")
    normalized = dict(value)
    normalized["id"] = _required_identifier(value, "id", f"Evaluation {label}")
    normalized["revision"] = _required_text(value, "revision", f"Evaluation {label}")
    if require_type:
        normalized["type"] = _required_text(value, "type", f"Evaluation {label}")
    return normalized


def _validate_limits(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("Evaluation limits must be an object.")
    required_positive = ("max_duration_seconds", "max_tokens")
    for field in required_positive:
        if not _positive_int(value.get(field)):
            raise ValueError(f"Evaluation limits.{field} must be a positive integer.")
    retries = value.get("max_retries")
    if not _non_negative_int(retries):
        raise ValueError("Evaluation limits.max_retries must be a non-negative integer.")
    return dict(value)


def _validate_run_metrics(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("Evaluation run metrics must be an object.")
    metrics = dict(value)
    completed = metrics.get("completed")
    if completed is not None and not isinstance(completed, bool):
        raise ValueError("Evaluation metric completed must be boolean when present.")
    for field in (
        "regressions",
        "retries",
        "human_interventions",
        "cost_usd",
        "duration_seconds",
        "review_findings",
        "escaped_defects",
    ):
        metric = metrics.get(field)
        if metric is not None and not _non_negative_number(metric):
            raise ValueError(f"Evaluation metric {field} must be non-negative when present.")
    tokens = metrics.get("tokens")
    if tokens is not None:
        if not isinstance(tokens, dict):
            raise ValueError("Evaluation metric tokens must be an object.")
        for field, metric in tokens.items():
            if field not in {"input", "output", "cached", "total"} or not _non_negative_number(metric):
                raise ValueError("Token metrics support non-negative input, output, cached, and total fields.")
    return metrics


def _validate_provenance(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise ValueError("Evaluation run requires raw provenance.")
    native_run_id = value.get("native_run_id")
    evidence = value.get("evidence")
    if not (isinstance(native_run_id, str) and native_run_id.strip()) and not (
        isinstance(evidence, list) and any(isinstance(item, str) and item for item in evidence)
    ):
        raise ValueError("Evaluation provenance requires native_run_id or evidence references.")
    return dict(value)


def _load_evaluation_runs(root: Path, experiment_id: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    directory = root / EVALUATION_RUNS_PATH / experiment_id / "runs"
    if not directory.exists():
        return [], []
    runs: list[dict[str, Any]] = []
    invalid: list[dict[str, str]] = []
    for path in sorted(directory.glob("*.yml")):
        relative = path.relative_to(root).as_posix()
        try:
            payload = load_data(path, None)
        except (json.JSONDecodeError, OSError) as exc:
            invalid.append({"path": relative, "reason": str(exc)})
            continue
        if not isinstance(payload, dict) or payload.get("schema") != EVALUATION_RUN_SCHEMA:
            invalid.append({"path": relative, "reason": "Unsupported or malformed run evidence."})
            continue
        error = _loaded_run_error(payload, experiment_id)
        if error:
            invalid.append({"path": relative, "reason": error})
            continue
        runs.append({**payload, "path": relative})
    runs.sort(
        key=lambda item: (
            str(item.get("provider")),
            str(item.get("task_id")),
            int(item.get("replicate", 0)),
            str(item.get("condition_id")),
            str(item.get("id")),
        )
    )
    return runs, invalid


def _loaded_run_error(payload: dict[str, Any], experiment_id: str) -> str | None:
    for field in ("id", "task_id", "condition_id", "provider"):
        value = payload.get(field)
        if not isinstance(value, str) or not value:
            return f"Run evidence requires a non-empty {field}."
    if payload.get("experiment_id") != experiment_id:
        return "Run evidence experiment_id does not match its experiment directory."
    if not _positive_int(payload.get("replicate")):
        return "Run evidence replicate must be a positive integer."
    if not isinstance(payload.get("metrics"), dict):
        return "Run evidence metrics must be an object."
    if not isinstance(payload.get("provenance"), dict):
        return "Run evidence provenance must be an object."
    return None


def _build_pairs(manifest: dict[str, Any], runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with_condition = next(item for item in manifest["conditions"] if item["agentspec"])
    control_condition = next(item for item in manifest["conditions"] if not item["agentspec"])
    pairs: list[dict[str, Any]] = []
    for task in manifest["tasks"]:
        for provider in manifest["providers"]:
            for replicate in range(1, int(manifest["replicates"]) + 1):
                expected = {
                    "task_revision": task["revision"],
                    "model": provider["model"],
                    "environment": manifest["environment"],
                    "limits": manifest["limits"],
                    "oracle": task["oracle"],
                }
                cells = {
                    "agentspec": _matching_runs(
                        runs,
                        task_id=str(task["id"]),
                        provider=str(provider["id"]),
                        condition_id=str(with_condition["id"]),
                        replicate=replicate,
                    ),
                    "control": _matching_runs(
                        runs,
                        task_id=str(task["id"]),
                        provider=str(provider["id"]),
                        condition_id=str(control_condition["id"]),
                        replicate=replicate,
                    ),
                }
                pairs.append(
                    _classify_pair(
                        pair_id=f"{task['id']}:{provider['id']}:r{replicate}",
                        task_id=str(task["id"]),
                        provider=str(provider["id"]),
                        replicate=replicate,
                        expected=expected,
                        cells=cells,
                    )
                )
    return pairs


def _classify_pair(
    *,
    pair_id: str,
    task_id: str,
    provider: str,
    replicate: int,
    expected: dict[str, Any],
    cells: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    reasons: list[str] = []
    invalid = False
    if any(len(cell) > 1 for cell in cells.values()):
        invalid = True
        reasons.append("Duplicate run evidence exists for one or more experiment cells.")
    selected = {name: values[0] if len(values) == 1 else None for name, values in cells.items()}
    if any(run is None for run in selected.values()):
        reasons.append("One or both paired condition runs are missing.")
    else:
        for name, run in selected.items():
            if not isinstance(run, dict):
                continue
            for field in COMPARABILITY_FIELDS:
                actual = run.get(field)
                if actual is None:
                    reasons.append(f"{name} run is missing comparability field {field}.")
                elif _canonical(actual) != _canonical(expected[field]):
                    invalid = True
                    reasons.append(f"{name} run {field} does not match the manifest.")
            missing_metrics = [field for field in CORE_METRICS if _metric_value(run, field) is None]
            if missing_metrics:
                reasons.append(f"{name} run is missing core metrics: {', '.join(missing_metrics)}.")
            optional_missing = [field for field in OPTIONAL_METRICS if _metric_value(run, field) is None]
            if optional_missing:
                reasons.append(f"{name} run has unavailable optional metrics: {', '.join(optional_missing)}.")
    both_present = all(isinstance(run, dict) for run in selected.values())
    metadata_complete = both_present and not any(
        isinstance(run, dict) and any(run.get(field) is None for field in COMPARABILITY_FIELDS)
        for run in selected.values()
    )
    comparable = bool(both_present and metadata_complete and not invalid)
    classification = "invalid" if invalid else ("limited" if reasons else "valid")
    return {
        "id": pair_id,
        "task_id": task_id,
        "provider": provider,
        "replicate": replicate,
        "classification": classification,
        "comparable": comparable,
        "reasons": _dedupe(reasons),
        "expected": expected,
        "agentspec_run": selected["agentspec"],
        "control_run": selected["control"],
    }


def _comparison_deltas(
    paired_metrics: dict[str, dict[str, Any]],
    conditions: dict[str, bool],
) -> dict[str, float | None]:
    agentspec_id = next(condition_id for condition_id, enabled in conditions.items() if enabled)
    control_id = next(condition_id for condition_id, enabled in conditions.items() if not enabled)
    agentspec = paired_metrics[agentspec_id]
    control = paired_metrics[control_id]
    deltas: dict[str, float | None] = {
        "completion_rate": _difference(
            _nested(agentspec, "completion.rate"),
            _nested(control, "completion.rate"),
        )
    }
    for metric in (
        "regressions",
        "retries",
        "human_interventions",
        "tokens",
        "cost_usd",
        "duration_seconds",
        "review_findings",
        "escaped_defects",
    ):
        deltas[f"{metric}_average"] = _difference(
            _nested(agentspec, f"{metric}.average"),
            _nested(control, f"{metric}.average"),
        )
    return deltas


def _report_conclusions(deltas: dict[str, float | None], pairs: list[dict[str, Any]]) -> list[str]:
    comparable = sum(1 for pair in pairs if pair.get("comparable"))
    if not comparable:
        return ["No compatible paired cells are available; no AgentSpec-versus-control conclusion is supported."]
    completion = deltas.get("completion_rate")
    regressions = deltas.get("regressions_average")
    interventions = deltas.get("human_interventions_average")
    conclusion = f"{comparable} paired cell(s) are metadata-compatible."
    if completion is not None:
        conclusion += f" AgentSpec completion-rate delta is {completion:+.4f}."
    if regressions is not None:
        conclusion += f" Average regression delta is {regressions:+.4f}."
    if interventions is not None:
        conclusion += f" Average human-intervention delta is {interventions:+.4f}."
    return [conclusion]


def _report_limitations(
    pairs: list[dict[str, Any]],
    invalid_records: list[dict[str, str]],
    paired_metrics: dict[str, dict[str, Any]],
) -> list[str]:
    limitations = [
        f"{pair['id']} ({pair['classification']}): {reason}"
        for pair in pairs
        if pair.get("classification") != "valid"
        for reason in pair.get("reasons", [])
    ]
    limitations.extend(
        f"Invalid run record {record['path']}: {record['reason']}" for record in invalid_records
    )
    if all(int(metrics.get("run_count", 0)) == 0 for metrics in paired_metrics.values()):
        limitations.append("No compatible paired run evidence contributes to comparative metrics.")
    return _dedupe(limitations)


def _matching_runs(
    runs: list[dict[str, Any]],
    *,
    task_id: str,
    provider: str,
    condition_id: str,
    replicate: int,
) -> list[dict[str, Any]]:
    return [
        run
        for run in runs
        if run.get("task_id") == task_id
        and run.get("provider") == provider
        and run.get("condition_id") == condition_id
        and run.get("replicate") == replicate
    ]


def _pair_runs(pair: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        run
        for run in (pair.get("agentspec_run"), pair.get("control_run"))
        if isinstance(run, dict)
    ]


def _find_by_id(records: list[dict[str, Any]], identifier: str, label: str) -> dict[str, Any]:
    for record in records:
        if record.get("id") == identifier:
            return record
    raise ValueError(f"Evaluation run references unknown {label} {identifier}.")


def _require_unique_ids(records: list[dict[str, Any]], label: str) -> None:
    ids = [str(record["id"]) for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Evaluation {label} ids must be unique.")


def _required_identifier(payload: dict[str, Any], field: str, label: str) -> str:
    value = _required_text(payload, field, label)
    if not _safe_identifier(value):
        raise ValueError(f"{label} {field} contains unsupported characters.")
    return value


def _required_text(payload: dict[str, Any], field: str, label: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} requires a non-empty {field}.")
    return value.strip()


def _optional_timestamp(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or _parse_datetime(value) is None:
        raise ValueError(f"Evaluation run {field} must be an ISO 8601 timestamp with timezone.")
    return value


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp must contain a timezone.")
    return parsed


def _metric_value(run: dict[str, Any], path: str) -> Any:
    value: Any = run.get("metrics")
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _nested(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _difference(left: Any, right: Any) -> float | None:
    if not _non_negative_number(left) or not _non_negative_number(right):
        return None
    return round(float(left) - float(right), 6)


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _non_negative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _safe_identifier(value: str) -> bool:
    return bool(value) and all(character.isalnum() or character in "._-" for character in value)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _format_delta(value: Any) -> str:
    return f"{value:+.6f}" if isinstance(value, (int, float)) else "unavailable"
