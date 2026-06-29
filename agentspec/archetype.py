"""Archetype-aware target inference and path provenance.

Implements R-136 (repository-aware code/test target inference) and R-137
(allowed-path provenance) per ADR-0004 / DCR-0019. Reuses the language
detection helpers from `doctor.py` rather than duplicating them.

Public surface:

- `detect_archetype(root)` — returns a dict describing the host repo's
  language, source roots, and test roots.
- `infer_code_targets(text, archetype)` — returns archetype-appropriate
  code paths for a requirement description. Falls back to glob patterns
  for non-Python languages and to `docs/**` for unknown archetypes.
- `infer_test_targets(text, archetype)` — same shape, for tests.
- `validate_path_provenance(path, root)` — `confirmed | inferred | pattern`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .doctor import _languages, _repo_files, _roots


# Mapping from a Python-self-host keyword to a specific path. Preserved
# verbatim from the previous compile.py behavior so AgentSpec dogfooding
# continues to produce stable code_targets.
_PYTHON_SELF_KEYWORD_PATHS: list[tuple[tuple[str, ...], str]] = [
    (("init", "artifact layout"), "agentspec/init.py"),
    (("cli", "command"), "agentspec/cli.py"),
    (("markdown", "section", "hash"), "agentspec/markdown.py"),
    (("requirement", "compile", "spec", "readiness"), "agentspec/compile.py"),
    (("context pack", "task"), "agentspec/task.py"),
    (("agent", "claude", "codex", "emit"), "agentspec/emit.py"),
    (("doctor", "brownfield", "repo"), "agentspec/doctor.py"),
    (("drift", "diff"), "agentspec/drift.py"),
]


def detect_archetype(root: Path) -> dict[str, Any]:
    """Return language, source_roots, test_roots for the host repo."""
    files = _repo_files(root)
    languages = _languages(files)
    if not languages:
        language = "undetermined"
    else:
        # Pick the dominant language by file count among known mappings.
        language = _dominant_language(files, languages)
    source_roots = _roots(files, ["agentspec", "src", "app", "lib", "cmd", "internal", "pkg"])
    test_roots = _roots(files, ["tests", "test", "spec", "__tests__"])
    return {
        "language": language,
        "languages": languages,
        "source_roots": source_roots,
        "test_roots": test_roots,
    }


def infer_code_targets(text: str, archetype: dict[str, Any]) -> list[str]:
    """Return code-target paths inferred from a requirement description."""
    language = archetype.get("language", "undetermined")
    source_roots = archetype.get("source_roots") or []

    if language == "undetermined":
        return ["docs/**"]

    if language == "python":
        # Self-host keyword mapping if we look like AgentSpec; otherwise
        # produce generic <source_root>/*.py glob.
        is_self_host = "agentspec/" in source_roots
        if is_self_host:
            return _python_self_host_targets(text)
        return _glob_targets(source_roots or ["src/"], "py")

    if language == "typescript":
        return _glob_targets(source_roots or ["src/"], "ts", extra_extensions=("tsx",))

    if language == "javascript":
        return _glob_targets(source_roots or ["src/"], "js", extra_extensions=("jsx",))

    if language == "go":
        return _glob_targets(source_roots or ["cmd/", "internal/", "pkg/"], "go")

    if language == "rust":
        return _glob_targets(source_roots or ["src/"], "rs")

    if language == "java":
        return _glob_targets(source_roots or ["src/"], "java")

    if language == "ruby":
        return _glob_targets(source_roots or ["lib/", "app/"], "rb")

    return ["docs/**"]


def infer_test_targets(text: str, archetype: dict[str, Any]) -> list[str]:
    """Return test-target paths inferred from a requirement description."""
    language = archetype.get("language", "undetermined")
    test_roots = archetype.get("test_roots") or []

    if language == "undetermined":
        return ["docs/**"]

    if language == "python":
        is_self_host = "agentspec/" in (archetype.get("source_roots") or [])
        if is_self_host:
            return _python_self_host_test_targets(text)
        return _glob_targets(test_roots or ["tests/"], "py")

    if language == "typescript":
        return _glob_targets(test_roots or ["tests/"], "ts", extra_extensions=("tsx",))

    if language == "javascript":
        return _glob_targets(test_roots or ["tests/"], "js", extra_extensions=("jsx",))

    if language == "go":
        # Go convention: tests live next to source as *_test.go.
        return ["./**/*_test.go"]

    if language == "rust":
        return _glob_targets(test_roots or ["tests/"], "rs")

    if language == "java":
        return _glob_targets(test_roots or ["src/test/"], "java")

    if language == "ruby":
        return _glob_targets(test_roots or ["spec/", "test/"], "rb")

    return ["docs/**"]


def validate_path_provenance(path: str, root: Path) -> str:
    """Return `confirmed | inferred | pattern` for a single allowed-path."""
    if any(ch in path for ch in ("*", "?", "[")):
        return "pattern"
    target = Path(root) / path
    return "confirmed" if target.exists() else "inferred"


# --- internals ---


def _dominant_language(files: list[str], languages: list[str]) -> str:
    """Pick the language whose source files are most numerous."""
    suffix_to_lang = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
    }
    counts: dict[str, int] = {lang: 0 for lang in languages}
    for path in files:
        for suffix, language in suffix_to_lang.items():
            if path.endswith(suffix) and language in counts:
                counts[language] += 1
                break
    return max(counts, key=lambda language: counts[language]) if counts else languages[0]


def _python_self_host_targets(text: str) -> list[str]:
    """Original AgentSpec keyword → path mapping. Preserved verbatim."""
    lower = text.lower()
    targets: list[str] = []
    for keywords, path in _PYTHON_SELF_KEYWORD_PATHS:
        if any(keyword in lower for keyword in keywords):
            targets.append(path)
    return sorted(set(targets)) or ["docs/traceability/requirements.yml"]


def _python_self_host_test_targets(text: str) -> list[str]:
    """Original AgentSpec test target mapping. Preserved verbatim."""
    lower = text.lower()
    if "markdown" in lower or "section" in lower:
        return ["tests/test_markdown_sectionizer.py"]
    return ["tests/test_cli_workflow.py"]


def _glob_targets(roots: list[str], extension: str, extra_extensions: tuple[str, ...] = ()) -> list[str]:
    """Build glob patterns for the given roots and extensions."""
    extensions = (extension,) + extra_extensions
    out: list[str] = []
    for root in roots:
        normalized = root if root.endswith("/") else f"{root}/"
        for ext in extensions:
            out.append(f"{normalized}**/*.{ext}")
    return out
