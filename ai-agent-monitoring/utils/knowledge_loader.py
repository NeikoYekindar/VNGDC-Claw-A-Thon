"""
Knowledge base loader — reads .md files from the knowledge/ directory
and injects ALL content into LLM context for RCA analysis.

Design: load every .md file unconditionally so that uploading a new file
via the UI takes effect immediately without any redeploy.
The LLM itself selects which sections are relevant for each alert.
"""

from pathlib import Path
from functools import lru_cache


_KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


@lru_cache(maxsize=64)
def _load_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""


def get_relevant_knowledge(alert_name: str = "", alert_description: str = "") -> str:
    """
    Return ALL knowledge base content.
    All .md files are loaded so uploading a new file via UI works immediately.
    The LLM picks the relevant sections based on alert context.
    """
    if not _KNOWLEDGE_DIR.exists():
        return ""

    sections: list[str] = []
    for md_file in sorted(_KNOWLEDGE_DIR.rglob("*.md")):
        content = _load_file(str(md_file))
        if content:
            rel = md_file.relative_to(_KNOWLEDGE_DIR)
            sections.append(f"### Knowledge: {rel}\n{content}")

    if not sections:
        return ""

    return "\n\n---\n\n".join(sections)


def list_knowledge_files() -> list[dict]:
    """Return all available knowledge files with metadata."""
    files = []
    if _KNOWLEDGE_DIR.exists():
        for p in sorted(_KNOWLEDGE_DIR.rglob("*.md")):
            files.append({
                "name": str(p.relative_to(_KNOWLEDGE_DIR)),
                "size": p.stat().st_size,
            })
    return files


def read_knowledge_file(filename: str) -> str | None:
    """Read one markdown file from the knowledge directory."""
    safe = Path(filename).name
    dest = _KNOWLEDGE_DIR / safe
    if dest.exists() and dest.suffix == ".md" and dest.is_file():
        return dest.read_text(encoding="utf-8")
    return None


def save_knowledge_file(filename: str, content: str) -> str:
    """Save a markdown file to the knowledge directory. Returns saved path."""
    # Sanitize filename
    safe = Path(filename).name
    if not safe.endswith(".md"):
        safe += ".md"
    dest = _KNOWLEDGE_DIR / safe
    _KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    # Clear cache so new file is picked up immediately
    _load_file.cache_clear()
    return safe


def delete_knowledge_file(filename: str) -> bool:
    """Delete a knowledge file. Returns True if deleted."""
    safe = Path(filename).name
    dest = _KNOWLEDGE_DIR / safe
    if dest.exists() and dest.suffix == ".md":
        dest.unlink()
        _load_file.cache_clear()
        return True
    return False
