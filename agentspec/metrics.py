"""Read-only project metrics derived from AgentSpec lifecycle artifacts."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any

from .io import load_data, utc_now_iso
from .status import build_project_status, load_run_records


METRICS_SCHEMA = "agentspec.metrics.v0"
_MODEL_REVIEW_FALLBACK_FLAG = "model_review_unavailable"


def build_project_metrics(root: Path) -> dict[str, Any]:
    """Build read-only project metrics from existing AgentSpec artifacts."""

    root = root.resolve()
    status = build_project_status(root, recent_limit=0)
    runs = load_run_records(root)
    quality = _quality_summary(root)

    return {
        "schema": METRICS_SCHEMA,
        "generated_at": utc_now_iso(),
        "root": str(root),
        "readiness": status.get("readiness", {}),
        "requirements": _requirements_metrics(status.get("requirements")),
        "dcrs": _dcr_metrics(status.get("dcrs")),
        "tasks": _task_metrics(status.get("tasks")),
        "runs": _run_metrics(status.get("runs"), runs),
        "verification": _verification_metrics(runs),
        "policy_flags": _policy_flag_metrics(runs),
        "cycle_time": _cycle_time_metrics(runs),
        "quality_gc": quality,
    }


def format_project_metrics(metrics: dict[str, Any]) -> str:
    """Format project metrics for terminal output."""

    readiness = metrics.get("readiness", {})
    requirements = metrics.get("requirements", {})
    dcrs = metrics.get("dcrs", {})
    tasks = metrics.get("tasks", {})
    runs = metrics.get("runs", {})
    verification = metrics.get("verification", {})
    policy_flags = metrics.get("policy_flags", {})
    cycle_time = metrics.get("cycle_time", {})
    quality = metrics.get("quality_gc", {})

    lines = [
        "AgentSpec Metrics",
        f"Root: {metrics.get('root')}",
        f"Readiness: {readiness.get('score', '-')}/100 ({readiness.get('mode', '-')})",
        (
            "Requirements: "
            f"{requirements.get('total', 0)} total, "
            f"{requirements.get('accepted', 0)} accepted "
            f"({_percent(requirements.get('acceptance_rate'))})"
        ),
        (
            "DCRs: "
            f"{dcrs.get('total', 0)} total, "
            f"{dcrs.get('open_or_classified', 0)} open/classified"
        ),
        (
            "Tasks: "
            f"{tasks.get('total', 0)} total, "
            f"{tasks.get('complete', 0)} complete "
            f"({_percent(tasks.get('completion_rate'))}), "
            f"{tasks.get('ready', 0)} ready"
        ),
        (
            "Runs: "
            f"{runs.get('total', 0)} total, "
            f"complete {_percent(runs.get('completion_rate'))}, "
            f"pause/halt {_percent(runs.get('pause_halt_rate'))}, "
            f"abort {_percent(runs.get('abort_rate'))}"
        ),
        (
            "Verification: "
            f"{verification.get('passed', 0)} passed, "
            f"{verification.get('failed', 0)} failed, "
            f"pass rate {_percent(verification.get('pass_rate'))}"
        ),
        (
            "Policy flags: "
            f"{policy_flags.get('total', 0)} total, "
            f"model-review fallback {_percent(policy_flags.get('reviewer_fallback_rate'))}"
        ),
        (
            "Cycle time: "
            f"{cycle_time.get('completed_run_count', 0)} completed run(s), "
            f"median {_duration(cycle_time.get('median_seconds'))}"
        ),
        (
            "Quality GC: "
            f"{quality.get('grade', '-') if quality.get('present') else '-'} "
            f"({quality.get('finding_count', 0)} finding(s))"
        ),
    ]
    return "\n".join(lines)


def _requirements_metrics(section: Any) -> dict[str, Any]:
    total = _section_total(section)
    accepted = _count(section, "by_status", "accepted")
    return {
        "total": total,
        "accepted": accepted,
        "acceptance_rate": _rate(accepted, total),
        "by_status": _counts(section, "by_status"),
        "by_priority": _counts(section, "by_priority"),
    }


def _dcr_metrics(section: Any) -> dict[str, Any]:
    open_count = _count(section, "by_status", "open")
    classified = _count(section, "by_status", "classified")
    return {
        "total": _section_total(section),
        "open_or_classified": open_count + classified,
        "by_status": _counts(section, "by_status"),
        "by_classification": _counts(section, "by_classification"),
    }


def _task_metrics(section: Any) -> dict[str, Any]:
    total = _section_total(section)
    complete = _count(section, "by_status", "complete")
    ready = _count(section, "by_status", "ready")
    return {
        "total": total,
        "complete": complete,
        "ready": ready,
        "completion_rate": _rate(complete, total),
        "ready_rate": _rate(ready, total),
        "by_status": _counts(section, "by_status"),
        "by_type": _counts(section, "by_type"),
    }


def _run_metrics(section: Any, runs: list[dict[str, Any]]) -> dict[str, Any]:
    total = _section_total(section)
    complete = _count(section, "by_status", "complete")
    paused = _count(section, "by_status", "paused")
    halted = _count(section, "by_status", "halted")
    aborted = _count(section, "by_status", "aborted")
    active = sum(1 for run in runs if run.get("status") in {"started", "running"})
    attention = paused + halted
    return {
        "total": total,
        "complete": complete,
        "active": active,
        "attention": attention,
        "aborted": aborted,
        "completion_rate": _rate(complete, total),
        "pause_halt_rate": _rate(attention, total),
        "abort_rate": _rate(aborted, total),
        "by_status": _counts(section, "by_status"),
        "by_mode": _counts(section, "by_mode"),
    }


def _verification_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(str(run.get("test_status") or "unknown") for run in runs)
    passed = statuses.get("passed", 0)
    failed = statuses.get("failed", 0)
    known_total = passed + failed
    return {
        "passed": passed,
        "failed": failed,
        "not_run": statuses.get("not_run", 0),
        "unknown": statuses.get("unknown", 0),
        "by_status": {key: statuses[key] for key in sorted(statuses)},
        "known_total": known_total,
        "pass_rate": _rate(passed, known_total),
    }


def _policy_flag_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    flags: Counter[str] = Counter()
    for run in runs:
        raw_flags = run.get("policy_flags", [])
        if not isinstance(raw_flags, list):
            continue
        flags.update(str(flag) for flag in raw_flags)
    fallback_count = flags.get(_MODEL_REVIEW_FALLBACK_FLAG, 0)
    return {
        "total": sum(flags.values()),
        "by_flag": {key: flags[key] for key in sorted(flags)},
        "reviewer_fallback_count": fallback_count,
        "reviewer_fallback_rate": _rate(fallback_count, len(runs)),
    }


def _cycle_time_metrics(runs: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [
        duration
        for run in runs
        if run.get("status") == "complete"
        for duration in [_run_duration_seconds(run)]
        if duration is not None
    ]
    if not durations:
        return {
            "completed_run_count": 0,
            "average_seconds": None,
            "median_seconds": None,
            "minimum_seconds": None,
            "maximum_seconds": None,
        }
    return {
        "completed_run_count": len(durations),
        "average_seconds": round(mean(durations), 3),
        "median_seconds": round(median(durations), 3),
        "minimum_seconds": round(min(durations), 3),
        "maximum_seconds": round(max(durations), 3),
    }


def _run_duration_seconds(run: dict[str, Any]) -> float | None:
    created = _parse_datetime(run.get("created_at"))
    updated = _parse_datetime(run.get("updated_at"))
    if created is None or updated is None:
        return None
    duration = (updated - created).total_seconds()
    return duration if duration >= 0 else None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _quality_summary(root: Path) -> dict[str, Any]:
    report = load_data(root / "reports" / "quality" / "latest.yml", {})
    if not isinstance(report, dict) or not report:
        return {"present": False, "path": "reports/quality/latest.yml"}
    findings = report.get("findings", [])
    return {
        "present": True,
        "path": "reports/quality/latest.yml",
        "schema": report.get("schema"),
        "generated_at": report.get("generated_at"),
        "grade": report.get("grade"),
        "summary": report.get("summary"),
        "finding_count": len(findings) if isinstance(findings, list) else 0,
        "cadence": report.get("cadence", {}),
    }


def _section_total(section: Any) -> int:
    return int(section.get("total", 0)) if isinstance(section, dict) else 0


def _count(section: Any, group: str, key: str) -> int:
    counts = _counts(section, group)
    return int(counts.get(key, 0))


def _counts(section: Any, group: str) -> dict[str, int]:
    if not isinstance(section, dict) or not isinstance(section.get(group), dict):
        return {}
    return {str(key): int(value) for key, value in section[group].items()}


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _percent(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    return f"{value * 100:.1f}%"


def _duration(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return "-"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    return f"{minutes / 60:.1f}h"
