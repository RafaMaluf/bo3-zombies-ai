import json
from typing import List, Optional

from app.schemas import SelectedFile


def build_selection_messages(user_message: str, catalog_text: str, conversation_history: Optional[List[dict]] = None) -> list[dict]:
    history_text = ""
    if conversation_history:
        trimmed = conversation_history[-6:]
        history_text = json.dumps(trimmed, ensure_ascii=False, indent=2)

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
- If the user mentions a named item, badge, book, pen, wig, belt, sword, shield, fuse, pod, or wonder weapon part, strongly prefer the file whose summary explicitly mentions that item.
- Use general.md only for broad map overview questions.
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
    available_images: List[str],
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

    available_images_text = json.dumps(available_images, ensure_ascii=False, indent=2)

    system_prompt = """
You are a Black Ops 3 Zombies assistant.

Rules:
- Answer ONLY using the provided knowledge base context.
- If the provided context is insufficient, set need_clarification=true and ask one short clarification question.
- Do not invent steps, locations, or mechanics.
- Prefer direct, practical answers.
- Select only the images that are directly useful for the answer.
- Return image paths exactly as written in the available images list.
- If no images are needed, return an empty relevant_images list.
- Return JSON only.

JSON format:
{
  "answer": "text here",
  "need_clarification": true/false,
  "clarification_question": "",
  "relevant_images": ["images/..."]
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