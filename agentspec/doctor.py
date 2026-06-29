"""Repository diagnostics for AgentSpec configuration and invariants."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_project_config, merged_runtime_config
from .io import ensure_writable_dir, write_data, write_text
from .model_review import build_agent_profile_diagnostics
from .policy import evaluate_project_invariants


IGNORED_DIRS = {".git", ".agentspec", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache"}
AGENT_CONTEXT_RECOVERY_COMMAND = "aspec emit --target claude,codex"


def run_doctor(root: Path, report_dir: Path | None = None) -> dict[str, Any]:
    """Run a brownfield assessment.

    Reports default to `<root>/reports/doctor/`. When `report_dir` is
    given (DCR-0020), reports are written under
    `<report_dir>/doctor/` instead — used for cross-repo runs where the
    target checkout is not writable.
    """

    destination = _doctor_destination(root, report_dir)
    ensure_writable_dir(destination)

    files = _repo_files(root)
    scan = {
        "repo": {
            "languages": _languages(files),
            "package_managers": _package_managers(files),
            "test_frameworks": _test_frameworks(files),
            "ci": _ci(files),
            "source_roots": _roots(files, ["agentspec", "src", "app", "lib"]),
            "test_roots": _roots(files, ["tests", "test"]),
            "docs": [path for path in files if path == "README.md" or path.startswith("docs/")],
        },
        "agent_context": _agent_context_freshness(root),
        "agent_profiles": _agent_profile_diagnostics(root),
        "project_invariants": evaluate_project_invariants(root, files),
        "first_safe_tasks": _first_safe_tasks(files),
    }
    write_data(destination / "repo-scan.yml", scan)
    write_text(destination / "agent-readiness.md", _doctor_report(scan))
    return scan


def _doctor_destination(root: Path, report_dir: Path | None) -> Path:
    if report_dir is None:
        return root / "reports" / "doctor"
    base = report_dir if report_dir.is_absolute() else root / report_dir
    return base / "doctor"


def _repo_files(root: Path) -> list[str]:
    result = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORED_DIRS for part in relative_parts):
            continue
        result.append(str(path.relative_to(root)))
    return sorted(result)


def _languages(files: list[str]) -> list[str]:
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
    }
    return sorted({language for file in files for suffix, language in mapping.items() if file.endswith(suffix)})


def _package_managers(files: list[str]) -> list[str]:
    checks = {
        "pyproject.toml": "python-packaging",
        "requirements.txt": "pip",
        "poetry.lock": "poetry",
        "package.json": "npm",
        "pnpm-lock.yaml": "pnpm",
        "yarn.lock": "yarn",
        "go.mod": "go",
        "Cargo.toml": "cargo",
    }
    return [name for file, name in checks.items() if file in files]


def _test_frameworks(files: list[str]) -> list[str]:
    frameworks = []
    if any(file.startswith("tests/") and file.endswith(".py") for file in files):
        frameworks.append("unittest-or-pytest")
    if "pytest.ini" in files:
        frameworks.append("pytest")
    if any(file.endswith((".test.ts", ".spec.ts", ".test.js", ".spec.js")) for file in files):
        frameworks.append("javascript-test-runner")
    return frameworks


def _ci(files: list[str]) -> list[str]:
    ci = []
    if any(file.startswith(".github/workflows/") for file in files):
        ci.append("github_actions")
    if ".gitlab-ci.yml" in files:
        ci.append("gitlab_ci")
    return ci


def _roots(files: list[str], names: list[str]) -> list[str]:
    roots = []
    for name in names:
        prefix = name + "/"
        if any(file.startswith(prefix) for file in files):
            roots.append(prefix)
    return roots


def _first_safe_tasks(files: list[str]) -> list[str]:
    tasks = []
    if not any(file.startswith("tests/") for file in files):
        tasks.append("Add smoke tests for the current CLI workflow.")
    if "AGENTS.md" not in files:
        tasks.append("Generate AGENTS.md from AgentSpec.")
    if not any(file.startswith("docs/traceability/") for file in files):
        tasks.append("Create traceability placeholders.")
    tasks.append("Map existing modules to tentative AgentSpec components.")
    return tasks


def _agent_context_freshness(root: Path) -> dict[str, Any]:
    source_artifacts = _existing_paths(
        root,
        [
            "docs/traceability/requirements.yml",
            "docs/discovery/readiness.yml",
            "agent/task-ledger.yml",
        ],
    )
    expected_artifacts = [
        "AGENTS.md",
        "CLAUDE.md",
    ]
    codex_agent_dir = root / ".codex" / "agents"
    codex_artifacts = []
    if codex_agent_dir.is_dir():
        codex_artifacts = [
            str(path.relative_to(root))
            for path in sorted(codex_agent_dir.glob("*.toml"))
            if path.is_file()
        ]
    checked_artifacts = expected_artifacts + (codex_artifacts or [".codex/agents/*.toml"])

    if not source_artifacts:
        return {
            "status": "not_applicable",
            "source_artifacts": [],
            "checked_artifacts": checked_artifacts,
            "warnings": [],
            "recovery_command": AGENT_CONTEXT_RECOVERY_COMMAND,
        }

    newest_source = max(source_artifacts, key=lambda rel: (root / rel).stat().st_mtime_ns)
    newest_source_mtime = (root / newest_source).stat().st_mtime_ns
    warnings: list[dict[str, str]] = []

    for rel in checked_artifacts:
        if rel == ".codex/agents/*.toml":
            warnings.append(
                {
                    "kind": "missing",
                    "path": rel,
                    "message": "No generated Codex agent TOML files found under .codex/agents/.",
                    "recovery_command": AGENT_CONTEXT_RECOVERY_COMMAND,
                }
            )
            continue
        path = root / rel
        if not path.exists():
            warnings.append(
                {
                    "kind": "missing",
                    "path": rel,
                    "message": f"{rel} is missing while AgentSpec source artifacts exist.",
                    "recovery_command": AGENT_CONTEXT_RECOVERY_COMMAND,
                }
            )
            continue
        if path.stat().st_mtime_ns < newest_source_mtime:
            warnings.append(
                {
                    "kind": "stale",
                    "path": rel,
                    "newer_source": newest_source,
                    "message": f"{rel} is older than {newest_source}.",
                    "recovery_command": AGENT_CONTEXT_RECOVERY_COMMAND,
                }
            )

    return {
        "status": "warning" if warnings else "fresh",
        "source_artifacts": source_artifacts,
        "checked_artifacts": checked_artifacts,
        "warnings": warnings,
        "recovery_command": AGENT_CONTEXT_RECOVERY_COMMAND,
    }


def _existing_paths(root: Path, relative_paths: list[str]) -> list[str]:
    return [rel for rel in relative_paths if (root / rel).is_file()]


def _agent_profile_diagnostics(root: Path) -> dict[str, Any]:
    try:
        config = merged_runtime_config(load_project_config(root))
    except ValueError as exc:
        return {
            "schema": "agentspec.agent_profile_diagnostics.v0",
            "status": "invalid_config",
            "bindings": {},
            "profiles": {},
            "warnings": [{"profile": None, "message": str(exc)}],
        }
    return build_agent_profile_diagnostics(config)


def _doctor_report(scan: dict[str, Any]) -> str:
    repo = scan["repo"]
    out = ["# Brownfield Doctor Report", "", "Read-only assessment.", ""]
    for key in ["languages", "package_managers", "test_frameworks", "ci", "source_roots", "test_roots"]:
        out.append(f"- {key.replace('_', ' ').title()}: {', '.join(repo[key]) or '-'}")
    agent_context = scan.get("agent_context", {})
    out.extend(["", "## Agent Context Freshness", ""])
    out.append(f"- Status: {agent_context.get('status', 'unknown')}")
    warnings = agent_context.get("warnings", [])
    if warnings:
        out.append(f"- Recovery: `{agent_context.get('recovery_command', AGENT_CONTEXT_RECOVERY_COMMAND)}`")
        out.append("")
        for warning in warnings:
            out.append(f"- Warning: {warning.get('message', 'Generated agent context may be stale.')}")
    else:
        out.append("- Warnings: -")
    profiles = scan.get("agent_profiles", {})
    out.extend(["", "## Agent Profiles", ""])
    out.append(f"- Status: {profiles.get('status', 'unknown')}")
    bindings = profiles.get("bindings") if isinstance(profiles.get("bindings"), dict) else {}
    if bindings:
        out.append(
            "- Active bindings: "
            + ", ".join(f"{role}={name}" for role, name in sorted(bindings.items()))
        )
    warnings = profiles.get("warnings") if isinstance(profiles.get("warnings"), list) else []
    if warnings:
        for warning in warnings:
            profile_name = warning.get("profile") or "-"
            out.append(f"- Warning: `{profile_name}` {warning.get('message', 'Profile may be unavailable.')}")
    else:
        out.append("- Warnings: -")
    invariants = scan.get("project_invariants", {})
    out.extend(["", "## Project Invariants", ""])
    out.append(f"- Status: {invariants.get('status', 'unknown')}")
    results = invariants.get("results", [])
    if results:
        out.append("")
        for result in results:
            out.append(
                f"- `{result.get('id', '-')}` {result.get('status', 'unknown')} "
                f"({result.get('severity', 'warning')}): {result.get('message', '-')}"
            )
    else:
        out.append("- Results: -")
    out.extend(["", "## First Safe Tasks", ""])
    for task in scan["first_safe_tasks"]:
        out.append(f"- {task}")
    return "\n".join(out) + "\n"
