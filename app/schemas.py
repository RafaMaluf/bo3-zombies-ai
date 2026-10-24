from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.companion_models import MatchState


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)
    source_paths: list[str] = Field(default_factory=list, max_length=20)


class GuideState(BaseModel):
    map_id: str = Field(max_length=80)
    document_path: str = Field(max_length=200)
    phase: int = Field(default=0, ge=0, le=200)
    completed_phases: list[int] = Field(default_factory=list, max_length=200)
    player_count: int | None = Field(default=None, ge=1, le=4)
    language: str | None = Field(
        default=None,
        max_length=35,
        pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$",
    )


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2_000)
    response_mode: Literal["quick", "complete"] = "quick"
    conversation_history: list[ConversationMessage] = Field(default_factory=list)
    active_map_id: str | None = None
    match_state: MatchState | None = None
    guide_state: GuideState | None = None
    guide_action: Literal["start", "complete", "overview", "full", "jump", "stop"] | None = None
    guide_phase: int | None = Field(default=None, ge=0, le=200)
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
    thumbnail_url: str
    full_url: str


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
    cover_image_url: str | None = None


class MapSwitchAction(BaseModel):
    current_map_id: str
    requested_map_id: str


class AnswerBlock(BaseModel):
    title: str = ""
    body: str
    source_ids: list[str] = Field(default_factory=list)
    images: list[RelevantImage] = Field(default_factory=list)
    available_image_count: int = 0


class GuidePhase(BaseModel):
    index: int
    title: str
    completed: bool = False


class GuideProgress(BaseModel):
    state: GuideState
    mode: Literal["overview", "phase", "full", "finished"]
    phases: list[GuidePhase]


class ChatResponse(BaseModel):
    answer: str = ""
    introduction: str = ""
    need_clarification: bool = False
    clarification_question: str = ""
    suggested_map_ids: list[str] = Field(default_factory=list)
    suggested_queries: list[str] = Field(default_factory=list)
    sources: list[SelectedSource] = Field(default_factory=list)
    relevant_images: list[RelevantImage] = Field(default_factory=list)
    active_map_id: str | None = None
    map_switch: MapSwitchAction | None = None
    blocks: list[AnswerBlock] = Field(default_factory=list)
    guide: GuideProgress | None = None
    companion_offer_map_id: str | None = None
    response_language: str | None = None
    offer_complete: bool = False


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
