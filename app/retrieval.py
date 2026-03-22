import re
import string
from difflib import SequenceMatcher
from typing import Dict, List, Tuple

# Scoring weights for find_relevant_chunks
KEYWORD_HIT_WEIGHT = 2.0
CONTENT_HIT_WEIGHT = 1.0
TITLE_FUZZY_THRESHOLD = 0.75

# Minimum token length for query tokenization (shorter than keyword extraction
# to catch short but meaningful words like map abbreviations, e.g. "gk", "de")
MIN_TOKEN_LENGTH = 2


# ---------------------------------------------------------------------------
# Alias table: short names / common abbreviations → canonical map IDs
# ---------------------------------------------------------------------------
_MAP_ALIASES: Dict[str, str] = {
    "gk": "gorod_krovi",
    "gorod": "gorod_krovi",
    "gorod krovi": "gorod_krovi",
    "gorodkrovi": "gorod_krovi",
    "pap": "pack_a_punch",
    "pack a punch": "pack_a_punch",
    "packapunch": "pack_a_punch",
    "soe": "shadows_of_evil",
    "shadows": "shadows_of_evil",
    "shadows of evil": "shadows_of_evil",
    "shadowsofevil": "shadows_of_evil",
    "rev": "revelations",
    "revs": "revelations",
    "de": "der_eisendrache",
    "der eisendrache": "der_eisendrache",
    "dereisen": "der_eisendrache",
    "zns": "zetsubou_no_shima",
    "zetsubou": "zetsubou_no_shima",
    "zetsubou no shima": "zetsubou_no_shima",
    "giant": "the_giant",
    "the giant": "the_giant",
    "thegiant": "the_giant",
}


def normalize_query(query: str) -> str:
    """Lowercase, remove punctuation, collapse whitespace."""
    query = query.lower()
    query = query.translate(str.maketrans("", "", string.punctuation))
    query = " ".join(query.split())
    return query


def get_aliases(map_name: str) -> List[str]:
    """
    Return a list containing the canonical name plus all known aliases for it.
    Input may be a canonical map_id or any alias.
    """
    normalized = normalize_query(map_name)
    # Resolve to canonical first
    canonical = _MAP_ALIASES.get(normalized, normalized)
    # Collect all keys that point to this canonical value
    aliases = [key for key, val in _MAP_ALIASES.items() if val == canonical]
    result = [canonical] + [a for a in aliases if a != canonical]
    return result


def fuzzy_match(
    query: str,
    candidates: List[str],
    threshold: float = 0.85,
) -> List[Tuple[str, float]]:
    """
    Compare *query* against each candidate using SequenceMatcher.
    Returns a list of (candidate, score) pairs where score >= threshold,
    sorted by score descending.
    """
    q = normalize_query(query)
    results: List[Tuple[str, float]] = []
    for candidate in candidates:
        c = normalize_query(candidate)
        ratio = SequenceMatcher(None, q, c).ratio()
        if ratio >= threshold:
            results.append((candidate, ratio))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


def find_relevant_chunks(
    query: str,
    chunks: List[Dict],
    top_k: int = 5,
) -> List[Dict]:
    """
    Score each chunk by how well it matches *query* and return the top_k results.

    Scoring strategy (additive):
      +2  per query token that appears in chunk keywords (exact keyword hit)
      +1  per query token that appears anywhere in chunk content (substring hit)
      +fuzzy score  when the whole query fuzzy-matches the section title (>= 0.75)
    """
    q_normalized = normalize_query(query)
    q_tokens = [t for t in q_normalized.split() if len(t) > MIN_TOKEN_LENGTH]

    # Resolve aliases so "gk" also matches gorod_krovi content
    expanded_tokens: List[str] = list(q_tokens)
    for token in q_tokens:
        canonical = _MAP_ALIASES.get(token)
        if canonical:
            expanded_tokens.extend(canonical.replace("_", " ").split())

    scored: List[Tuple[float, Dict]] = []

    for chunk in chunks:
        score = 0.0
        kw_set = set(chunk.get("keywords", []))
        content_lower = chunk.get("content", "").lower()
        title_normalized = normalize_query(chunk.get("section_title", ""))

        for token in expanded_tokens:
            if token in kw_set:
                score += KEYWORD_HIT_WEIGHT
            elif token in content_lower:
                score += CONTENT_HIT_WEIGHT

        # Fuzzy match against section title
        if title_normalized:
            title_ratio = SequenceMatcher(None, q_normalized, title_normalized).ratio()
            if title_ratio >= TITLE_FUZZY_THRESHOLD:
                score += title_ratio

        if score > 0:
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [chunk for _, chunk in scored[:top_k]]
