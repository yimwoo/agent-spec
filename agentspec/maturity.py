"""Progressive maturity checks for AgentSpec project readiness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .evidence import (
    PASSING_PUBLIC_REVIEW_VERDICTS,
    load_public_release_tasks,
    public_release_evidence_path,
)
from .io import load_data, write_data


MATURITY_CONFIG_SCHEMA = "agentspec.maturity.v1"
MATURITY_STATUS_SCHEMA = "agentspec.maturity_status.v0"
ALLOWED_MATURITY_LEVELS = ("lightweight", "governed-implementation", "production-readiness")
ALLOWED_MATURITY_ENFORCEMENT = ("warn", "block")
DEFAULT_MATURITY_LEVEL = "lightweight"
DEFAULT_MATURITY_ENFORCEMENT = "warn"

_LEVEL_CHECKS: dict[str, tuple[str, ...]] = {
    "lightweight": (
        "agents_md",
        "project_status",
        "basic_requirements",
        "doc_registry",
    ),
    "governed-implementation": (
        "task_context_pack",
        "allowed_paths",
        "session_lease_state",
        "review_evidence",
        "test_evidence",
        "drift_check",
    ),
    "production-readiness": (
        "outcome_gates",
        "security_review",
        "release_runbook",
        "rollback_plan",
        "audit_record",
        "ci_e2e_evidence",
    ),
}

_CHECK_TITLES: dict[str, str] = {
    "agents_md": "AGENTS.md entrypoint exists",
    "project_status": "AgentSpec project status artifacts exist",
    "basic_requirements": "Basic requirements artifact exists",
    "doc_registry": "Documentation registry or source-of-truth index exists",
    "task_context_pack": "Task context pack exists",
    "allowed_paths": "Task context packs declare allowed paths",
    "session_lease_state": "Session lease directories exist",
    "review_evidence": "Code review evidence exists",
    "test_evidence": "Passed task verification evidence exists",
    "drift_check": "Drift report evidence exists",
    "outcome_gates": "Product outcome gates are configured",
    "security_review": "Security review evidence exists",
    "release_runbook": "Release runbook exists",
    "rollback_plan": "Rollback plan evidence exists",
    "audit_record": "Task or audit ledger exists",
    "ci_e2e_evidence": "CI or E2E evidence exists",
}


def default_maturity_config(
    *,
    level: str = DEFAULT_MATURITY_LEVEL,
    enforcement: str = DEFAULT_MATURITY_ENFORCEMENT,
) -> dict[str, Any]:
    """Return the default repo-local maturity configuration."""

    _validate_level(level)
    _validate_enforcement(enforcement)
    return {
        "schema": MATURITY_CONFIG_SCHEMA,
        "level": level,
        "enforcement": enforcement,
        "notes": [
            "Maturity profiles are progressive: lightweight for adoption, governed-implementation for normal enterprise work, production-readiness for production claims."
        ],
    }


def load_maturity_config(root: Path) -> dict[str, Any]:
    """Load and validate the repo maturity configuration."""

    path = _config_path(root)
    data = load_data(path, None)
    if data is None:
        config = default_maturity_config()
        config["configured"] = False
        return config
    if not isinstance(data, dict):
        raise ValueError("agent/maturity.yml must contain a JSON/YAML object.")
    level = str(data.get("level") or DEFAULT_MATURITY_LEVEL)
    enforcement = str(data.get("enforcement") or DEFAULT_MATURITY_ENFORCEMENT)
    _validate_level(level)
    _validate_enforcement(enforcement)
    return {
        **data,
        "schema": str(data.get("schema") or MATURITY_CONFIG_SCHEMA),
        "level": level,
        "enforcement": enforcement,
        "configured": True,
    }


def set_maturity_config(root: Path, *, level: str, enforcement: str) -> dict[str, Any]:
    """Write the maturity profile and return its current status projection."""

    root = root.resolve()
    config = default_maturity_config(level=level, enforcement=enforcement)
    write_data(_config_path(root), config)
    return build_maturity_status(root)


def build_maturity_status(root: Path) -> dict[str, Any]:
    """Build the maturity readiness projection for the configured profile."""

    root = root.resolve()
    config = load_maturity_config(root)
    level = str(config["level"])
    enforcement = str(config["enforcement"])
    checks = [_evaluate_check(root, check_id) for check_id in _checks_for_level(level)]
    missing = [check for check in checks if check["status"] == "missing"]
    passed_count = sum(1 for check in checks if check["status"] == "passed")
    score = int(round((passed_count / len(checks)) * 100)) if checks else 100
    blocking = missing if enforcement == "block" else []
    warnings = missing if enforcement == "warn" else []
    readiness = "ready" if not missing else "blocked" if blocking else "needs_attention"
    return {
        "schema": MATURITY_STATUS_SCHEMA,
        "path": "agent/maturity.yml",
        "configured": bool(config.get("configured")),
        "level": level,
        "enforcement": enforcement,
        "readiness": readiness,
        "score": score,
        "summary": _summary(level, enforcement, score, len(missing), len(blocking)),
        "counts": {
            "checks": len(checks),
            "passed": passed_count,
            "missing": len(missing),
            "warnings": len(warnings),
            "blocking": len(blocking),
        },
        "checks": checks,
        "missing": missing,
        "warnings": warnings,
        "blocking": blocking,
    }


def format_maturity_status(status: dict[str, Any]) -> str:
    """Format a maturity status payload for human CLI output."""

    lines = [
        "AgentSpec Maturity",
        f"Level: {status.get('level')}",
        f"Enforcement: {status.get('enforcement')}",
        f"Readiness: {status.get('readiness')} ({status.get('score')}/100)",
        f"Summary: {status.get('summary')}",
    ]
    blocking = status.get("blocking") if isinstance(status.get("blocking"), list) else []
    warnings = status.get("warnings") if isinstance(status.get("warnings"), list) else []
    if blocking:
        lines.extend(["", "Blocking Checks:"])
        lines.extend(f"- {check.get('id')}: {check.get('title')}" for check in blocking)
    if warnings:
        lines.extend(["", "Warnings:"])
        lines.extend(f"- {check.get('id')}: {check.get('title')}" for check in warnings)
    return "\n".join(lines)


def _config_path(root: Path) -> Path:
    return root / "agent" / "maturity.yml"


def _validate_level(level: str) -> None:
    if level not in ALLOWED_MATURITY_LEVELS:
        raise ValueError(f"maturity level must be one of: {', '.join(ALLOWED_MATURITY_LEVELS)}.")


def _validate_enforcement(enforcement: str) -> None:
    if enforcement not in ALLOWED_MATURITY_ENFORCEMENT:
        raise ValueError(
            f"maturity enforcement must be one of: {', '.join(ALLOWED_MATURITY_ENFORCEMENT)}."
        )


def _checks_for_level(level: str) -> list[str]:
    checks: list[str] = []
    for configured_level in ALLOWED_MATURITY_LEVELS:
        checks.extend(_LEVEL_CHECKS[configured_level])
        if configured_level == level:
            return checks
    return checks


def _evaluate_check(root: Path, check_id: str) -> dict[str, Any]:
    passed, evidence = _check_predicate(root, check_id)
    return {
        "id": check_id,
        "title": _CHECK_TITLES[check_id],
        "status": "passed" if passed else "missing",
        "evidence": evidence,
    }


def _check_predicate(root: Path, check_id: str) -> tuple[bool, list[str]]:
    if check_id == "agents_md":
        return _exists(root, "AGENTS.md")
    if check_id == "project_status":
        return _exists(root, ".agentspec/config.yml")
    if check_id == "basic_requirements":
        return _exists(root, "docs/traceability/requirements.yml")
    if check_id == "doc_registry":
        return _any_exists(
            root,
            [
                "docs/doc-registry.yml",
                "docs/designs/design-registry.yml",
                "docs/source_of_truth/README.md",
                "docs/designs/README.md",
            ],
        )
    if check_id == "task_context_pack":
        return _any_glob(root, "agent/context-packs/T-*.md")
    if check_id == "allowed_paths":
        return _any_context_pack_has(root, "## Allowed Paths")
    if check_id == "session_lease_state":
        return _all_exist(root, ["agent/sessions/active", "agent/sessions/archived"])
    if check_id == "review_evidence":
        return _any_passed(
            _any_glob(root, "agent/reviews/REVIEW-*.yml"),
            _public_release_tasks_have_code_review(root),
        )
    if check_id == "test_evidence":
        return _any_passed(
            _task_ledger_has_passed_verification(root),
            _public_release_tasks_have_passed_verification(root),
        )
    if check_id == "drift_check":
        return _any_exists(root, ["reports/drift/latest.md", "docs/drift"])
    if check_id == "outcome_gates":
        return _outcomes_configured(root)
    if check_id == "security_review":
        return _any_passed(
            _any_evidence_globs(
                root,
                [
                    "reports/security/*.json",
                    "reports/security/*.md",
                    "reports/security/*.yml",
                    "reports/security/*.yaml",
                    "docs/security/*.md",
                ],
            ),
            _any_glob(root, "agent/reviews/*security*.yml"),
        )
    if check_id == "release_runbook":
        return _any_exists(
            root,
            [
                "docs/operations/release-runbook.md",
                "docs/runbooks/release.md",
                "docs/release/runbook.md",
            ],
        )
    if check_id == "rollback_plan":
        return _any_passed(
            _any_exists(root, ["docs/operations/rollback.md", "docs/release/rollback.md"]),
            _any_context_pack_has(root, "Rollback"),
        )
    if check_id == "audit_record":
        return _any_passed(
            _exists(root, "agent/task-ledger.yml"),
            _public_release_evidence_exists(root),
        )
    if check_id == "ci_e2e_evidence":
        return _any_passed(
            _workflow_has_test_or_e2e_job(root),
            _any_evidence_globs(
                root,
                [
                    "reports/e2e/*.json",
                    "reports/e2e/*.md",
                    "reports/e2e/*.yml",
                    "reports/e2e/*.yaml",
                    "reports/eval/*.json",
                    "reports/eval/*.md",
                    "reports/eval/*.yml",
                    "reports/eval/*.yaml",
                ],
            ),
        )
    raise ValueError(f"Unknown maturity check: {check_id}")


def _exists(root: Path, relative_path: str) -> tuple[bool, list[str]]:
    path = root / relative_path
    return path.exists(), [relative_path] if path.exists() else []


def _all_exist(root: Path, relative_paths: list[str]) -> tuple[bool, list[str]]:
    existing = [path for path in relative_paths if (root / path).exists()]
    return len(existing) == len(relative_paths), existing


def _any_exists(root: Path, relative_paths: list[str]) -> tuple[bool, list[str]]:
    existing = [path for path in relative_paths if (root / path).exists()]
    return bool(existing), existing


def _any_glob(root: Path, pattern: str) -> tuple[bool, list[str]]:
    paths = sorted(root.glob(pattern))
    evidence = [_relative(root, path) for path in paths[:5]]
    return bool(paths), evidence


def _any_evidence_globs(root: Path, patterns: list[str]) -> tuple[bool, list[str]]:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(
            path
            for path in sorted(root.glob(pattern))
            if path.is_file() and path.name != ".gitkeep"
        )
    evidence = [_relative(root, path) for path in paths[:5]]
    return bool(paths), evidence


def _any_passed(*checks: tuple[bool, list[str]]) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    for passed, paths in checks:
        evidence.extend(paths)
        if passed:
            return True, evidence
    return False, evidence


def _workflow_has_test_or_e2e_job(root: Path) -> tuple[bool, list[str]]:
    workflows = sorted((root / ".github" / "workflows").glob("*.yml"))
    workflows.extend(sorted((root / ".github" / "workflows").glob("*.yaml")))
    evidence: list[str] = []
    keywords = ("e2e", "playwright", "pytest", "unittest", "npm test", "pnpm test")
    for path in workflows:
        try:
            text = path.read_text(encoding="utf-8").lower()
        except OSError:
            continue
        if any(keyword in text for keyword in keywords):
            evidence.append(_relative(root, path))
            if len(evidence) >= 5:
                break
    return bool(evidence), evidence


def _any_context_pack_has(root: Path, marker: str) -> tuple[bool, list[str]]:
    evidence: list[str] = []
    for path in sorted((root / "agent" / "context-packs").glob("T-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if marker in text:
            evidence.append(_relative(root, path))
            if len(evidence) >= 5:
                break
    return bool(evidence), evidence


def _task_ledger_has_passed_verification(root: Path) -> tuple[bool, list[str]]:
    path = root / "agent" / "task-ledger.yml"
    data = load_data(path, {})
    if not isinstance(data, dict):
        return False, []
    tasks = data.get("tasks")
    if not isinstance(tasks, dict):
        return False, []
    for context_pack, entry in tasks.items():
        if not isinstance(entry, dict):
            continue
        verification = entry.get("verification")
        if isinstance(verification, dict) and verification.get("status") == "passed":
            return True, ["agent/task-ledger.yml", str(context_pack)]
    return False, []


def _public_release_tasks_have_passed_verification(root: Path) -> tuple[bool, list[str]]:
    evidence_path = public_release_evidence_path()
    for context_pack, entry in load_public_release_tasks(root).items():
        raw_verification = entry.get("verification")
        verification: dict[str, Any] = raw_verification if isinstance(raw_verification, dict) else {}
        if verification.get("status") == "passed":
            return True, [evidence_path, context_pack]
    return False, []


def _public_release_tasks_have_code_review(root: Path) -> tuple[bool, list[str]]:
    evidence_path = public_release_evidence_path()
    for context_pack, entry in load_public_release_tasks(root).items():
        review = entry.get("code_review")
        if isinstance(review, dict) and review.get("verdict") in PASSING_PUBLIC_REVIEW_VERDICTS:
            return True, [evidence_path, context_pack]
    return False, []


def _public_release_evidence_exists(root: Path) -> tuple[bool, list[str]]:
    exists = bool(load_public_release_tasks(root))
    return exists, [public_release_evidence_path()] if exists else []


def _outcomes_configured(root: Path) -> tuple[bool, list[str]]:
    path = root / "agent" / "outcomes.yml"
    data = load_data(path, {})
    if not isinstance(data, dict):
        return False, []
    outcomes = data.get("outcomes")
    if isinstance(outcomes, list) and outcomes:
        return True, ["agent/outcomes.yml"]
    return False, []


def _summary(level: str, enforcement: str, score: int, missing: int, blocking: int) -> str:
    if missing == 0:
        return f"Maturity {level} is ready ({score}/100, enforcement={enforcement})."
    if blocking:
        return f"Maturity {level} has {blocking} blocking check(s) ({score}/100)."
    return f"Maturity {level} has {missing} warning check(s) ({score}/100)."


def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)
