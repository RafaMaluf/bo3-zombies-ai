from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)
    source_paths: list[str] = Field(default_factory=list, max_length=20)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    active_map_id: str | None = None
    preferred_language: str = Field(
        default="pt-BR",
        min_length=2,
        max_length=35,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$",
    )


class SelectedSource(BaseModel):
    chunk_id: str
    map_id: str
    map_name: str
    path: str
    section: str
    score: float


class RelevantImage(BaseModel):
    id: str
    map_id: str
    path: str
    caption: str
    section: str


class MapSummary(BaseModel):
    map_id: str
    display_name: str
    release_order: int | None = None
    summary: str
    aliases: list[str]
    document_count: int
    chunk_count: int
    image_count: int
    cover_image_id: str | None = None


class ChatResponse(BaseModel):
    answer: str = ""
    need_clarification: bool = False
    clarification_question: str = ""
    suggested_map_ids: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    sources: list[SelectedSource] = Field(default_factory=list)
    relevant_images: list[RelevantImage] = Field(default_factory=list)
    active_map_id: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    llm_configured: bool
    embeddings_configured: bool = False
    embeddings_ready: bool = False
    embedding_model: str | None = None
    maps: int
    documents: int
    chunks: int
    images: int
    validation_errors: int
    validation_warnings: int
