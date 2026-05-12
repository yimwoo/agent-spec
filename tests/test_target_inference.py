"""Tests for archetype-aware target inference and path provenance.

Covers R-136 and R-137 (DCR-0019).
"""

import json
import tempfile
import unittest
from pathlib import Path


class _RepoFixture:
    """Helper to build minimal language-marker repos in a tmpdir."""

    def __init__(self, root: Path):
        self.root = root

    def write(self, relative: str, content: str = "") -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class DetectArchetypeTests(unittest.TestCase):
    def test_python_repo_detected(self) -> None:
        from agentspec.archetype import detect_archetype

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fx = _RepoFixture(root)
            fx.write("pyproject.toml", "[project]\nname='x'\n")
            fx.write("agentspec/cli.py", "")
            fx.write("tests/test_x.py", "")

            arch = detect_archetype(root)
            self.assertEqual(arch["language"], "python")
            self.assertIn("agentspec/", arch["source_roots"])
            self.assertIn("tests/", arch["test_roots"])

    def test_typescript_repo_detected(self) -> None:
        from agentspec.archetype import detect_archetype

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fx = _RepoFixture(root)
            fx.write("package.json", '{"name":"x"}')
            fx.write("src/index.ts", "")
            fx.write("tests/index.test.ts", "")

            arch = detect_archetype(root)
            self.assertEqual(arch["language"], "typescript")
            self.assertIn("src/", arch["source_roots"])
            self.assertIn("tests/", arch["test_roots"])

    def test_go_repo_detected(self) -> None:
        from agentspec.archetype import detect_archetype

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            fx = _RepoFixture(root)
            fx.write("go.mod", "module x\n")
            fx.write("cmd/x/main.go", "")
            fx.write("internal/lib/lib.go", "")

            arch = detect_archetype(root)
            self.assertEqual(arch["language"], "go")

    def test_empty_repo_is_undetermined(self) -> None:
        from agentspec.archetype import detect_archetype

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            arch = detect_archetype(root)
            self.assertEqual(arch["language"], "undetermined")


class InferCodeTargetsTests(unittest.TestCase):
    def test_python_archetype_keeps_existing_keyword_mapping(self) -> None:
        from agentspec.archetype import infer_code_targets

        archetype = {"language": "python", "source_roots": ["agentspec/"], "test_roots": ["tests/"]}
        targets = infer_code_targets("Implement the CLI command", archetype)
        # Python self-host behavior: specific .py file paths under the source root.
        self.assertTrue(any(t.endswith("cli.py") for t in targets), f"got: {targets}")

    def test_typescript_archetype_returns_glob_patterns(self) -> None:
        from agentspec.archetype import infer_code_targets

        archetype = {"language": "typescript", "source_roots": ["src/"], "test_roots": ["tests/"]}
        targets = infer_code_targets("Implement the CLI command", archetype)
        self.assertTrue(any("src/" in t and "*" in t for t in targets), f"got: {targets}")
        self.assertFalse(any(t.endswith(".py") for t in targets), f"leaked python: {targets}")

    def test_go_archetype_returns_cmd_internal_pkg_globs(self) -> None:
        from agentspec.archetype import infer_code_targets

        archetype = {"language": "go", "source_roots": ["cmd/", "internal/"], "test_roots": []}
        targets = infer_code_targets("Implement the CLI command", archetype)
        self.assertTrue(any("cmd/" in t or "internal/" in t for t in targets), f"got: {targets}")

    def test_undetermined_archetype_falls_back_to_docs(self) -> None:
        from agentspec.archetype import infer_code_targets

        archetype = {"language": "undetermined", "source_roots": [], "test_roots": []}
        targets = infer_code_targets("anything", archetype)
        self.assertEqual(targets, ["docs/**"])


class InferTestTargetsTests(unittest.TestCase):
    def test_python_test_targets(self) -> None:
        from agentspec.archetype import infer_test_targets

        archetype = {"language": "python", "source_roots": ["agentspec/"], "test_roots": ["tests/"]}
        targets = infer_test_targets("Sectionize markdown", archetype)
        self.assertTrue(any(t.startswith("tests/") and t.endswith(".py") for t in targets), f"got: {targets}")

    def test_typescript_test_targets(self) -> None:
        from agentspec.archetype import infer_test_targets

        archetype = {"language": "typescript", "source_roots": ["src/"], "test_roots": ["tests/"]}
        targets = infer_test_targets("anything", archetype)
        self.assertTrue(any(".test.ts" in t or "tests/" in t for t in targets), f"got: {targets}")
        self.assertFalse(any(t.endswith(".py") for t in targets), f"leaked python: {targets}")


class CreateTaskContextPackScopeTests(unittest.TestCase):
    def test_generated_pack_allows_declared_test_targets(self) -> None:
        from agentspec.task import create_task_context_pack

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_task_workspace(
                root,
                [
                    _requirement(
                        "R-005",
                        "Validate trace event envelopes",
                        code_targets=["src/**/*.py"],
                        test_targets=["tests/**/*.py"],
                    )
                ],
            )

            path = create_task_context_pack(
                root,
                requirement_id="R-005",
                task_type="scaffold",
                title="Validate trace event envelopes",
            )
            text = path.read_text(encoding="utf-8")

            allowed_paths = _markdown_list_after_heading(text, "Allowed Paths")
            tests_to_update = _markdown_list_after_heading(text, "Tests To Add Or Update")
            self.assertIn("src/**/*.py", allowed_paths)
            self.assertIn("tests/**/*.py", allowed_paths)
            self.assertEqual(allowed_paths.count("tests/**/*.py"), 1)
            self.assertIn("tests/**/*.py", tests_to_update)
            self.assertIn("| `tests/**/*.py` | pattern; task verification |", text)
            self.assertNotIn("examples/**", allowed_paths)
            self.assertNotIn("scripts/**", allowed_paths)

    def test_default_tests_section_is_allowed_when_no_test_targets_exist(self) -> None:
        from agentspec.task import create_task_context_pack

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_task_workspace(
                root,
                [
                    _requirement(
                        "R-006",
                        "Implement feature",
                        code_targets=["src/**/*.py"],
                        test_targets=[],
                    )
                ],
            )

            path = create_task_context_pack(root, requirement_id="R-006")
            text = path.read_text(encoding="utf-8")

            self.assertIn("tests/", _markdown_list_after_heading(text, "Allowed Paths"))
            self.assertIn("| `tests/` | confirmed; task verification |", text)

    def test_docs_fallback_remains_when_only_default_tests_are_known(self) -> None:
        from agentspec.task import create_task_context_pack

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _seed_task_workspace(
                root,
                [
                    _requirement(
                        "R-007",
                        "Document generated context",
                        code_targets=[],
                        test_targets=[],
                    )
                ],
            )

            path = create_task_context_pack(root, requirement_id="R-007")
            text = path.read_text(encoding="utf-8")
            allowed_paths = _markdown_list_after_heading(text, "Allowed Paths")

            self.assertIn("docs/**", allowed_paths)
            self.assertIn("tests/", allowed_paths)
            self.assertIn("| `docs/**` | pattern; fallback scope |", text)

    def test_explicit_support_targets_join_allowed_scope(self) -> None:
        from agentspec.task import create_task_context_pack

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            requirement = _requirement(
                "R-008",
                "Add local example artifact validation",
                code_targets=["src/**/*.py"],
                test_targets=["tests/**/*.py"],
            )
            requirement["example_targets"] = ["examples/filtered_workload.json"]
            requirement["support_targets"] = ["scripts/smoke_check.sh"]
            requirement["verification_targets"] = ["fixtures/**"]
            _seed_task_workspace(root, [requirement])

            path = create_task_context_pack(root, requirement_id="R-008")
            text = path.read_text(encoding="utf-8")
            allowed_paths = _markdown_list_after_heading(text, "Allowed Paths")

            self.assertIn("examples/filtered_workload.json", allowed_paths)
            self.assertIn("scripts/smoke_check.sh", allowed_paths)
            self.assertIn("fixtures/**", allowed_paths)
            self.assertIn("| `examples/filtered_workload.json` | inferred; example artifact |", text)
            self.assertIn("| `scripts/smoke_check.sh` | inferred; support artifact |", text)
            self.assertIn("| `fixtures/**` | pattern; verification support |", text)

    def test_task_create_replaces_stale_python_targets_in_typescript_repo(self) -> None:
        from agentspec.task import create_task_context_pack

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            requirement = _requirement(
                "R-009",
                "Implement OpenTelemetry GenAI and OpenInference crosswalk",
                code_targets=["agentspec/emit.py"],
                test_targets=["tests/test_cli_workflow.py"],
            )
            _seed_task_workspace(root, [requirement])
            (root / "package.json").write_text('{"name":"fixture"}', encoding="utf-8")
            (root / "src" / "schema.ts").write_text("export const schema = {};\n", encoding="utf-8")
            (root / "tests" / "schema.test.ts").write_text("test('schema', () => {});\n", encoding="utf-8")

            path = create_task_context_pack(root, requirement_id="R-009")
            text = path.read_text(encoding="utf-8")
            allowed_paths = _markdown_list_after_heading(text, "Allowed Paths")
            tests_to_update = _markdown_list_after_heading(text, "Tests To Add Or Update")

            self.assertIn("src/**/*.ts", allowed_paths)
            self.assertIn("tests/**/*.ts", allowed_paths)
            self.assertIn("tests/**/*.ts", tests_to_update)
            self.assertNotIn("agentspec/emit.py", allowed_paths)
            self.assertNotIn("tests/test_cli_workflow.py", allowed_paths)
            self.assertNotIn("tests/test_cli_workflow.py", tests_to_update)


class ValidatePathProvenanceTests(unittest.TestCase):
    def test_confirmed_path(self) -> None:
        from agentspec.archetype import validate_path_provenance

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agentspec").mkdir()
            (root / "agentspec" / "cli.py").write_text("")
            self.assertEqual(validate_path_provenance("agentspec/cli.py", root), "confirmed")

    def test_inferred_path(self) -> None:
        from agentspec.archetype import validate_path_provenance

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(validate_path_provenance("src/missing.ts", root), "inferred")

    def test_glob_pattern_marked_pattern(self) -> None:
        from agentspec.archetype import validate_path_provenance

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self.assertEqual(validate_path_provenance("src/**/*.ts", root), "pattern")
            self.assertEqual(validate_path_provenance("docs/**", root), "pattern")


class IsPackAutonomousEligibleTests(unittest.TestCase):
    def _write_pack(self, root: Path, allowed_paths: list[str]) -> Path:
        path = root / "agent" / "context-packs" / "T-999-fixture.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        body = "# T-999: Fixture\n\n## Allowed Paths\n\n"
        for p in allowed_paths:
            body += f"- `{p}`\n"
        path.write_text(body, encoding="utf-8")
        return path

    def test_pack_with_at_least_one_confirmed_is_eligible(self) -> None:
        from agentspec.run import is_pack_autonomous_eligible

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "agentspec").mkdir()
            (root / "agentspec" / "cli.py").write_text("")
            pack = self._write_pack(root, ["agentspec/cli.py", "src/missing.ts"])
            self.assertTrue(is_pack_autonomous_eligible(pack, root))

    def test_pack_with_glob_pattern_is_eligible(self) -> None:
        from agentspec.run import is_pack_autonomous_eligible

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = self._write_pack(root, ["src/**/*.ts"])
            self.assertTrue(is_pack_autonomous_eligible(pack, root))

    def test_pack_with_all_inferred_paths_is_not_eligible(self) -> None:
        from agentspec.run import is_pack_autonomous_eligible

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pack = self._write_pack(root, ["agentspec/missing.py", "docs/missing.md"])
            self.assertFalse(is_pack_autonomous_eligible(pack, root))


def _requirement(
    requirement_id: str,
    title: str,
    *,
    code_targets: list[str],
    test_targets: list[str],
) -> dict[str, object]:
    return {
        "id": requirement_id,
        "title": title,
        "description": title,
        "source_sections": [],
        "priority": "P1",
        "status": "accepted",
        "confidence": "medium",
        "acceptance": ["Generated context pack scope is internally consistent."],
        "code_targets": code_targets,
        "test_targets": test_targets,
    }


def _seed_task_workspace(root: Path, requirements: list[dict[str, object]]) -> None:
    for sub in [
        "agent/context-packs",
        "docs/discovery",
        "docs/source",
        "docs/traceability",
        "src",
        "tests",
    ]:
        (root / sub).mkdir(parents=True, exist_ok=True)
    (root / "docs" / "traceability" / "requirements.yml").write_text(
        json.dumps(requirements),
        encoding="utf-8",
    )
    (root / "docs" / "source" / "sections.yml").write_text("[]", encoding="utf-8")
    (root / "docs" / "source" / "sources.yml").write_text("[]", encoding="utf-8")
    (root / "docs" / "discovery" / "assumptions.yml").write_text("[]", encoding="utf-8")
    (root / "docs" / "discovery" / "readiness.yml").write_text(
        json.dumps({"score": 100, "mode": "normal-implementation"}),
        encoding="utf-8",
    )


def _markdown_list_after_heading(text: str, heading: str) -> list[str]:
    lines = text.splitlines()
    items: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == f"## {heading}":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if in_section and line.strip().startswith("- `") and line.strip().endswith("`"):
            items.append(line.strip()[3:-1])
    return items


if __name__ == "__main__":
    unittest.main()
