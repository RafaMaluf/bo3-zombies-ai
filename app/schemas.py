from typing import List, Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    conversation_history: Optional[List[dict]] = None


class SelectedFile(BaseModel):
    map_id: str
    path: str


class SelectionResponse(BaseModel):
    need_clarification: bool
    clarification_question: str = ""
    query_mode: str  # single_map or multi_map
    selected_files: List[SelectedFile] = []


class FinalAnswerResponse(BaseModel):
    answer: str
    need_clarification: bool = False
    clarification_question: str = ""
    relevant_images: List[str] = []


class ChatResponse(BaseModel):
    answer: str
    need_clarification: bool = False
    clarification_question: str = ""
    selected_files: List[SelectedFile] = []
    relevant_images: List[str] = []