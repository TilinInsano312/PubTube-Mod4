"""Documentation context loader for PubTube Modulo 4 agent runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DocumentReference:
    """Relevant project document discovered for an agent run.

    Args:
        path: Repository-relative document path.
        title: First Markdown H1 found in the document.
        category: Document category used by the agent brief.
        status: Optional ADR status when present.
        excerpt: Compact content excerpt for analysis.
    """

    path: str
    title: str
    category: str
    status: str | None
    excerpt: str


def load_project_documents(project_root: Path | str = ".") -> list[DocumentReference]:
    """Load Markdown documents from `docs/` for the analysis phase.

    Args:
        project_root: Repository root that contains the `docs` directory.

    Returns:
        Sorted document references with compact metadata and excerpts.
    """

    root = Path(project_root)
    docs_dir = root / "docs"
    if not docs_dir.exists():
        return []

    documents = []
    for path in sorted(docs_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        documents.append(
            DocumentReference(
                path=_relative_path(path, root),
                title=_extract_title(text, fallback=path.stem),
                category=_category_for(path, docs_dir),
                status=_extract_status(text),
                excerpt=_extract_excerpt(text),
            )
        )
    return documents


def render_document_context(documents: list[DocumentReference]) -> str:
    """Render document references for an agent run brief."""

    if not documents:
        return "- No docs found"

    lines = []
    for document in documents:
        status = f" ({document.status})" if document.status else ""
        lines.append(
            f"- `{document.path}` [{document.category}]{status}: "
            f"{document.title} - {document.excerpt}"
        )
    return "\n".join(lines)


def _relative_path(path: Path, root: Path) -> str:
    """Return a repository-relative path using POSIX separators."""

    return path.relative_to(root).as_posix()


def _category_for(path: Path, docs_dir: Path) -> str:
    """Classify project documents by location."""

    try:
        relative = path.relative_to(docs_dir)
    except ValueError:
        return "project-doc"

    if relative.parts and relative.parts[0].lower() == "adr":
        return "adr"
    return "project-doc"


def _extract_title(text: str, fallback: str) -> str:
    """Extract the first Markdown H1 title."""

    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def _extract_status(text: str) -> str | None:
    """Extract a compact ADR status when available."""

    for line in text.splitlines():
        normalized = line.strip()
        if normalized.lower().startswith("## estado"):
            continue
        if normalized.startswith("- **Estado:**"):
            return normalized.removeprefix("- **Estado:**").strip()
        if normalized.lower().startswith("aceptada"):
            return normalized
        if normalized.lower().startswith("aceptado"):
            return normalized
    return None


def _extract_excerpt(text: str, max_chars: int = 180) -> str:
    """Extract a short plain-text excerpt after headings and empty lines."""

    status = _extract_status(text)
    for line in text.splitlines():
        cleaned = _clean_markdown_line(line)
        if not cleaned or cleaned.startswith("#") or cleaned == status:
            continue
        if _is_metadata_line(cleaned):
            continue
        if len(cleaned) > max_chars:
            return f"{cleaned[: max_chars - 3].rstrip()}..."
        return cleaned
    return "Sin resumen disponible."


def _clean_markdown_line(line: str) -> str:
    """Remove simple Markdown markers from one text line."""

    return line.strip().strip("*` ").replace("**", "").replace("`", "")


def _is_metadata_line(line: str) -> bool:
    """Return whether a line is document metadata rather than useful context."""

    normalized = line.lower().lstrip("- ").strip()
    return normalized.startswith(("estado:", "fecha:", "autor:", "version:"))
