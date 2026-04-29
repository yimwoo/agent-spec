"""Globstar path matching semantics for policy and drift.

Covers R-145 / DCR-0023.
"""

import unittest

from agentspec.drift import _path_matches
from agentspec.paths import path_matches_pattern
from agentspec.policy import evaluate_policy


class SharedGlobSemanticsTests(unittest.TestCase):
    def test_globstar_matches_zero_or_more_directories(self) -> None:
        self.assertTrue(path_matches_pattern("src/foo.py", "src/**/*.py"))
        self.assertTrue(path_matches_pattern("src/sub/bar.py", "src/**/*.py"))
        self.assertTrue(path_matches_pattern("src/sub/deep/bar.py", "src/**/*.py"))

    def test_single_star_does_not_cross_directories(self) -> None:
        self.assertTrue(path_matches_pattern("src/foo.py", "src/*.py"))
        self.assertFalse(path_matches_pattern("src/sub/bar.py", "src/*.py"))

    def test_directory_tree_pattern_still_matches_descendants(self) -> None:
        self.assertTrue(path_matches_pattern("src/foo.py", "src/**"))
        self.assertTrue(path_matches_pattern("src/sub/bar.py", "src/**"))


class PolicyGlobSemanticsTests(unittest.TestCase):
    def test_policy_allows_generated_globstar_direct_and_nested_files(self) -> None:
        for touched_path in ["src/foo.py", "src/sub/bar.py"]:
            verdict = evaluate_policy(
                allowed_paths=["src/**/*.py"],
                touched_paths=[touched_path],
                iteration=1,
                max_iterations=3,
            )
            self.assertEqual(verdict.decision, "allow", touched_path)

    def test_policy_single_star_rejects_nested_file(self) -> None:
        verdict = evaluate_policy(
            allowed_paths=["src/*.py"],
            touched_paths=["src/sub/bar.py"],
            iteration=1,
            max_iterations=3,
        )
        self.assertEqual(verdict.decision, "halt")
        self.assertIn("forbidden_path", verdict.flags)


class DriftGlobSemanticsTests(unittest.TestCase):
    def test_drift_uses_same_generated_globstar_semantics(self) -> None:
        self.assertTrue(_path_matches("src/foo.py", "src/**/*.py"))
        self.assertTrue(_path_matches("src/sub/bar.py", "src/**/*.py"))
        self.assertFalse(_path_matches("src/sub/bar.py", "src/*.py"))


if __name__ == "__main__":
    unittest.main()
