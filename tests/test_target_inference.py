"""Tests for archetype-aware target inference and path provenance.

Covers R-136 and R-137 (DCR-0019).
"""

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


if __name__ == "__main__":
    unittest.main()
