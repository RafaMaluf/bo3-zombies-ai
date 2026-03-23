import re
import uuid
from typing import Dict, List


MIN_KEYWORD_LENGTH = 4

_STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her",
    "was", "one", "our", "out", "day", "get", "has", "him", "his", "how",
    "its", "may", "new", "now", "old", "see", "two", "who", "did", "use",
    "man", "she", "also", "from", "this", "that", "with", "have", "will",
    "your", "when", "more", "been", "then", "each", "there", "their",
    "what", "make", "like", "time", "just", "into", "than", "them", "some",
    "these", "would", "other", "after", "first", "about", "which", "where",
    "only", "over", "such", "same", "back", "through", "before", "being",
    "between", "both", "during", "here", "should", "under", "while",
}


def _extract_keywords(text: str) -> List[str]:
    """Extract meaningful keywords from text (words > 4 chars, not stop words)."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    seen: set = set()
    keywords: List[str] = []
    for word in words:
        if len(word) > MIN_KEYWORD_LENGTH and word not in _STOP_WORDS and word not in seen:
            seen.add(word)
            keywords.append(word)
    return keywords


def split_markdown_by_sections(content: str) -> List[Dict]:
    """
    Split a markdown document into chunks by ## (H2) sections.

    Each chunk contains:
      - chunk_id: unique identifier (uuid4 hex)
      - section_title: the ## heading text (empty string for pre-heading content)
      - content: raw markdown content of that section
      - keywords: list of meaningful words extracted from content
      - word_count: number of words in content
    """
    # Split on lines that start with "## " (H2 headings only)
    section_pattern = re.compile(r"^(## .+)$", re.MULTILINE)
    parts = section_pattern.split(content)

    chunks: List[Dict] = []

    # parts alternates between: [pre-heading-text, heading, section-body, heading, section-body, ...]
    # Index 0 is always any content before the first ##
    pre_heading = parts[0].strip()
    if pre_heading:
        chunks.append(_make_chunk("", pre_heading))

    i = 1
    while i < len(parts) - 1:
        heading_line = parts[i].strip()          # e.g. "## overview"
        section_title = heading_line.lstrip("#").strip()
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        section_content = f"{heading_line}\n\n{body}".strip()
        chunks.append(_make_chunk(section_title, section_content))
        i += 2

    return chunks


def _make_chunk(section_title: str, content: str) -> Dict:
    return {
        "chunk_id": uuid.uuid4().hex,
        "section_title": section_title,
        "content": content,
        "keywords": _extract_keywords(content),
        "word_count": len(content.split()),
    }
