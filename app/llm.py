from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings


class LLMResponse(BaseModel):
    answer: str = ""
    need_clarification: bool = False
    clarification_question: str = ""
    image_ids: list[str] = Field(default_factory=list)


class LLMUnavailableError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


@dataclass(slots=True)
class LLMService:
    settings: Settings
    _client: AsyncOpenAI | None = field(init=False, repr=False, default=None)

    def __post_init__(self) -> None:
        self._client = (
            AsyncOpenAI(
                api_key=self.settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=35.0,
                max_retries=2,
            )
            if self.settings.llm_configured
            else None
        )

    async def answer(self, messages: list[dict[str, str]]) -> LLMResponse:
        if self._client is None:
            raise LLMUnavailableError(
                "GROQ_API_KEY is not configured. The knowledge base is healthy, "
                "but chat generation is unavailable."
            )

        try:
            response = await self._client.chat.completions.create(
                model=self.settings.groq_model,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
        except Exception as error:
            raise LLMResponseError(f"Model request failed: {error}") from error

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise LLMResponseError("The model returned no usable completion.") from error
        if not content:
            raise LLMResponseError("The model returned an empty response.")

        try:
            payload = json.loads(_strip_json_fence(content))
            parsed = LLMResponse.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as error:
            raise LLMResponseError(
                f"The model returned invalid structured output: {error}"
            ) from error
        if not parsed.need_clarification and not parsed.answer.strip():
            raise LLMResponseError("The model returned an empty answer.")
        if parsed.need_clarification and not parsed.clarification_question.strip():
            raise LLMResponseError("The model requested clarification without a question.")
        return parsed


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped
