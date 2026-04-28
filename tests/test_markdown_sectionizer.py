import unittest

from agentspec.markdown import sectionize_markdown


SAMPLE_MARKDOWN = """# AgentSpec Product Design

Introductory text.

## 1. Executive Summary

AgentSpec must convert Markdown design documents into source-backed artifacts.

### 1.1 Durable Context

- Every implementation task must have a task context pack.

## 2. CLI Specification

### 2.1 `agentspec init`

Creates AgentSpec structure in a repository.

## 30. Open Questions

1. Should the schema format be YAML, JSON, TOML, or Markdown frontmatter?
"""

FENCED_MARKDOWN = """# AgentSpec Product Design

## 1. Real Section

```md
# Not A Heading
## Also Not A Heading
```

## 2. Next Real Section

Content.
"""


class MarkdownSectionizerTests(unittest.TestCase):
    def test_single_document_title_is_not_counted_as_design_section(self) -> None:
        sections = sectionize_markdown(SAMPLE_MARKDOWN, source_id="SRC-0001")

        self.assertEqual([section["id"] for section in sections], ["D-01", "D-01.1", "D-02", "D-02.1", "D-03"])
        self.assertEqual(sections[0]["title"], "1. Executive Summary")
        self.assertEqual(sections[1]["parent"], "D-01")
        self.assertEqual(sections[0]["children"], ["D-01.1"])
        self.assertEqual(sections[0]["heading_path"], ["1. Executive Summary"])
        self.assertEqual(sections[1]["heading_path"], ["1. Executive Summary", "1.1 Durable Context"])

    def test_line_ranges_and_hashes_are_stable(self) -> None:
        first = sectionize_markdown(SAMPLE_MARKDOWN, source_id="SRC-0001")
        second = sectionize_markdown(SAMPLE_MARKDOWN, source_id="SRC-0001")

        self.assertEqual(first, second)
        self.assertTrue(first[0]["content_hash"].startswith("sha256:"))
        self.assertEqual(first[0]["start_line"], 5)
        self.assertEqual(first[0]["end_line"], 12)

    def test_headings_inside_fenced_code_blocks_are_ignored(self) -> None:
        sections = sectionize_markdown(FENCED_MARKDOWN, source_id="SRC-0001")

        self.assertEqual([section["id"] for section in sections], ["D-01", "D-02"])
        self.assertEqual([section["title"] for section in sections], ["1. Real Section", "2. Next Real Section"])


if __name__ == "__main__":
    unittest.main()
