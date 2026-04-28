from __future__ import annotations

from pathlib import Path

from .init import init_project
from .io import copy_text_file, load_data, read_text, sha256_text, utc_now_iso, write_data
from .markdown import document_title, sectionize_markdown
from .paths import slugify


def ingest_source(root: Path, source_path: Path, classification: str = "internal", storage_mode: str = "committed") -> dict[str, object]:
    init_project(root)
    source_path = source_path.resolve()
    if not source_path.exists():
        raise FileNotFoundError(f"Source document not found: {source_path}")
    if source_path.suffix.lower() not in {".md", ".markdown", ".txt"}:
        raise ValueError("MVP ingest supports Markdown/text sources only")

    markdown = read_text(source_path)
    source_id = _source_id_for(root, source_path)
    destination = root / "docs" / "source" / _destination_name(source_path, source_id)
    if source_path != destination.resolve():
        copy_text_file(source_path, destination)

    sources_path = root / "docs" / "source" / "sources.yml"
    sources = load_data(sources_path, [])
    source_record = {
        "id": source_id,
        "kind": "markdown",
        "uri": str(destination.relative_to(root)),
        "original_uri": str(source_path),
        "title": document_title(markdown, source_path.stem),
        "version": None,
        "content_hash": sha256_text(markdown),
        "fetched_at": utc_now_iso(),
        "classification": classification,
        "storage_mode": storage_mode,
    }
    sources = [record for record in sources if record.get("id") != source_id]
    sources.append(source_record)
    write_data(sources_path, sources)

    sections = sectionize_markdown(markdown, source_id=source_id)
    sections_path = root / "docs" / "source" / "sections.yml"
    all_sections = load_data(sections_path, [])
    all_sections = [section for section in all_sections if section.get("source_id") != source_id]
    all_sections.extend(sections)
    write_data(sections_path, all_sections)

    return {"source": source_record, "sections": sections}


def _source_id_for(root: Path, source_path: Path) -> str:
    sources_path = root / "docs" / "source" / "sources.yml"
    sources = load_data(sources_path, [])
    original = str(source_path)
    for source in sources:
        if source.get("original_uri") == original:
            return str(source["id"])
    existing_ids = [str(source.get("id")) for source in sources]
    highest = 0
    for existing_id in existing_ids:
        if existing_id.startswith("SRC-") and existing_id[4:].isdigit():
            highest = max(highest, int(existing_id[4:]))
    return f"SRC-{highest + 1:04d}"


def _destination_name(source_path: Path, source_id: str) -> str:
    slug = slugify(source_path.stem, "source")
    suffix = source_path.suffix or ".md"
    return f"{source_id.lower()}-{slug}{suffix}"
