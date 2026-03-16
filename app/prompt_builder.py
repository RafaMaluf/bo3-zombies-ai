import json
from typing import List, Optional

from app.schemas import SelectedFile, RelevantImage


def build_selection_messages(
    user_message: str,
    catalog_text: str,
    conversation_history: Optional[List[dict]] = None,
    active_map_id: Optional[str] = None,
) -> list[dict]:
    history_text = ""
    if conversation_history:
        trimmed = conversation_history[-6:]
        history_text = json.dumps(trimmed, ensure_ascii=False, indent=2)

    active_map_text = active_map_id if active_map_id else "None"

    system_prompt = """
You are a routing assistant for a Black Ops 3 Zombies knowledge base.

Your job is ONLY to choose which map files are relevant to answer the user's question.

Rules:
- Use only the provided catalog.
- If the request is ambiguous, ask ONE short clarification question.
- If the request is about one specific map, use query_mode = "single_map".
- If the request compares multiple maps or asks a general BO3 Zombies question, use query_mode = "multi_map".
- Select only relevant files.
- Do not select unnecessary files.
- Prefer specific files over general.md whenever the user mentions a concrete item, step, or mechanic.
- If the user asks about something that does not clearly exist in the catalog, do not guess.
- If the term is not clearly present in the file summaries or map summaries, ask for clarification.
- Do not reinterpret slang or vague words as game mechanics unless strongly supported by the catalog.
- Use general.md only for broad map overview questions.
- If there is an active_map_id and the new user message is short, vague, or an obvious follow-up, prefer staying on that same map.
- Only switch away from the active_map_id if the user explicitly mentions another map or clearly asks a multi-map question.
- Return JSON only.
- Never include explanations outside JSON.

JSON format:
{
  "need_clarification": true/false,
  "clarification_question": "",
  "query_mode": "single_map" or "multi_map",
  "selected_files": [
    {"map_id": "...", "path": "..."}
  ]
}
""".strip()

    user_prompt = f"""
Active map id:
{active_map_text}

Conversation history:
{history_text if history_text else "[]"}

Catalog:
{catalog_text}

User question:
{user_message}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_answer_messages(
    user_message: str,
    combined_context: str,
    selected_files: List[SelectedFile],
    available_images: List[RelevantImage],
    conversation_history: Optional[List[dict]] = None,
) -> list[dict]:
    history_text = ""
    if conversation_history:
        trimmed = conversation_history[-6:]
        history_text = json.dumps(trimmed, ensure_ascii=False, indent=2)

    selected_text = json.dumps(
        [{"map_id": sf.map_id, "path": sf.path} for sf in selected_files],
        ensure_ascii=False,
        indent=2,
    )

    available_images_text = json.dumps(
        [{"map_id": img.map_id, "path": img.path} for img in available_images],
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = """
You are a Black Ops 3 Zombies assistant.

Rules:
- Answer ONLY using the provided knowledge base context.
- If the provided context is insufficient, set need_clarification=true and ask one short clarification question.
- Do not invent steps, locations, mechanics, mappings, or values.
- If a user term is not explicitly supported by the context, do not map it to a similar reward or mechanic.
- If the term is unclear, ask a clarification question instead of guessing.
- Prefer direct, practical answers.
- Select only the images that are directly useful for the answer.
- For step-by-step and location-based questions, prefer returning 1 to 4 relevant images instead of none.
- For broad summary questions, you may return no images if they are not necessary.
- Return image objects exactly as they appear in the available images list.
- If no images are needed, return an empty relevant_images list.
- Return JSON only.

Special rule for Gorod Krovi valve-step questions:
- Use only the fixed lookup table present in the provided context.
- Never solve the valve puzzle from memory or by inference.
- Treat "Tank Station" and "Tank Factory" as the same location.
- The codex / cylinder valve is always the END POINT.
- Never assign a number to the codex / cylinder valve.
- Return only the valves that must be set, plus the end point.
- If the context says the start and end are the same location, say that this setup is invalid.

If the user asks for a lookup-style answer such as a Gorod Krovi valve combination:
- reproduce the mapping exactly from context
- do not add extra valve values
- do not rewrite the endpoint as a configurable valve

JSON format:
{
  "answer": "text here",
  "need_clarification": true/false,
  "clarification_question": "",
  "relevant_images": [
    {"map_id": "...", "path": "images/..."}
  ]
}
""".strip()

    user_prompt = f"""
Conversation history:
{history_text if history_text else "[]"}

Selected files:
{selected_text}

Knowledge base context:
{combined_context}

Available related images:
{available_images_text}

User question:
{user_message}
""".strip()

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]