from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.schemas import RateLimitUsage


class LLMResponse(BaseModel):
    answer: str = ""
    need_clarification: bool = False
    clarification_question: str = ""
    image_ids: list[str] = Field(default_factory=list)
    usage: RateLimitUsage | None = Field(default=None, exclude=True)


class QueryResolution(BaseModel):
    resolved_query: str = ""
    need_clarification: bool = False
    clarification_question: str = ""
    candidate_document_paths: list[str] = Field(default_factory=list)
    usage: RateLimitUsage | None = Field(default=None, exclude=True)


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
        payload, usage = await self._json_completion(messages)
        try:
            parsed = LLMResponse.model_validate(payload)
        except ValidationError as error:
            raise LLMResponseError(
                f"The model returned invalid structured output: {error}"
            ) from error
        parsed.usage = usage
        if not parsed.need_clarification and not parsed.answer.strip():
            raise LLMResponseError("The model returned an empty answer.")
        if parsed.need_clarification and not parsed.clarification_question.strip():
            raise LLMResponseError("The model requested clarification without a question.")
        return parsed

    async def resolve_query(
        self,
        messages: list[dict[str, str]],
    ) -> QueryResolution:
        payload, usage = await self._json_completion(messages)
        try:
            parsed = QueryResolution.model_validate(payload)
        except ValidationError as error:
            raise LLMResponseError(
                f"The model returned invalid query resolution: {error}"
            ) from error
        parsed.usage = usage
        if parsed.need_clarification and not parsed.clarification_question.strip():
            raise LLMResponseError("Query resolution requested an empty clarification.")
        if not parsed.need_clarification and not parsed.resolved_query.strip():
            raise LLMResponseError("Query resolution returned no query.")
        return parsed

    async def _json_completion(
        self,
        messages: list[dict[str, str]],
    ) -> tuple[dict[str, object], RateLimitUsage | None]:
        if self._client is None:
            raise LLMUnavailableError(
                "GROQ_API_KEY is not configured. The knowledge base is healthy, "
                "but chat generation is unavailable."
            )

        try:
            request_options: dict[str, object] = {
                "model": self.settings.groq_model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }
            if self.settings.groq_model.startswith("openai/gpt-oss"):
                request_options["reasoning_effort"] = "low"
            raw_response = await self._client.chat.completions.with_raw_response.create(
                **request_options,
            )
        except Exception as error:
            raise LLMResponseError(f"Model request failed: {error}") from error

        usage = _extract_rate_limit_usage(raw_response.headers)
        response = raw_response.parse()

        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise LLMResponseError("The model returned no usable completion.") from error
        if not content:
            raise LLMResponseError("The model returned an empty response.")

        try:
            payload = json.loads(_strip_json_fence(content))
        except json.JSONDecodeError as error:
            raise LLMResponseError(
                f"The model returned invalid structured output: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise LLMResponseError("The model returned a non-object JSON value.")
        return payload, usage


def _header_int(headers, name: str) -> int | None:
    value = headers.get(name)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _extract_rate_limit_usage(headers) -> RateLimitUsage | None:
    usage = RateLimitUsage(
        remaining_tokens=_header_int(headers, "x-ratelimit-remaining-tokens"),
        token_limit=_header_int(headers, "x-ratelimit-limit-tokens"),
        remaining_requests=_header_int(headers, "x-ratelimit-remaining-requests"),
        request_limit=_header_int(headers, "x-ratelimit-limit-requests"),
        tokens_reset_in=headers.get("x-ratelimit-reset-tokens"),
        requests_reset_in=headers.get("x-ratelimit-reset-requests"),
    )
    return usage if any(value is not None for value in usage.model_dump().values()) else None


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped
