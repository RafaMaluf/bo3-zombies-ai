from __future__ import annotations

from dataclasses import dataclass

from app.domain import ImageAsset, ScoredChunk
from app.knowledge_base import KnowledgeBase
from app.schemas import ConversationMessage


@dataclass(frozen=True, slots=True)
class PromptBundle:
    messages: list[dict[str, str]]
    chunks: tuple[ScoredChunk, ...]
    images: tuple[ImageAsset, ...]


SYSTEM_PROMPT = """
You are Krono, a specialist assistant for Call of Duty: Black Ops III Zombies.

Answer the user's question using only the supplied knowledge-base excerpts.
Keep exact step order, prerequisites, solo/co-op differences, item names and
locations. Never invent a missing step. If the excerpts are insufficient,
say so or request one concise clarification.

The application has already resolved the response language. Write the entire
answer in the supplied response language. Do not infer a different language
from the knowledge-base excerpts or override the supplied language.

Translate all explanatory prose, headings, verbs, generic item types and
elemental variants. Never mix English grammar into a Portuguese sentence:
write "construa", "melhore", "equipe" and "cajado", never "craft", "upgrade",
"equip" or "staff".
Canonical in-game proper names such as Pack-a-Punch, G-Strike, Maxis Drone,
One Inch Punch, GobbleGum, character names and location names may remain in
their official form. Translate source headings instead of copying them
verbatim. If an original English term helps recognition, include it in
parentheses only on its first occurrence.

Use compact Markdown that is easy to follow during a match. Prefer numbered
steps for procedures. When the user explicitly requests two or three named
objectives and excerpts from multiple files are supplied, answer every
requested objective in one response, with one heading per objective. Do not
ask the user to choose between objectives they already named. Do not expand
into related guides that were not requested.

Images are represented by stable IDs and captions. Select only images that
directly help the answer. For procedural or location-based questions, select
at least one image whenever image options are available, preferably one image
for each important step. Never invent an image ID. Put IDs only in the
`image_ids` JSON field; never expose IDs or add an image list to the answer
text because the interface renders the selected images separately.

Return one valid JSON object and no text outside it:
{
  "answer": "Markdown answer",
  "need_clarification": false,
  "clarification_question": "",
  "image_ids": ["img_example"]
}
""".strip()


def build_answer_prompt(
    user_message: str,
    history: list[ConversationMessage],
    scored_chunks: tuple[ScoredChunk, ...],
    knowledge_base: KnowledgeBase,
    max_context_chars: int,
    max_candidate_images: int,
    response_language: str = "pt-BR",
) -> PromptBundle:
    context_parts: list[str] = []
    included_chunks: list[ScoredChunk] = []
    image_ids: list[str] = []
    total_chars = 0

    document_keys = {(item.chunk.map_id, item.chunk.path) for item in scored_chunks}
    ordered_chunks = scored_chunks
    if len(document_keys) == 1:
        ordered_chunks = tuple(sorted(scored_chunks, key=lambda item: item.chunk.position))

    for scored in ordered_chunks:
        chunk = scored.chunk
        context_part = "\n".join(
            [
                f"[SOURCE {chunk.id}]",
                f"MAP: {chunk.map_name} ({chunk.map_id})",
                f"FILE: {chunk.path}",
                f"SECTION: {chunk.section_title}",
                f"CATEGORY: {chunk.category}",
                "",
                chunk.content,
            ]
        ).strip()

        if context_parts and total_chars + len(context_part) > max_context_chars:
            break
        if not context_parts and len(context_part) > max_context_chars:
            context_part = context_part[:max_context_chars].rstrip() + "\n[TRUNCATED]"

        context_parts.append(context_part)
        included_chunks.append(scored)
        total_chars += len(context_part)
        for image_id in chunk.image_ids:
            if image_id not in image_ids:
                image_ids.append(image_id)

    images: list[ImageAsset] = []
    for image_id in image_ids[:max_candidate_images]:
        asset = knowledge_base.get_image(image_id)
        if asset is not None:
            images.append(asset)

    image_catalog = "\n".join(
        (f"- {asset.id} | {asset.map_id} | {asset.section} | {asset.caption}") for asset in images
    )
    if not image_catalog:
        image_catalog = "(No images are available for these excerpts.)"

    user_content = "\n\n".join(
        [
            "KNOWLEDGE-BASE EXCERPTS",
            "\n\n---\n\n".join(context_parts),
            "AVAILABLE IMAGES",
            image_catalog,
            f"RESPONSE LANGUAGE\n{response_language}",
            f"USER QUESTION\n{user_message}",
        ]
    )

    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for message in history:
        messages.append({"role": message.role, "content": message.content})
    messages.append({"role": "user", "content": user_content})

    return PromptBundle(
        messages=messages,
        chunks=tuple(included_chunks),
        images=tuple(images),
    )
