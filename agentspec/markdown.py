"""Markdown heading parsing and stable source-section generation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .io import sha256_text


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class Heading:
    """One parsed Markdown heading with source position metadata."""

    level: int
    title: str
    line: int


def document_title(markdown: str, fallback: str) -> str:
    """Return the first Markdown heading or a caller-provided fallback."""

    for line in markdown.splitlines():
        match = HEADING_RE.match(line)
        if match:
            return _clean_heading(match.group(2))
    return fallback


def sectionize_markdown(markdown: str, source_id: str) -> list[dict[str, Any]]:
    """Split Markdown into stable hierarchical AgentSpec section records."""

    lines = markdown.splitlines()
    headings = _find_headings(lines)
    if not headings:
        content = markdown.rstrip("\n")
        return [
            {
                "id": "D-01",
                "source_id": source_id,
                "title": "Document",
                "heading_path": ["Document"],
                "start_line": 1,
                "end_line": max(len(lines), 1),
                "content_hash": sha256_text(content),
                "parent": None,
                "children": [],
            }
        ]

    design_headings = _drop_document_title(headings)
    if not design_headings:
        design_headings = headings

    stack: list[dict[str, Any]] = []
    counters: list[int] = []
    sections: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}

    base_level = min(heading.level for heading in design_headings)
    for index, heading in enumerate(design_headings):
        while stack and stack[-1]["level"] >= heading.level:
            stack.pop()

        depth = max(heading.level - base_level, 0)
        while len(counters) <= depth:
            counters.append(0)
        counters = counters[: depth + 1]
        counters[depth] += 1
        section_id = "D-" + ".".join(f"{part:02d}" if i == 0 else str(part) for i, part in enumerate(counters))

        parent = stack[-1]["id"] if stack else None
        heading_path = [item["title"] for item in stack] + [_clean_heading(heading.title)]
        end_line = _section_end_line(design_headings, index, len(lines))
        content = "\n".join(lines[heading.line - 1 : end_line])
        section = {
            "id": section_id,
            "source_id": source_id,
            "title": _clean_heading(heading.title),
            "heading_path": heading_path,
            "start_line": heading.line,
            "end_line": end_line,
            "content_hash": sha256_text(content),
            "parent": parent,
            "children": [],
            "_level": heading.level,
        }
        sections.append(section)
        by_id[section_id] = section
        if parent:
            by_id[parent]["children"].append(section_id)
        stack.append({"id": section_id, "title": section["title"], "level": heading.level})

    for section in sections:
        section.pop("_level", None)
    return sections


def _find_headings(lines: list[str]) -> list[Heading]:
    headings: list[Heading] = []
    in_fence = False
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append(Heading(level=len(match.group(1)), title=match.group(2), line=index))
    return headings


def _drop_document_title(headings: list[Heading]) -> list[Heading]:
    if len(headings) <= 1:
        return headings
    first = headings[0]
    later = headings[1:]
    if first.level == 1 and all(heading.level > first.level for heading in later):
        return later
    return headings


def _section_end_line(headings: list[Heading], index: int, total_lines: int) -> int:
    current = headings[index]
    for next_heading in headings[index + 1 :]:
        if next_heading.level <= current.level:
            return next_heading.line - 1
    return total_lines


def _clean_heading(title: str) -> str:
    return title.strip().strip("#").strip()
