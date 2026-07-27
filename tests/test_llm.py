from types import SimpleNamespace

import pytest

from app.config import Settings
from app.llm import LLMResponseError, LLMService, LLMUnavailableError


class FakeCompletions:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.last_kwargs: dict[str, object] = {}

    async def create(self, **kwargs: object) -> object:
        self.last_kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


def _service_with_response(response: object) -> LLMService:
    service = LLMService(Settings(groq_api_key="test"))
    service._client = SimpleNamespace(
        chat=SimpleNamespace(completions=FakeCompletions(response=response))
    )
    return service


@pytest.mark.asyncio
async def test_missing_api_key_fails_cleanly() -> None:
    service = LLMService(Settings(groq_api_key=""))

    with pytest.raises(LLMUnavailableError):
        await service.answer([{"role": "user", "content": "test"}])


@pytest.mark.asyncio
async def test_json_fence_is_accepted() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '```json\n{"answer":"Ready","need_clarification":false,"image_ids":[]}\n```'
                    )
                )
            )
        ]
    )

    result = await _service_with_response(response).answer([{"role": "user", "content": "test"}])

    assert result.answer == "Ready"


@pytest.mark.asyncio
async def test_gpt_oss_uses_low_reasoning_effort() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content='{"answer":"Pronto","need_clarification":false,"image_ids":[]}'
                )
            )
        ]
    )
    completions = FakeCompletions(response=response)
    service = LLMService(
        Settings(groq_api_key="test", groq_model="openai/gpt-oss-120b")
    )
    service._client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )

    await service.answer([{"role": "user", "content": "teste"}])

    assert completions.last_kwargs["reasoning_effort"] == "low"


@pytest.mark.asyncio
async def test_query_resolution_is_validated() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '{"resolved_query":"","need_clarification":true,'
                        '"clarification_question":"Qual deles?",'
                        '"candidate_document_paths":["fire_bow.md","wolf_bow.md"]}'
                    )
                )
            )
        ]
    )

    result = await _service_with_response(response).resolve_query(
        [{"role": "user", "content": "e os outros?"}]
    )

    assert result.need_clarification
    assert result.candidate_document_paths == ["fire_bow.md", "wolf_bow.md"]


@pytest.mark.asyncio
async def test_query_resolution_requires_query_or_clarification() -> None:
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '{"resolved_query":"","need_clarification":false,'
                        '"clarification_question":"","candidate_document_paths":[]}'
                    )
                )
            )
        ]
    )

    with pytest.raises(LLMResponseError, match="no query"):
        await _service_with_response(response).resolve_query(
            [{"role": "user", "content": "e ele?"}]
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(choices=[]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="[]"))]),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"answer":"","need_clarification":false,"image_ids":[]}'
                    )
                )
            ]
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=(
                            '{"answer":"","need_clarification":true,'
                            '"clarification_question":"","image_ids":[]}'
                        )
                    )
                )
            ]
        ),
    ],
)
async def test_malformed_or_empty_completions_fail_cleanly(response: object) -> None:
    with pytest.raises(LLMResponseError):
        await _service_with_response(response).answer([{"role": "user", "content": "test"}])
