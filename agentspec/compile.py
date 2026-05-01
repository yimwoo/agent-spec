from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .archetype import detect_archetype, infer_code_targets, infer_test_targets
from .io import lines_between, load_data, sha256_text, write_data, write_text
from .paths import slugify
from .policy import can_emit_source_body, source_body_redaction


SPEC_SHARDS = [
    ("product-charter", "Product Charter", ["executive summary", "goals", "success criteria", "target users", "personas", "non-goals"]),
    ("runtime-architecture", "Runtime Architecture", ["system overview", "core runtime", "architectural principles", "architecture"]),
    ("module-contracts", "Module Contracts", ["domain model", "workflow designs", "task types", "components"]),
    ("security-and-governance", "Security And Governance", ["security", "governance", "policy", "audit", "permissions"]),
    ("observability-and-evaluation", "Observability And Evaluation", ["observability", "evaluation", "metrics", "golden fixtures", "quality"]),
    ("plugin-strategy", "Plugin Strategy", ["plugin", "claude", "codex", "mcp"]),
    ("brownfield-strategy", "Brownfield Strategy", ["brownfield", "repo scanner", "doctor"]),
    ("rollout-plan", "Rollout Plan", ["rollout", "phase", "initial implementation"]),
]

OPEN_QUESTION_TITLE_RE = re.compile(r"\bopen questions?\b", re.IGNORECASE)
LIST_ITEM_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+\.\s+)(.+?)\s*$")
REQUIREMENT_WORD_RE = re.compile(
    r"\b(must|should|support|generate|provide|create|detect|compute|parse|validate|implement|emit|expose|record|run|convert|include|require|responsible)\b",
    re.IGNORECASE,
)


def compile_project(root: Path) -> dict[str, Any]:
    sections = _accepted_sections(load_data(root / "docs" / "source" / "sections.yml", []))
    sources = load_data(root / "docs" / "source" / "sources.yml", [])
    if not sections:
        raise ValueError("No source sections found. Run `agentspec ingest <design.md>` first.")

    source_by_id = {source["id"]: source for source in sources}
    section_texts = {section["id"]: _section_text(root, section, source_by_id) for section in sections}

    shards = _write_spec_shards(root, sections, section_texts)
    source_derived_requirements = _extract_requirements(root, sections, section_texts)
    source_derived_questions = _extract_open_questions(sections, section_texts)
    assumptions = _compile_assumptions(root)
    readiness = _score_readiness(sections)

    # DCR-0003 / R-131, R-132: preserve DCR-originated material when
    # regenerating from source. Reconcile-impossible cases (ID collision)
    # raise loudly with the originating DCR named.
    existing_requirements = load_data(root / "docs" / "traceability" / "requirements.yml", []) or []
    existing_questions = load_data(root / "docs" / "discovery" / "open-questions.yml", []) or []

    preserved_requirements = [r for r in existing_requirements if _is_dcr_originated_requirement(r)]
    preserved_questions = [q for q in existing_questions if _is_dcr_originated_question(q)]

    _check_dcr_id_collisions(source_derived_requirements, preserved_requirements, kind="requirement")
    _check_dcr_id_collisions(source_derived_questions, preserved_questions, kind="open question")

    requirements = source_derived_requirements + preserved_requirements
    open_questions = source_derived_questions + preserved_questions

    write_data(root / "docs" / "traceability" / "requirements.yml", requirements)
    write_data(root / "docs" / "discovery" / "open-questions.yml", open_questions)
    write_data(root / "docs" / "discovery" / "assumptions.yml", assumptions)
    write_data(root / "docs" / "discovery" / "readiness.yml", readiness)
    write_text(root / "docs" / "discovery" / "project-canvas.md", _project_canvas(sections, readiness))
    write_text(root / "reports" / "traceability" / "readiness.md", _readiness_report(readiness))
    write_text(root / "docs" / "traceability" / "design-to-code-map.md", _design_to_code_map(requirements))

    _validate_requirements(source_derived_requirements, {section["id"] for section in sections})
    return {"requirements": requirements, "assumptions": assumptions, "open_questions": open_questions, "readiness": readiness, "spec_shards": shards}


def _accepted_sections(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        section
        for section in sections
        if isinstance(section, dict) and section.get("state", "accepted") == "accepted"
    ]


def _is_dcr_originated_requirement(requirement: dict[str, Any]) -> bool:
    """Return True for any requirement that compile must not regenerate over.

    Covers DCR-originated entries (R-131) plus an explicit `preserve` opt-in
    for hand-curated material that pre-dates the DCR protocol.
    """
    if requirement.get("originating_dcr"):
        return True
    if requirement.get("status") == "proposed-pending-acceptance":
        return True
    if requirement.get("preserve"):
        return True
    return False


def _is_dcr_originated_question(question: dict[str, Any]) -> bool:
    """Return True for any open question that compile must not regenerate over."""
    if question.get("raised_by"):
        return True
    if question.get("preserve"):
        return True
    return False


def _check_dcr_id_collisions(
    source_derived: list[dict[str, Any]],
    preserved: list[dict[str, Any]],
    *,
    kind: str,
) -> None:
    source_ids = {item["id"] for item in source_derived}
    for item in preserved:
        item_id = item.get("id")
        if item_id in source_ids:
            origin = item.get("originating_dcr") or item.get("raised_by") or "unknown DCR"
            raise ValueError(
                f"agentspec compile: cannot reconcile DCR-originated {kind} {item_id} "
                f"(from {origin}) with a newly source-derived {kind} of the same ID. "
                f"Resolve the collision (re-number the DCR-originated entry, or change "
                f"the source content) before re-running compile. See DCR-0003."
            )


def _section_text(root: Path, section: dict[str, Any], source_by_id: dict[str, dict[str, Any]]) -> str:
    source = source_by_id.get(section["source_id"])
    if not source:
        return ""
    if not can_emit_source_body(source):
        return source_body_redaction(source, section)
    source_path = root / source["uri"]
    return lines_between(source_path, int(section["start_line"]), int(section["end_line"]))


def _write_spec_shards(root: Path, sections: list[dict[str, Any]], section_texts: dict[str, str]) -> list[dict[str, Any]]:
    shard_records = []
    for slug, title, keywords in SPEC_SHARDS:
        matched = [section for section in sections if _matches_keywords(section, keywords)]
        if not matched:
            continue
        path = root / "docs" / "spec" / f"{slug}.md"
        write_text(path, _spec_shard_text(title, matched, section_texts))
        shard_records.append(
            {
                "id": "SPEC-" + slug.upper().replace("-", "_"),
                "title": title,
                "path": str(path.relative_to(root)),
                "source_sections": [section["id"] for section in matched],
                "status": "draft",
                "confidence": "medium",
                "content_hash": sha256_text(path.read_text(encoding="utf-8")),
            }
        )

    index = ["# Spec Index", ""]
    for record in shard_records:
        index.append(f"- [{record['title']}]({Path(record['path']).name}) cites {', '.join(record['source_sections'])}")
    write_text(root / "docs" / "spec" / "spec-index.md", "\n".join(index) + "\n")
    write_data(root / "docs" / "spec" / "spec-index.yml", shard_records)
    return shard_records


def _spec_shard_text(title: str, sections: list[dict[str, Any]], section_texts: dict[str, str]) -> str:
    out = [f"# {title}", "", "Status: draft", "Confidence: medium", "", "## Source Sections", ""]
    for section in sections:
        out.append(f"- `{section['id']}` {' > '.join(section['heading_path'])}")
    out.extend(["", "## Source-Backed Notes", ""])
    for section in sections[:12]:
        excerpt = _excerpt(section_texts.get(section["id"], ""))
        out.append(f"### {section['id']} {section['title']}")
        out.append("")
        out.append("Source-backed.")
        out.append("")
        out.append(excerpt or "_No body text in section._")
        out.append("")
    return "\n".join(out)


def _matches_keywords(section: dict[str, Any], keywords: list[str]) -> bool:
    haystack = " ".join(str(part).lower() for part in section.get("heading_path", []))
    return any(keyword in haystack for keyword in keywords)


def _extract_requirements(root: Path, sections: list[dict[str, Any]], section_texts: dict[str, str]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    seen: set[str] = set()
    # R-136: detect host archetype once per compile run; downstream
    # inference uses language-aware paths instead of AgentSpec's
    # Python-specific defaults.
    archetype = detect_archetype(root)
    for section in sections:
        title = str(section["title"])
        if OPEN_QUESTION_TITLE_RE.search(title) or "candidate project names" in title.lower():
            continue
        for candidate in _requirement_candidates(section, section_texts.get(section["id"], "")):
            normalized = _normalize_requirement(candidate)
            if not normalized or normalized.lower() in seen:
                continue
            seen.add(normalized.lower())
            req_id = f"R-{len(requirements) + 1:03d}"
            requirements.append(
                {
                    "id": req_id,
                    "title": _title_from_requirement(normalized),
                    "description": normalized,
                    "source_sections": [section["id"]],
                    "priority": _priority(normalized),
                    "status": "accepted",
                    "confidence": _confidence(normalized),
                    "acceptance": _acceptance(normalized),
                    "code_targets": infer_code_targets(normalized, archetype),
                    "test_targets": infer_test_targets(normalized, archetype),
                    "owner_roles": _owner_roles(normalized),
                }
            )
            if len(requirements) >= 120:
                return requirements
    return requirements


def _requirement_candidates(section: dict[str, Any], text: str) -> list[str]:
    candidates: list[str] = []
    title = str(section["title"])
    title_lower = title.lower()
    if any(keyword in title_lower for keyword in ["agentspec ", "cli", "sectionizer", "context pack", "emitter", "doctor", "drift", "mcp server"]):
        candidates.append(title)

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("|") or stripped.startswith("```") or stripped.startswith("#"):
            continue
        match = LIST_ITEM_RE.match(stripped)
        if match:
            stripped = match.group(1).strip()
        if _looks_like_requirement(stripped):
            candidates.append(stripped)
    return candidates


def _looks_like_requirement(text: str) -> bool:
    if len(text) < 8:
        return False
    lower = text.lower()
    if lower.startswith(("examples:", "input:", "behavior:", "needs:", "use case:")):
        return False
    return bool(REQUIREMENT_WORD_RE.search(text)) or "deliverable" in lower


def _normalize_requirement(text: str) -> str:
    text = re.sub(r"^\s*(?:[-*+]\s+|\d+\.\s+)", "", text)
    text = text.replace("`", "")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip(" .")
    if not text:
        return ""
    if text[-1] not in ".!?":
        text += "."
    return text


def _title_from_requirement(text: str) -> str:
    title = text.rstrip(".")
    title = re.sub(r"^(AgentSpec\s+)?(must|should|will|can|shall)\s+", "", title, flags=re.IGNORECASE)
    return title[:96]


def _priority(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ["must", "cannot", "required", "100%", "source", "security", "task context pack"]):
        return "P0"
    if any(word in lower for word in ["should", "v1", "cli", "generate", "validate"]):
        return "P1"
    return "P2"


def _confidence(text: str) -> str:
    lower = text.lower()
    if any(word in lower for word in ["must", "will not", "v1", "success criteria"]):
        return "high"
    return "medium"


def _acceptance(text: str) -> list[str]:
    return [
        f"Generated artifacts or implementation demonstrate: {text}",
        "Evidence cites the source section listed on this requirement.",
    ]


def _code_targets(text: str) -> list[str]:
    lower = text.lower()
    targets = []
    if "init" in lower or "artifact layout" in lower:
        targets.append("agentspec/init.py")
    if "cli" in lower or "command" in lower:
        targets.append("agentspec/cli.py")
    if "markdown" in lower or "section" in lower or "hash" in lower:
        targets.append("agentspec/markdown.py")
    if "requirement" in lower or "compile" in lower or "spec" in lower or "readiness" in lower:
        targets.append("agentspec/compile.py")
    if "context pack" in lower or "task" in lower:
        targets.append("agentspec/task.py")
    if "agent" in lower or "claude" in lower or "codex" in lower or "emit" in lower:
        targets.append("agentspec/emit.py")
    if "doctor" in lower or "brownfield" in lower or "repo" in lower:
        targets.append("agentspec/doctor.py")
    if "drift" in lower or "diff" in lower:
        targets.append("agentspec/drift.py")
    return sorted(set(targets)) or ["docs/traceability/requirements.yml"]


def _test_targets(text: str) -> list[str]:
    lower = text.lower()
    if "markdown" in lower or "section" in lower:
        return ["tests/test_markdown_sectionizer.py"]
    return ["tests/test_cli_workflow.py"]


def _owner_roles(text: str) -> list[str]:
    lower = text.lower()
    roles = ["coordinator"]
    if "security" in lower or "governance" in lower:
        roles.append("security-reviewer")
    if "test" in lower or "evaluation" in lower:
        roles.append("test-eval-reviewer")
    if "architecture" in lower or "module" in lower:
        roles.append("architect-reviewer")
    return roles


def _extract_open_questions(sections: list[dict[str, Any]], section_texts: dict[str, str]) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for section in sections:
        if not OPEN_QUESTION_TITLE_RE.search(str(section["title"])):
            continue
        for line in section_texts.get(section["id"], "").splitlines():
            match = LIST_ITEM_RE.match(line.strip())
            if match:
                question = _normalize_requirement(match.group(1))
                questions.append(
                    {
                        "id": f"Q-{len(questions) + 1:03d}",
                        "question": question,
                        "status": "open",
                        "impact": _question_impact(question),
                        "source_sections": [section["id"]],
                    }
                )
    return questions


def _question_impact(question: str) -> list[str]:
    lower = question.lower()
    impact = []
    for keyword in ["security", "enterprise", "plugin", "mcp", "github", "schema", "language", "automation"]:
        if keyword in lower:
            impact.append(keyword)
    return impact or ["product"]


def _compile_assumptions(root: Path) -> list[dict[str, Any]]:
    assumptions = load_data(root / "docs" / "discovery" / "assumptions.yml", []) or []
    if not any(assumption.get("id") == "A-002" for assumption in assumptions):
        assumptions.append(
            {
                "id": "A-002",
                "statement": "The MVP stores structured .yml artifacts as YAML-compatible JSON to avoid runtime dependencies.",
                "source": "implementation_choice",
                "confidence": "medium",
                "status": "accepted",
                "impact": ["schema format", "packaging", "local execution"],
            }
        )
    return assumptions


def _score_readiness(sections: list[dict[str, Any]]) -> dict[str, Any]:
    headings = " ".join(" ".join(section.get("heading_path", [])) for section in sections).lower()
    checks = {
        "problem_definition": ["executive summary", "problem"],
        "target_users": ["target users", "personas", "audience"],
        "goals": ["goals"],
        "non_goals": ["non-goals", "non goals"],
        "success_criteria": ["success criteria"],
        "architecture_boundaries": ["architecture", "core runtime", "system overview"],
        "data_model": ["domain model", "schema"],
        "integrations": ["plugin", "mcp", "claude", "codex", "cli"],
        "security_model": ["security", "governance", "permissions"],
        "test_strategy": ["test", "evaluation", "quality", "golden fixtures", "success criteria"],
        "rollout_plan": ["rollout", "phase"],
    }
    dimensions = {
        name: {"score": 10 if any(keyword in headings for keyword in keywords) else 0, "signals": [keyword for keyword in keywords if keyword in headings]}
        for name, keywords in checks.items()
    }
    score = round(sum(value["score"] for value in dimensions.values()) / (len(dimensions) * 10) * 100)
    if score < 30:
        mode = "discovery"
    elif score < 60:
        mode = "discovery+spike"
    elif score < 80:
        mode = "bounded-implementation"
    else:
        mode = "normal-implementation"
    return {"score": score, "mode": mode, "dimensions": dimensions, "summary": f"Readiness is {score}/100 ({mode})."}


def _project_canvas(sections: list[dict[str, Any]], readiness: dict[str, Any]) -> str:
    by_title = {str(section["title"]).lower(): section for section in sections}
    return f"""# Project Canvas

## Canonical Sources

- {len(sections)} source sections compiled.

## Problem

See source sections matching Executive Summary and Problem.

## Goals

See source sections matching Product Goals and Success Criteria.

## Readiness

{readiness['summary']}

## Important Sections

{_important_section_list(by_title)}
"""


def _important_section_list(by_title: dict[str, dict[str, Any]]) -> str:
    rows = []
    for keyword in ["executive summary", "goals", "success criteria", "core runtime", "security", "rollout"]:
        for title, section in by_title.items():
            if keyword in title:
                rows.append(f"- `{section['id']}` {section['title']}")
                break
    return "\n".join(rows) or "- No important sections detected yet."


def _readiness_report(readiness: dict[str, Any]) -> str:
    out = ["# Readiness Report", "", readiness["summary"], "", "| Dimension | Score | Signals |", "|---|---:|---|"]
    for name, info in readiness["dimensions"].items():
        out.append(f"| {name.replace('_', ' ').title()} | {info['score']} | {', '.join(info['signals']) or '-'} |")
    return "\n".join(out) + "\n"


def _design_to_code_map(requirements: list[dict[str, Any]]) -> str:
    out = ["# Design To Code Map", "", "| Requirement | Source Sections | Code Targets | Tests |", "|---|---|---|---|"]
    for req in requirements:
        out.append(
            f"| `{req['id']}` {req['title']} | {', '.join(req['source_sections'])} | {', '.join(req['code_targets'])} | {', '.join(req['test_targets'])} |"
        )
    return "\n".join(out) + "\n"


def _excerpt(text: str, limit: int = 1200) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rstrip() + "\n\n..."


def _validate_requirements(requirements: list[dict[str, Any]], valid_sections: set[str]) -> None:
    for requirement in requirements:
        if not requirement.get("source_sections"):
            raise ValueError(f"Requirement {requirement.get('id')} has no source sections")
        for section_id in requirement["source_sections"]:
            if section_id not in valid_sections:
                raise ValueError(f"Requirement {requirement.get('id')} references missing source section {section_id}")
        if not requirement.get("acceptance"):
            raise ValueError(f"Requirement {requirement.get('id')} has no acceptance criteria")
