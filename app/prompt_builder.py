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

Reply in the same language as the user. Use compact Markdown that is easy to
follow during a match. Prefer numbered steps for procedures.

Images are represented by stable IDs and captions. Select only images that
directly help the answer. For procedural or location-based questions, select
at least one image whenever image options are available, preferably one image
for each important step. Never invent an image ID.

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
) -> PromptBundle:
    context_parts: list[str] = []
    included_chunks: list[ScoredChunk] = []
    image_ids: list[str] = []
    total_chars = 0

    for scored in scored_chunks:
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
