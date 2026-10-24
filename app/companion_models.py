"""Typed match state, independent from generated text and chat history."""

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProgressChange(StrictModel):
    completed: list[str] = Field(default_factory=list, max_length=160)
    pending: list[str] = Field(default_factory=list, max_length=160)
    focus: str | None = None
    from_start: bool = False
    player_count: int | None = Field(default=None, ge=1, le=4)
    applicability: dict[str, bool] = Field(default_factory=dict)
    partial: dict[str, str] = Field(default_factory=dict)
    evidence: str = Field(default="", max_length=2000)
    clarification: str = Field(default="", max_length=1000)
    intent: Literal["progress", "question", "consult", "help", "unclear", "status"] = "question"
    reply: str = Field(default="", max_length=6000)


class MatchState(StrictModel):
    version: Literal[1] = 1
    session_id: str = Field(default_factory=lambda: uuid4().hex, max_length=64)
    map_id: str = Field(max_length=80)
    catalog_version: str = Field(max_length=64)
    revision: int = Field(default=0, ge=0)
    player_count: int | None = Field(default=None, ge=1, le=4)
    language: str = Field(default="pt-BR", max_length=35)
    stage: Literal["position", "active", "finished"] = "position"
    statuses: dict[str, Literal["unknown", "pending", "complete"]] = Field(default_factory=dict)
    applicability: dict[str, bool] = Field(default_factory=dict)
    partial: dict[str, str] = Field(default_factory=dict)
    focus: str | None = None
    return_to: list[str] = Field(default_factory=list, max_length=12)
    confirmation: ProgressChange | None = None


class Objective(StrictModel):
    id: str
    title: str
    source_ids: list[str]
    requires: list[str] = Field(default_factory=list)
    implies: list[str] = Field(default_factory=list)
    condition: str = ""
    main: bool = False
    optional: bool = False
    number: int | None = None


class CompanionCatalog(StrictModel):
    map_id: str
    map_name: str
    document_path: str
    version: str
    objectives: list[Objective]


class CompanionRequest(StrictModel):
    state: MatchState
    action: Literal["message", "complete", "confirm", "decline", "resume", "explain", "consult"] = (
        "message"
    )
    message: str = Field(default="", max_length=2000)
    objective_id: str | None = None


class CompanionStart(StrictModel):
    map_id: str = Field(max_length=80)
    player_count: int | None = Field(default=None, ge=1, le=4)
    language: str = Field(default="pt-BR", max_length=35)


class CompanionExplanation(StrictModel):
    state: MatchState
    message: str = Field(default="", max_length=2000)
    deeper: bool = False
    question: bool = False


class CompanionView(StrictModel):
    state: MatchState
    catalog: CompanionCatalog
    message: str = ""
    needs_confirmation: bool = False
    can_explain: bool = False
    completed_count: int = 0
    total_count: int = 0
    question_mode: bool = False
