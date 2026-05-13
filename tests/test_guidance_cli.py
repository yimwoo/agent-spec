import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from agentspec.cli import main
from agentspec.review import record_doc_review


class GuidanceCLITests(unittest.TestCase):
    def test_guidance_json_returns_structured_commands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_design(root)
            record_doc_review(
                root,
                artifact_selector="docs/designs/test-design.md",
                verdict="ready",
                reviewer="human",
                summary="Ready.",
            )
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                code = main(["--root", td, "guidance", "docs/designs/test-design.md", "--json"])

            self.assertEqual(code, 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["schema"], "agentspec.post_artifact_guidance.v0")
            self.assertEqual(payload["artifact"]["kind"], "design")
            self.assertEqual(payload["next_actions"][0]["id"], "promote_source")
            self.assertIn("aspec ingest docs/designs/test-design.md", payload["next_actions"][0]["commands"])
            self.assertFalse(payload["agent_display"]["show_terminal_commands"])

    def test_guidance_human_output_hides_terminal_commands(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_design(root)
            output = io.StringIO()

            with contextlib.redirect_stdout(output):
                code = main(["--root", td, "guidance", "docs/designs/test-design.md"])

            self.assertEqual(code, 0)
            text = output.getvalue()
            self.assertIn("needs document review", text)
            self.assertIn("Next: Document review is missing", text)
            self.assertIn("Prompt: Review the design", text)
            self.assertNotIn("aspec review doc", text)


def _write_design(root: Path) -> Path:
    path = root / "docs" / "designs" / "test-design.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """# Test Design

## Summary

Design summary.
""",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
