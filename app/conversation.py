from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain import RetrievalResult
from app.knowledge_base import KnowledgeBase
from app.retrieval import expanded_query_tokens, normalize_text, tokenize
from app.schemas import ConversationMessage

REFERENTIAL_OPENERS = {
    "agora",
    "aquele",
    "aquela",
    "aqueles",
    "aquelas",
    "como",
    "depois",
    "e",
    "esse",
    "essa",
    "esses",
    "essas",
    "este",
    "esta",
    "isso",
    "qual",
    "quais",
    "what",
    "where",
    "which",
}
REFERENTIAL_TERMS = {
    "another",
    "others",
    "outro",
    "outra",
    "outros",
    "outras",
    "tambem",
    "também",
}


@dataclass(frozen=True, slots=True)
class DocumentReference:
    path: str
    label: str
    category: str
    summary: str


RESOLUTION_SYSTEM_PROMPT = """
You resolve ambiguous follow-up questions for a Call of Duty: Black Ops III
Zombies knowledge-base assistant. Do not answer the gameplay question.

Use the active map, recent conversation, previous source paths, and the exact
document catalog to determine what the user means.

Rules:
- Resolve ellipsis and references such as "and the others?", "what about it?",
  "where is the third one?", and equivalent wording in any language.
- If one document or intent is clear, produce a self-contained resolved_query.
- If the user asks about a broad family with multiple distinct guides, request
  one concise clarification and return the matching document paths.
- If the previous answer covered one item and the user asks for the others,
  return its sibling guides, normally excluding the guide already covered.
- When a catalog has one base-item guide and several upgrade or variant guides,
  a plural request for the variants should normally return the upgrade guides.
  Include the base guide only when the user asks how to obtain or start it.
- Never invent a document path or a gameplay fact.
- Keep clarification_question in the user's language.

Return one valid JSON object and no text outside it:
{
  "resolved_query": "self-contained search query or empty string",
  "need_clarification": false,
  "clarification_question": "",
  "candidate_document_paths": ["exact/path/from/catalog.md"]
}
""".strip()


def history_without_duplicate_current_message(
    history: list[ConversationMessage],
    current_message: str,
    limit: int,
) -> list[ConversationMessage]:
    selected = list(history[-limit:])
    if (
        selected
        and selected[-1].role == "user"
        and normalize_text(selected[-1].content) == normalize_text(current_message)
    ):
        selected.pop()
    return selected


def should_resolve_follow_up(
    message: str,
    history: list[ConversationMessage],
    active_map_id: str | None,
    retrieval: RetrievalResult,
) -> bool:
    if not active_map_id or not history:
        return False
    if retrieval.needs_clarification:
        return True

    words = normalize_text(message).split()
    if not words or len(words) > 8:
        return False
    return words[0] in REFERENTIAL_OPENERS or bool(set(words) & REFERENTIAL_TERMS)


def document_catalog(
    knowledge_base: KnowledgeBase,
    map_id: str,
) -> tuple[DocumentReference, ...]:
    record = knowledge_base.maps.get(map_id)
    if record is None:
        return ()

    references: list[DocumentReference] = []
    for path in record.document_paths:
        chunk = next(
            (
                knowledge_base.chunks[chunk_id]
                for chunk_id in record.chunk_ids
                if knowledge_base.chunks[chunk_id].path == path
            ),
            None,
        )
        if chunk is None:
            continue
        references.append(
            DocumentReference(
                path=path,
                label=_document_label(path),
                category=chunk.category,
                summary=chunk.file_summary,
            )
        )
    return tuple(references)


def build_resolution_messages(
    *,
    message: str,
    history: list[ConversationMessage],
    map_name: str,
    catalog: tuple[DocumentReference, ...],
) -> list[dict[str, str]]:
    history_lines: list[str] = []
    for item in history[-6:]:
        source_suffix = ""
        if item.source_paths:
            source_suffix = f" [sources: {', '.join(item.source_paths)}]"
        history_lines.append(f"{item.role.upper()}{source_suffix}: {item.content[:3000]}")
    catalog_lines = [
        (
            f"- PATH: {item.path} | LABEL: {item.label} | "
            f"CATEGORY: {item.category} | SUMMARY: {item.summary}"
        )
        for item in catalog
    ]
    user_content = "\n\n".join(
        [
            f"ACTIVE MAP\n{map_name}",
            "RECENT CONVERSATION\n" + ("\n".join(history_lines) or "(none)"),
            "DOCUMENT CATALOG\n" + "\n".join(catalog_lines),
            f"CURRENT FOLLOW-UP\n{message}",
        ]
    )
    return [
        {"role": "system", "content": RESOLUTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def validated_document_options(
    paths: list[str],
    catalog: tuple[DocumentReference, ...],
    message: str = "",
) -> list[DocumentReference]:
    allowed = {item.path: item for item in catalog}
    options: list[DocumentReference] = []
    seen: set[str] = set()
    for path in paths:
        item = allowed.get(path)
        if item is None or item.path in seen:
            continue
        seen.add(item.path)
        options.append(item)

    normalized_message = normalize_text(message)
    if "base" not in normalized_message:
        upgrade_options = [
            item for item in options if "upgrade guide" in normalize_text(item.summary)
        ]
        base_paths = {item.path for item in options if "base" in normalize_text(item.summary)}
        if len(upgrade_options) >= 2 and base_paths:
            options = [item for item in options if item.path not in base_paths]
    if len(options) > 8:
        return []
    return options


def deterministic_follow_up_options(
    message: str,
    history: list[ConversationMessage],
    catalog: tuple[DocumentReference, ...],
) -> list[DocumentReference]:
    topic_options = _topic_document_options(message, catalog)
    if len(topic_options) >= 2:
        return topic_options

    words = set(normalize_text(message).split())
    if words & REFERENTIAL_TERMS:
        sibling_options = _sibling_document_options(history, catalog)
        if len(sibling_options) >= 2:
            return sibling_options
    return []


def source_anchored_query(
    message: str,
    history: list[ConversationMessage],
    catalog: tuple[DocumentReference, ...],
) -> str:
    by_path = {item.path: item for item in catalog}
    for history_item in reversed(history):
        if history_item.role != "assistant" or not history_item.source_paths:
            continue
        labels = list(
            dict.fromkeys(
                by_path[path].label for path in history_item.source_paths if path in by_path
            )
        )
        if labels:
            return f"{message} {' '.join(labels)}"
    return ""


def clarification_for_options(
    message: str,
    map_name: str,
    options: list[DocumentReference],
    fallback: str,
) -> str:
    if not options:
        return fallback
    words = set(normalize_text(message).split())
    portuguese_markers = {
        "a",
        "agora",
        "como",
        "e",
        "o",
        "os",
        "outro",
        "outros",
        "qual",
        "quero",
    }
    if words & portuguese_markers:
        return (
            f"Encontrei {len(options)} guias relacionados em {map_name}. "
            "Qual deles você quer consultar?"
        )
    return f"I found {len(options)} related guides in {map_name}. Which one do you want?"


def _topic_document_options(
    message: str,
    catalog: tuple[DocumentReference, ...],
) -> list[DocumentReference]:
    query_tokens = set(expanded_query_tokens(message)) - REFERENTIAL_TERMS
    if not query_tokens:
        return []

    scored: list[tuple[float, DocumentReference]] = []
    for item in catalog:
        label_tokens = set(tokenize(item.label))
        summary_tokens = set(tokenize(item.summary))
        strong_matches = query_tokens & label_tokens
        weak_matches = query_tokens & summary_tokens
        score = 4.0 * len(strong_matches) + len(weak_matches)
        if score > 0:
            scored.append((score, item))
    if not scored:
        return []

    scored.sort(key=lambda pair: (-pair[0], pair[1].path))
    cutoff = scored[0][0] * 0.65
    options = [item for score, item in scored if score >= cutoff and item.category != "general"]
    return options[:8]


def _sibling_document_options(
    history: list[ConversationMessage],
    catalog: tuple[DocumentReference, ...],
) -> list[DocumentReference]:
    by_path = {item.path: item for item in catalog}
    previous_paths: list[str] = []
    for history_item in reversed(history):
        if history_item.role == "assistant" and history_item.source_paths:
            previous_paths = [path for path in history_item.source_paths if path in by_path]
            break
    if not previous_paths:
        return []

    source_items = [by_path[path] for path in previous_paths]
    source_path_set = set(previous_paths)
    source_label_tokens = {
        token for item in source_items for token in tokenize(item.label) if not token.isdigit()
    }
    source_categories = {item.category for item in source_items}
    strong_matches = [
        item
        for item in catalog
        if item.path not in source_path_set
        and item.category in source_categories
        and source_label_tokens.intersection(tokenize(item.label))
    ]
    if strong_matches:
        return strong_matches[:8]

    same_category = [
        item
        for item in catalog
        if item.path not in source_path_set and item.category in source_categories
    ]
    if len(same_category) <= 5:
        return same_category
    return []


def _document_label(path: str) -> str:
    stem = Path(path).stem.replace("_", " ").replace("-", " ")
    words = [
        word.upper() if word.lower() in {"ee", "kt4", "pap", "brm"} else word.title()
        for word in stem.split()
    ]
    return " ".join(words)
