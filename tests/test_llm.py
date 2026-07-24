from types import SimpleNamespace

import pytest

from app.config import Settings
from app.llm import LLMResponseError, LLMService, LLMUnavailableError


class FakeCompletions:
    def __init__(self, response: object = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    async def create(self, **_: object) -> object:
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
@pytest.mark.parametrize(
    "response",
    [
        SimpleNamespace(choices=[]),
        SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=""))]),
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
