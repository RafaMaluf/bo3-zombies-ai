import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pathlib import Path
from fastapi.staticfiles import StaticFiles

from app.config import GROQ_API_KEY, GROQ_MODEL, MAX_SELECTED_FILES
from app.kb_loader import build_catalog_for_selection, load_all_map_indexes, read_selected_files
from app.prompt_builder import build_answer_messages, build_selection_messages
from app.schemas import ChatRequest, ChatResponse, FinalAnswerResponse, SelectionResponse

app = FastAPI(title="Zombies AI Backend", version="0.1.0")

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
MAPS_DIR = BASE_DIR / "maps"

app.mount("/static", StaticFiles(directory=MAPS_DIR), name="static")
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    indexes = load_all_map_indexes()
    if not indexes:
        raise HTTPException(status_code=500, detail="No map indexes found")

    catalog_text = build_catalog_for_selection(indexes)

    # Step 1: selection
    selection_messages = build_selection_messages(
        user_message=req.message,
        catalog_text=catalog_text,
        conversation_history=req.conversation_history,
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
        )

    selected_files = selection.selected_files[:MAX_SELECTED_FILES]
    if not selected_files:
        return ChatResponse(
            answer="",
            need_clarification=True,
            clarification_question="Which map or topic do you mean?",
            selected_files=[],
            relevant_images=[],
        )

    # Step 2: read selected files
    combined_context, used_images = read_selected_files(indexes, selected_files)

    if not combined_context.strip():
        raise HTTPException(status_code=500, detail="Selected files could not be loaded")

    # Step 3: answer
    answer_messages = build_answer_messages(
        user_message=req.message,
        combined_context=combined_context,
        selected_files=selected_files,
        available_images=used_images,
        conversation_history=req.conversation_history,
    )

    try:
        answer_json = call_groq_json(answer_messages)
        final_answer = FinalAnswerResponse(**answer_json)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Answer step failed: {e}")

    return ChatResponse(
        answer=final_answer.answer,
        need_clarification=final_answer.need_clarification,
        clarification_question=final_answer.clarification_question,
        selected_files=selected_files,
        relevant_images=final_answer.relevant_images,
    )