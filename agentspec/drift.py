from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .io import ensure_writable_dir, load_data, utc_now_iso, write_text


SENSITIVE_PATH_HINTS = ["auth", "security", "secret", "permission", "policy", "billing"]
HIGH_IMPACT_TERMS = {
    "architecture",
    "auth",
    "authorization",
    "billing",
    "governance",
    "permission",
    "policy",
    "protocol",
    "schema",
    "security",
    "storage",
}
STOPWORDS = {
    "0001",
    "able",
    "accepted",
    "against",
    "agent",
    "agentspec",
    "and",
    "any",
    "are",
    "code",
    "comparing",
    "create",
    "diff",
    "docs",
    "file",
    "files",
    "for",
    "from",
    "generate",
    "generated",
    "implementation",
    "include",
    "into",
    "must",
    "not",
    "path",
    "paths",
    "project",
    "requirement",
    "requirements",
    "responsible",
    "section",
    "sections",
    "should",
    "source",
    "spec",
    "task",
    "tests",
    "that",
    "the",
    "this",
    "with",
}


@dataclass
class FileChange:
    path: str
    old_path: str | None = None
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    status: str = "modified"

    @property
    def added_count(self) -> int:
        return len(self.added_lines)

    @property
    def removed_count(self) -> int:
        return len(self.removed_lines)

    @property
    def tokens(self) -> set[str]:
        return _tokens(" ".join([self.path, *self.added_lines, *self.removed_lines]))


@dataclass
class ContextPack:
    id: str
    path: str
    requirements: set[str]
    allowed_paths: list[str]
    originating_dcrs: list[str] = field(default_factory=list)


@dataclass
class FileAssessment:
    file: FileChange
    verdict: str
    requirement_ids: list[str]
    context_pack_ids: list[str]
    originating_dcrs: list[str]
    findings: list[str]


def run_drift(root: Path, diff_ref: str | None = None, report_dir: Path | None = None) -> Path:
    """Generate the spec-drift review report.

    Defaults to `<root>/reports/drift/latest.md`. When `report_dir` is
    given (DCR-0020), writes to `<report_dir>/drift/latest.md` — used
    for cross-repo runs where the target checkout is not writable.
    """

    destination = _drift_destination(root, report_dir)
    ensure_writable_dir(destination)

    diff_text = _diff_text(root, diff_ref)
    changes = _parse_unified_diff(diff_text)
    if not changes:
        changes = [FileChange(path=file) for file in _changed_files(root, diff_ref)]
    requirements = load_data(root / "docs" / "traceability" / "requirements.yml", [])
    sections = load_data(root / "docs" / "source" / "sections.yml", [])
    context_packs = _context_packs(root)
    adrs = _adr_paths(root)
    report = _report(changes, requirements, sections, context_packs, adrs, diff_ref, bool(diff_text.strip()))
    path = destination / "latest.md"
    write_text(path, report)
    return path


def _drift_destination(root: Path, report_dir: Path | None) -> Path:
    if report_dir is None:
        return root / "reports" / "drift"
    base = report_dir if report_dir.is_absolute() else root / report_dir
    return base / "drift"


def _diff_text(root: Path, diff_ref: str | None) -> str:
    if diff_ref:
        diff_path = Path(diff_ref)
        if not diff_path.is_absolute():
            diff_path = root / diff_path
        if diff_path.exists() and diff_path.is_file():
            return diff_path.read_text(encoding="utf-8")

    command = ["git", "diff", "--no-ext-diff", "--unified=0"]
    if diff_ref:
        command.append(diff_ref)
    try:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return ""
    if result.returncode != 0:
        return ""
    return result.stdout


def _changed_files(root: Path, diff_ref: str | None) -> list[str]:
    command = ["git", "diff", "--name-only"]
    if diff_ref:
        command.append(diff_ref)
    try:
        result = subprocess.run(command, cwd=root, text=True, capture_output=True, check=False)
    except FileNotFoundError:
        return []
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _parse_unified_diff(diff_text: str) -> list[FileChange]:
    changes: list[FileChange] = []
    current: FileChange | None = None
    old_path: str | None = None

    for raw_line in diff_text.splitlines():
        if raw_line.startswith("diff --git "):
            if current:
                changes.append(current)
            parts = raw_line.split()
            old_path = _strip_diff_prefix(parts[2]) if len(parts) > 2 else None
            new_path = _strip_diff_prefix(parts[3]) if len(parts) > 3 else old_path
            current = FileChange(path=new_path or old_path or "unknown", old_path=old_path)
            continue

        if current is None:
            continue

        if raw_line.startswith("new file mode"):
            current.status = "added"
            continue
        if raw_line.startswith("deleted file mode"):
            current.status = "deleted"
            continue
        if raw_line.startswith("rename from "):
            current.old_path = raw_line.removeprefix("rename from ").strip()
            current.status = "renamed"
            continue
        if raw_line.startswith("rename to "):
            current.path = raw_line.removeprefix("rename to ").strip()
            current.status = "renamed"
            continue
        if raw_line.startswith("+++ "):
            new_path = raw_line.removeprefix("+++ ").strip()
            if new_path != "/dev/null":
                current.path = _strip_diff_prefix(new_path)
            continue
        if raw_line.startswith("--- "):
            old_path = raw_line.removeprefix("--- ").strip()
            if old_path != "/dev/null":
                current.old_path = _strip_diff_prefix(old_path)
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            current.added_lines.append(raw_line[1:])
            continue
        if raw_line.startswith("-") and not raw_line.startswith("---"):
            current.removed_lines.append(raw_line[1:])

    if current:
        changes.append(current)
    return [change for change in changes if change.path and change.path != "/dev/null"]


def _strip_diff_prefix(path: str) -> str:
    if path.startswith(("a/", "b/")):
        return path[2:]
    return path


def _context_packs(root: Path) -> list[ContextPack]:
    packs = []
    for path in sorted((root / "agent" / "context-packs").glob("T-*.md")):
        text = path.read_text(encoding="utf-8")
        requirements = set(re.findall(r"`(R-\d{3})`", _section(text, "Requirements")))
        allowed_paths = re.findall(r"`([^`]+)`", _section(text, "Allowed Paths"))
        originating_dcrs = _extract_originating_dcrs(text)
        packs.append(
            ContextPack(
                id=path.stem.split("-", 2)[0] + "-" + path.stem.split("-", 2)[1],
                path=str(path.relative_to(root)),
                requirements=requirements,
                allowed_paths=allowed_paths,
                originating_dcrs=originating_dcrs,
            )
        )
    return packs


def _extract_originating_dcrs(text: str) -> list[str]:
    """Pull DCR ids from header lines like:

        Originating DCR: `DCR-0019-...`
        Originating DCRs: `DCR-0002-...`, `DCR-0003-...`

    Returns a deduplicated list preserving first-seen order. Empty list
    when the pack predates the DCR protocol (early packs like T-001/T-002).
    """
    head = "\n".join(text.splitlines()[:30])
    dcrs: list[str] = []
    for match in re.finditer(r"^Originating\s+DCRs?:[^\n]*", head, re.MULTILINE):
        for dcr in re.findall(r"DCR-\d{4}", match.group(0)):
            if dcr not in dcrs:
                dcrs.append(dcr)
    return dcrs


def _section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return ""
    next_match = re.search(r"^## .+$", text[match.end() :], re.MULTILINE)
    if not next_match:
        return text[match.end() :]
    return text[match.end() : match.end() + next_match.start()]


def _adr_paths(root: Path) -> list[str]:
    adr_root = root / "docs" / "adr"
    if not adr_root.exists():
        return []
    return sorted(str(path.relative_to(root)) for path in adr_root.glob("*.md"))


def _report(
    changes: list[FileChange],
    requirements: list[dict[str, Any]],
    sections: list[dict[str, Any]],
    context_packs: list[ContextPack],
    adrs: list[str],
    diff_ref: str | None,
    parsed_diff: bool,
) -> str:
    section_titles = {section["id"]: " ".join(section.get("heading_path", [])) for section in sections}
    changed_paths = [change.path for change in changes]
    assessments = [_assess_file(change, requirements, section_titles, context_packs, changed_paths) for change in changes]
    findings = _summary_findings(assessments, changes, adrs, parsed_diff)
    decision = _decision(assessments, changes, parsed_diff, findings)

    out = [
        "# Spec Compliance Review",
        "",
        "## Decision",
        "",
        decision,
        "",
        "## Compared Against",
        "",
        f"- Diff: {diff_ref or 'working tree'}",
        f"- Generated: {utc_now_iso()}",
        f"- Requirements loaded: {len(requirements)}",
        f"- Context packs loaded: {len(context_packs)}",
        f"- ADRs loaded: {len(adrs)}",
        "",
        "## Changed Files",
        "",
    ]
    if changes:
        out.extend(f"- `{change.path}` ({change.status}, +{change.added_count}/-{change.removed_count})" for change in changes)
    else:
        out.append("- None detected")

    out.extend(["", "## Findings", ""])
    out.extend(f"- {finding}" for finding in findings)
    if not findings:
        out.append("- No drift concerns detected by path, requirement, context-pack, ADR, or security checks.")

    out.extend(["", "## File Impact", "", "| File | Verdict | Requirements | Context Packs | DCRs | Evidence |", "|---|---|---|---|---|---|"])
    if assessments:
        for assessment in assessments:
            out.append(
                "| "
                f"`{assessment.file.path}` | {assessment.verdict} | "
                f"{_id_list(assessment.requirement_ids)} | "
                f"{_id_list(assessment.context_pack_ids)} | "
                f"{_id_list(assessment.originating_dcrs)} | "
                f"{_escape_cell('; '.join(assessment.findings))} |"
            )
    else:
        out.append("| None | review | - | - | - | No git diff was available or no files changed. |")

    impacted = {requirement_id for assessment in assessments for requirement_id in assessment.requirement_ids}
    out.extend(["", "## Requirement Coverage", "", "| Requirement | Status | Evidence |", "|---|---|---|"])
    for requirement in requirements:
        requirement_id = requirement["id"]
        if requirement_id in impacted:
            files = [assessment.file.path for assessment in assessments if requirement_id in assessment.requirement_ids]
            out.append(f"| `{requirement_id}` | impacted | Changed file(s): {_escape_cell(', '.join(f'`{file}`' for file in files))}. |")
        else:
            out.append(f"| `{requirement_id}` | not-impacted | No changed file matched code targets, test targets, or semantic terms. |")
    return "\n".join(out) + "\n"


def _assess_file(
    change: FileChange,
    requirements: list[dict[str, Any]],
    section_titles: dict[str, str],
    context_packs: list[ContextPack],
    changed_paths: list[str],
) -> FileAssessment:
    impacted = _impacted_requirements(change, requirements, section_titles)
    matching_packs = _matching_context_packs(change.path, impacted, context_packs)
    findings: list[str] = []

    if impacted:
        findings.append(f"Maps to {len(impacted)} accepted requirement(s).")
    else:
        findings.append("No accepted requirement maps to this file or diff terms.")

    if matching_packs:
        findings.append("Allowed by task context pack scope.")
    else:
        findings.append("No task context pack allows this file.")

    if any(hint in change.path.lower() for hint in SENSITIVE_PATH_HINTS):
        findings.append("Security-sensitive path changed; request security reviewer confirmation.")

    if change.path.startswith("docs/spec/") and not _mentions_source_id(change):
        findings.append("Spec artifact changed without an added source section citation.")

    expected_tests = _expected_tests(impacted)
    changed_expected_tests = {test for test in expected_tests if any(_path_matches(path, test) for path in changed_paths)}
    if expected_tests and not _is_test_path(change.path) and not changed_expected_tests:
        findings.append(f"Expected tests for impacted requirements: {', '.join(sorted(expected_tests))}.")

    verdict = "aligned"
    if any(
        finding.startswith("No accepted requirement")
        or finding.startswith("No task context")
        or finding.startswith("Expected tests")
        for finding in findings
    ):
        verdict = "review"
    if any("Security-sensitive" in finding for finding in findings):
        verdict = "review"

    # R-126: union of originating DCRs across the matching packs.
    # Preserves first-seen order so the report is deterministic.
    originating_dcrs: list[str] = []
    for pack in matching_packs:
        for dcr in pack.originating_dcrs:
            if dcr not in originating_dcrs:
                originating_dcrs.append(dcr)

    return FileAssessment(
        file=change,
        verdict=verdict,
        requirement_ids=[requirement["id"] for requirement in impacted],
        context_pack_ids=[pack.id for pack in matching_packs],
        originating_dcrs=originating_dcrs,
        findings=findings,
    )


def _impacted_requirements(
    change: FileChange,
    requirements: list[dict[str, Any]],
    section_titles: dict[str, str],
) -> list[dict[str, Any]]:
    impacted = []
    change_tokens = change.tokens
    for requirement in requirements:
        targets = [*requirement.get("code_targets", []), *requirement.get("test_targets", [])]
        if any(_path_matches(change.path, target) for target in targets):
            impacted.append(requirement)
            continue

        requirement_text = " ".join(
            [
                str(requirement.get("title", "")),
                str(requirement.get("description", "")),
                " ".join(section_titles.get(section_id, "") for section_id in requirement.get("source_sections", [])),
            ]
        )
        overlap = change_tokens & _tokens(requirement_text)
        if len(overlap) >= 2:
            impacted.append(requirement)
    return impacted


def _matching_context_packs(path: str, impacted_requirements: list[dict[str, Any]], context_packs: list[ContextPack]) -> list[ContextPack]:
    impacted_ids = {requirement["id"] for requirement in impacted_requirements}
    matches = []
    for pack in context_packs:
        path_allowed = any(_path_matches(path, allowed_path) for allowed_path in pack.allowed_paths)
        requirement_allowed = bool(impacted_ids & pack.requirements)
        if path_allowed and (not impacted_ids or requirement_allowed or not pack.requirements):
            matches.append(pack)
    return matches


def _path_matches(path: str, pattern: str) -> bool:
    path = path.strip("/")
    pattern = pattern.strip("/")
    if not pattern:
        return False
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-3].rstrip("/") + "/")
    if pattern.endswith("/*"):
        prefix = pattern[:-2].rstrip("/")
        return path.startswith(prefix + "/") and "/" not in path[len(prefix) + 1 :]
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern or path.startswith(pattern.rstrip("/") + "/")


def _expected_tests(impacted: list[dict[str, Any]]) -> set[str]:
    tests = set()
    for requirement in impacted:
        tests.update(requirement.get("test_targets", []))
    return tests


def _is_test_path(path: str) -> bool:
    return path.startswith("tests/") or "/test_" in path or path.endswith("_test.py")


def _mentions_source_id(change: FileChange) -> bool:
    return any(re.search(r"\bD-\d+(?:\.\d+)?\b", line) for line in change.added_lines)


def _summary_findings(assessments: list[FileAssessment], changes: list[FileChange], adrs: list[str], parsed_diff: bool) -> list[str]:
    findings: list[str] = []
    if not changes:
        findings.append("No git diff was available or no files changed; semantic analysis could not run.")
    elif not parsed_diff:
        findings.append("Only changed file names were available; line-level semantic analysis could not run.")

    review_files = [assessment.file.path for assessment in assessments if assessment.verdict != "aligned"]
    if review_files:
        findings.append(f"{len(review_files)} changed file(s) need reviewer attention: {', '.join(review_files)}.")

    if any(any(hint in change.path.lower() for hint in SENSITIVE_PATH_HINTS) for change in changes):
        findings.append("Security-sensitive paths changed; route to a security reviewer.")

    high_impact_files = [change.path for change in changes if change.tokens & HIGH_IMPACT_TERMS]
    changed_adrs = [change.path for change in changes if change.path.startswith("docs/adr/")]
    if high_impact_files and not changed_adrs:
        findings.append(f"High-impact terms detected without an ADR change: {', '.join(high_impact_files)}.")
    elif changed_adrs:
        findings.append(f"ADR change present: {', '.join(changed_adrs)}.")
    elif adrs:
        findings.append("Accepted ADRs are available for comparison.")

    return findings


def _decision(assessments: list[FileAssessment], changes: list[FileChange], parsed_diff: bool, findings: list[str]) -> str:
    if not changes:
        return "approve-with-comments"
    if any(assessment.verdict != "aligned" for assessment in assessments):
        return "approve-with-comments"
    if not parsed_diff:
        return "approve-with-comments"
    if any(finding.startswith("High-impact terms") for finding in findings):
        return "approve-with-comments"
    return "approve"


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_]{2,}", text.lower())
        if token not in STOPWORDS and not token.isdigit()
    }


def _id_list(ids: list[str]) -> str:
    if not ids:
        return "-"
    return ", ".join(f"`{item}`" for item in ids)


def _escape_cell(value: str) -> str:
    return value.replace("|", "\\|") or "-"
