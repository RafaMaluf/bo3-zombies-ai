from typing import List, Dict

from app.config import MAPS_DIR


def build_selection_messages(
    user_message: str,
    catalog_text: str,
    conversation_history: list[dict],
    active_map_id: str | None,
) -> list[dict]:
    """
    Build messages for the selection step.
    Includes the actual index.json structure so model knows real file names.
    """
    
    # Constrói o index com nomes e descrições reais
    file_index = _build_file_index()
    
    system_prompt = f"""
You are a routing assistant for a Black Ops 3 Zombies knowledge base.

Your job is ONLY to choose which map files are relevant to answer the user's question.

Rules:
- Use only files listed in the FILE INDEX below.
- Do NOT invent or hallucinate file names.
- Select only files that exist in the index.
- If the request is ambiguous, ask ONE short clarification question.
- If the request is about one specific map, use query_mode = "single_map".
- If the request compares multiple maps, use query_mode = "multi_map".
- Prefer specific files over general.md when user mentions concrete items.
- Use general.md only for broad map overview questions.
- If active_map_id exists and message is a follow-up, prefer staying on that map.
- **CRITICAL: Only select files that exist in the FILE INDEX. Match by exact path name.**
- **IMPORTANT: The "path" field must be ONLY the filename (e.g., "general.md"), NOT including map_id.**

FILE INDEX (all available files):
{file_index}

JSON format:
{{
  "need_clarification": true/false,
  "clarification_question": "",
  "query_mode": "single_map" or "multi_map",
  "selected_files": [
    {{"map_id": "der_eisendrache", "path": "general.md"}}
  ]
}}
""".strip()

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        messages.extend(conversation_history)

    user_content = f"""Active map id:
{active_map_id or 'None'}

Conversation history:
{len(conversation_history)} messages

Catalog:
{catalog_text}

User query: {user_message}"""

    messages.append({"role": "user", "content": user_content})

    return messages


def _build_file_index() -> str:
    """Build index with actual filenames and descriptions from index.json files."""
    import json
    
    lines = []
    
    for map_dir in sorted(MAPS_DIR.iterdir()):
        if not map_dir.is_dir():
            continue
        
        index_file = map_dir / "index.json"
        if not index_file.exists():
            continue
        
        with index_file.open("r", encoding="utf-8") as f:
            index_data = json.load(f)
        
        map_id = index_data.get("map_id")
        display_name = index_data.get("display_name", map_id)
        
        lines.append(f"\n{display_name} ({map_id}):")
        
        # Usa a lista de arquivos do index.json
        for file_info in index_data.get("files", []):
            path = file_info.get("path")
            summary = file_info.get("summary", "")
            lines.append(f"  - {path}: {summary}")
    
    return "\n".join(lines)


def build_answer_messages(
    user_message: str,
    combined_context: str,
    selected_files: List,
    available_images: List,
    conversation_history: list[dict],
) -> list[dict]:
    """
    Build messages for the answer generation step.
    """
    system_prompt = """
You are a helpful Black Ops 3 Zombies expert assistant.

Your job is to answer the user's question based on the provided context.

Rules:
- Answer based ONLY on the provided context.
- If the answer is not in the context, say so.
- Be concise but thorough.
- If relevant images are available, mention them in your answer.
- Format your response as JSON with fields: answer, need_clarification, clarification_question, relevant_images.
- Return ONLY valid JSON, no explanations outside JSON.

JSON format:
{
  "answer": "Your detailed answer here",
  "need_clarification": false,
  "clarification_question": "",
  "relevant_images": []
}
""".strip()

    messages = [{"role": "system", "content": system_prompt}]

    if conversation_history:
        messages.extend(conversation_history)

    selected_files_str = "\n".join(
        [f"- {sf.map_id}/{sf.path}" for sf in selected_files]
    )
    available_images_str = "\n".join(
        [f"- {img.map_id}/{img.path}" for img in available_images]
    )

    user_content = f"""Context from selected files:
{selected_files_str}

Available images:
{available_images_str}

Knowledge base content:
{combined_context}

---

User question: {user_message}"""

    messages.append({"role": "user", "content": user_content})

    return messages