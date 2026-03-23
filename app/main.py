import json
import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI

from app.config import GROQ_API_KEY, GROQ_MODEL, MAX_SELECTED_FILES, MAX_TOTAL_CONTEXT_CHARS
from app.kb_loader import build_catalog_for_selection, load_all_map_indexes, get_file_info
from app.prompt_builder import build_answer_messages, build_selection_messages
from app.schemas import (
    ChatRequest,
    ChatResponse,
    FinalAnswerResponse,
    RelevantImage,
    SelectionResponse,
)

app = FastAPI(title="Zombies AI Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if not GROQ_API_KEY:
    raise RuntimeError("Missing GROQ_API_KEY in environment")

client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1",
)


def call_groq_json(messages: list[dict]) -> dict[str, Any]:
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("Empty JSON response from model")

    return json.loads(content)


def extract_image_paths(content: str) -> list[str]:
    paths: list[str] = []

    pattern_related = re.findall(r"Related image:\s*([^\s]+)", content)
    paths.extend(pattern_related)

    pattern_list = re.findall(r"^\-\s+(images/[^\s]+)$", content, flags=re.MULTILINE)
    paths.extend(pattern_list)

    deduped = []
    seen = set()
    for p in paths:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def read_selected_files(indexes: dict, selected_files: list) -> tuple[str, list[RelevantImage]]:
    chunks: list[str] = []
    available_images: list[RelevantImage] = []
    total_chars = 0

    for sf in selected_files:
        info = get_file_info(indexes, sf.map_id, sf.path)
        if info is None:
            continue

        # Usar chunks pré-computados em vez de ler arquivo
        file_chunks = info.get("chunks", [])
        if not file_chunks:
            continue

        for file_chunk in file_chunks:
            # Extrai imagens de cada chunk
            image_paths = extract_image_paths(file_chunk["content"])
            for img_path in image_paths:
                available_images.append(RelevantImage(map_id=sf.map_id, path=img_path))

            # Monta o contexto com metadados do chunk
            chunk = (
                f"MAP: {sf.map_id}\n"
                f"FILE: {sf.path}\n"
                f"SECTION: {file_chunk['section_title']}\n"
                f"CATEGORY: {info.get('category', 'unknown')}\n\n"
                f"{file_chunk['content']}\n"
            )

            if total_chars + len(chunk) > MAX_TOTAL_CONTEXT_CHARS:
                break

            chunks.append(chunk)
            total_chars += len(chunk)

        if total_chars >= MAX_TOTAL_CONTEXT_CHARS:
            break

    return "\n\n---\n\n".join(chunks), dedupe_images(available_images)


def dedupe_images(images: list[RelevantImage]) -> list[RelevantImage]:
    seen = set()
    deduped = []
    for img in images:
        key = (img.map_id, img.path)
        if key not in seen:
            seen.add(key)
            deduped.append(img)
    return deduped


def infer_active_map_id(selected_files: list) -> str | None:
    if not selected_files:
        return None

    unique_maps = {sf.map_id for sf in selected_files}
    if len(unique_maps) == 1:
        return selected_files[0].map_id

    return None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    indexes = load_all_map_indexes()
    if not indexes:
        raise HTTPException(status_code=500, detail="No map indexes found")

    catalog_text = build_catalog_for_selection(indexes)

    selection_messages = build_selection_messages(
        user_message=req.message,
        catalog_text=catalog_text,
        conversation_history=req.conversation_history,
        active_map_id=req.active_map_id,
    )

    try:
        selection_json = call_groq_json(selection_messages)
        selection = SelectionResponse(**selection_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Selection step failed: {e}")

    if selection.need_clarification:
        return ChatResponse(
            answer="",
            need_clarification=True,
            clarification_question=selection.clarification_question,
            selected_files=[],
            relevant_images=[],
            active_map_id=req.active_map_id,
        )

    selected_files = selection.selected_files[:MAX_SELECTED_FILES]
    if not selected_files:
        return ChatResponse(
            answer="",
            need_clarification=True,
            clarification_question="Which map or topic do you mean?",
            selected_files=[],
            relevant_images=[],
            active_map_id=req.active_map_id,
        )

    combined_context, available_images = read_selected_files(indexes, selected_files)

    if not combined_context.strip():
        raise HTTPException(status_code=500, detail="Selected files could not be loaded")

    answer_messages = build_answer_messages(
        user_message=req.message,
        combined_context=combined_context,
        selected_files=selected_files,
        available_images=available_images,
        conversation_history=req.conversation_history,
    )

    try:
        answer_json = call_groq_json(answer_messages)
        final_answer = FinalAnswerResponse(**answer_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer step failed: {e}")

    new_active_map_id = infer_active_map_id(selected_files) or req.active_map_id

    return ChatResponse(
        answer=final_answer.answer,
        need_clarification=final_answer.need_clarification,
        clarification_question=final_answer.clarification_question,
        selected_files=selected_files,
        relevant_images=final_answer.relevant_images,
        active_map_id=new_active_map_id,
    )


BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
MAPS_DIR = BASE_DIR / "maps"

app.mount("/static", StaticFiles(directory=MAPS_DIR), name="static")
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")