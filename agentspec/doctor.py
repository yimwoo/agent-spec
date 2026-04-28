from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import write_data, write_text


IGNORED_DIRS = {".git", ".agentspec", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", ".mypy_cache"}


def run_doctor(root: Path) -> dict[str, Any]:
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
        "first_safe_tasks": _first_safe_tasks(files),
    }
    write_data(root / "reports" / "doctor" / "repo-scan.yml", scan)
    write_text(root / "reports" / "doctor" / "agent-readiness.md", _doctor_report(scan))
    return scan


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


def _doctor_report(scan: dict[str, Any]) -> str:
    repo = scan["repo"]
    out = ["# Brownfield Doctor Report", "", "Read-only assessment.", ""]
    for key in ["languages", "package_managers", "test_frameworks", "ci", "source_roots", "test_roots"]:
        out.append(f"- {key.replace('_', ' ').title()}: {', '.join(repo[key]) or '-'}")
    out.extend(["", "## First Safe Tasks", ""])
    for task in scan["first_safe_tasks"]:
        out.append(f"- {task}")
    return "\n".join(out) + "\n"
