from __future__ import annotations

from dataclasses import dataclass

from app.answer_policy import AnswerContract
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
Detailed means preserving the source's specifics, not adding length. Stop once
the source procedure is exhausted. Do not invent extra usage steps, menu
options, activation rules or solo/co-op equivalence. Do not append a generic
conditions/prerequisites recap; include a condition only where the source
documents it. Preserve differences between parts: a part with one fixed spawn
must never be described as having three alternative spawns just because the
other parts do. Explain each fact once, without repetitive recaps.

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
steps for procedures. Supplied excerpts may span multiple guides selected
for the objective and its documented prerequisites. Follow the RESPONSE PLAN
in execution order and answer all supplied steps. Never ask the user to choose
between source files. Expand mandatory prerequisites in DETAILED mode; in
SUMMARY explain their purpose and offer to elaborate on long procedures.
Clearly label recommendations as optional; never make them requirements.
Consecutive objectives are not automatically dependencies. Never invent a causal
connection between independent tasks just because the user requested both.

Images are attached by the server from each section's source. You do not need
to choose or describe images. Follow only the output schema supplied for this
call; never invent an image ID and never expose IDs in the visible answer. Keep proper
names, prerequisites, alternative locations and exact procedure order.
The requested ANSWER DETAIL controls completeness: compact formatting must
never become an excuse to omit instructions in a DETAILED response.
""".strip()


GENERIC_OUTPUT_PROMPT = """
Return one valid JSON object and no text outside it:
{
  "answer": "Short introduction only; do not repeat the blocks here",
  "need_clarification": false,
  "clarification_question": "",
  "image_ids": [],
  "blocks": [
    {"title": "Translated step title", "body": "Markdown instructions for this step",
     "source_ids": ["exact SOURCE id from the excerpts"]}
  ]
}

For substantive answers, use blocks in execution order. Each block must cite
the exact SOURCE id(s) supporting that block; never invent a source id. Keep
different parts or phases in separate blocks. The server attaches the entire
image group from the cited section beneath its explanation. Cite only sections
actually explained by the block, never an unrelated section to get more images.
In DETAILED mode, list every documented alternative spawn location and explain
that only one contains the part. In SUMMARY mode, name the area and mention
the alternatives briefly; the attached images remain available. Do not label
a photo as a specific spawn unless the
source explicitly establishes that mapping. Do not add upgrades or side quests
unless requested or explicitly identified as mandatory in the RESPONSE PLAN.
A concise direct answer may use a single block.
""".strip()


ORDERED_OUTPUT_PROMPT = """
Return only the OrderedAnswer JSON schema supplied for this call: answer and
sections. Do not include generic answer metadata, blocks, image_ids,
need_clarification, clarification_question or source_ids fields. The server
binds each required section to its source and attaches its images. Preserve
all required section keys, even in summaries. In DETAILED mode explain every
documented alternative spawn; in SUMMARY explain each required procedure's
objective concisely, including each mandatory procedure grouped into a section.
""".strip()


def build_answer_prompt(
    user_message: str,
    history: list[ConversationMessage],
    scored_chunks: tuple[ScoredChunk, ...],
    knowledge_base: KnowledgeBase,
    max_context_chars: int,
    max_candidate_images: int,
    response_language: str = "pt-BR",
    guide_instructions: str = "",
    answer_contract: AnswerContract | None = None,
    include_image_catalog: bool = True,
) -> PromptBundle:
    context_parts: list[str] = []
    included_chunks: list[ScoredChunk] = []
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

    images: list[ImageAsset] = []
    selected_image_ids: set[str] = set()
    for scored in included_chunks:
        group = [
            asset
            for image_id in scored.chunk.image_ids
            if image_id not in selected_image_ids
            and (asset := knowledge_base.get_image(image_id)) is not None
        ]
        if len(images) + len(group) > max_candidate_images:
            continue
        images.extend(group)
        selected_image_ids.update(asset.id for asset in group)

    image_catalog = "\n".join(
        (f"- {asset.id} | {asset.map_id} | {asset.section} | {asset.caption}") for asset in images
    )
    if not image_catalog:
        image_catalog = "(No images are available for these excerpts.)"
    if not include_image_catalog:
        image_catalog = "Images are attached by the server; no manual image selection is needed."

    user_content = "\n\n".join(
        [
            "KNOWLEDGE-BASE EXCERPTS",
            "\n\n---\n\n".join(context_parts),
            "AVAILABLE IMAGES",
            image_catalog,
            f"RESPONSE LANGUAGE\n{response_language}",
            guide_instructions,
            answer_contract.instructions() if answer_contract else "",
            f"USER QUESTION\n{user_message}",
        ]
    )

    ordered = answer_contract and answer_contract.ordered and len(answer_contract.requirements) > 1
    output_prompt = ORDERED_OUTPUT_PROMPT if ordered else GENERIC_OUTPUT_PROMPT
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT + "\n\n" + output_prompt}
    ]
    if answer_contract and answer_contract.detail == "summary":
        messages.append(
            {
                "role": "system",
                "content": (
                    "This response is a SUMMARY ROADMAP, not a detailed walkthrough. "
                    "The full source text is reference material; do not reproduce it in full. "
                    "For a single procedure, aim for 15-30 words stating its purpose and "
                    "essential conditions. A grouped prerequisite contains MULTIPLE required "
                    "procedures: use one short clause or bullet for EACH procedure, including "
                    "required upgrades. Such a group may need more than two sentences; obey "
                    "its word budget instead of omitting a procedure to fit one sentence. "
                    "Do not enumerate every spawn, generator location, puzzle interaction or "
                    "recipe here. Preserve required objectives and solo/co-op conditions. "
                    "Offer deeper explanation of long prerequisites.\n"
                    + answer_contract.instructions()
                ),
            }
        )
    for message in history:
        messages.append({"role": message.role, "content": message.content})
    messages.append({"role": "user", "content": user_content})

    return PromptBundle(
        messages=messages,
        chunks=tuple(included_chunks),
        images=tuple(images),
    )
