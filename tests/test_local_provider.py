import json
from types import SimpleNamespace

import httpx
import pytest
from openai import RateLimitError

from app.config import Settings
from app.llm import LLMService, LLMUnavailableError
from tests.test_llm_contract import GOOD, MESSAGES, ScriptedCompletions, completion


def config(**kwargs):
    return Settings(
        **{
            "groq_api_key": "fake-free-key",
            "openrouter_api_key": "fake-paid-secret",
            "app_env": "development",
            "local_openrouter_enabled": True,
            "local_llm_provider": "groq",
            **kwargs,
        }
    )


def client(scripted):
    return SimpleNamespace(chat=SimpleNamespace(completions=scripted))


@pytest.mark.parametrize("environment", ["production", "staging", "", "Development"])
def test_paid_key_cannot_enable_openrouter_outside_explicit_development(environment):
    settings = config(app_env=environment, local_llm_provider="openrouter")
    llm = LLMService(settings)
    assert not settings.paid_local_enabled
    assert settings.llm_provider == "groq"
    assert llm._paid_client is None
    assert "fake-paid-secret" not in repr(settings)


def test_paid_access_requires_key_and_opt_in():
    assert not config(local_openrouter_enabled=False).paid_local_enabled
    assert not config(openrouter_api_key="").paid_local_enabled
    assert not config(groq_api_key="", app_env="production").llm_configured


@pytest.mark.asyncio
async def test_local_paid_request_preserves_schema_and_price_cap_and_logs_only_usage(tmp_path):
    llm = LLMService(config(local_llm_provider="openrouter", cache_dir=tmp_path))
    response = completion(GOOD)
    response.usage = SimpleNamespace(prompt_tokens=123, completion_tokens=45, cost=0.00001)
    scripted = ScriptedCompletions(response)
    llm._client = client(scripted)
    await llm.answer(MESSAGES)
    options = scripted.calls[0]
    assert options["model"] == "openai/gpt-oss-120b"
    assert options["response_format"]["json_schema"]["strict"]
    provider = options["extra_body"]["provider"]
    assert provider["require_parameters"]
    assert provider["only"] == ["deepinfra/bf16", "crusoe/bf16"]
    assert options["extra_body"]["reasoning"] == {"effort": "low"}
    assert "reasoning_effort" not in options
    assert provider["max_price"] == {"prompt": 0.06, "completion": 0.25}
    record_text = (tmp_path / "llm-usage.jsonl").read_text()
    record = json.loads(record_text)
    assert record["cost_usd"] == 0.00001
    assert record["prompt_tokens"] == 123
    assert "fake-paid-secret" not in record_text
    assert MESSAGES[0]["content"] not in record_text


@pytest.mark.asyncio
async def test_only_local_groq_quota_exhaustion_can_fall_back_to_paid():
    llm = LLMService(config())
    error = RateLimitError(
        "tokens per day",
        response=httpx.Response(
            429, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        ),
        body={},
    )
    free = ScriptedCompletions(error)
    paid = ScriptedCompletions(completion(GOOD))
    llm._client, llm._paid_client = client(free), client(paid)
    await llm.answer(MESSAGES)
    assert len(free.calls) == len(paid.calls) == 1
    assert "extra_body" not in free.calls[0]
    assert "extra_body" in paid.calls[0]


@pytest.mark.asyncio
async def test_local_fallback_skips_free_provider_during_cooldown_then_recovers():
    llm = LLMService(config())
    assert llm._client.max_retries == 0
    error = RateLimitError(
        "minute quota",
        response=httpx.Response(
            429,
            headers={"retry-after": "120"},
            request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"),
        ),
        body={},
    )
    free = ScriptedCompletions(error, completion(GOOD))
    paid = ScriptedCompletions(completion(GOOD))
    llm._client, llm._paid_client = client(free), client(paid)
    await llm.answer(MESSAGES)
    await llm.answer(MESSAGES)
    assert len(free.calls) == 1
    assert len(paid.calls) == 2
    llm._free_retry_after = 0
    await llm.answer(MESSAGES)
    assert len(free.calls) == 2
    assert len(paid.calls) == 2


@pytest.mark.asyncio
async def test_production_rate_limit_returns_without_paid_call_or_cooldown():
    llm = LLMService(config(app_env="production"))
    error = RateLimitError(
        "tokens per day",
        response=httpx.Response(
            429, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        ),
        body={},
    )
    free = ScriptedCompletions(error)
    llm._client = client(free)
    with pytest.raises(LLMUnavailableError, match="amanhã"):
        await llm.answer(MESSAGES)
    assert len(free.calls) == 1
    assert llm._paid_client is None
    assert llm._free_retry_after == 0


@pytest.mark.asyncio
async def test_paid_quota_error_does_not_claim_free_daily_limit():
    llm = LLMService(config(local_llm_provider="openrouter"))
    error = RateLimitError(
        "daily",
        response=httpx.Response(
            429, request=httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
        ),
        body={},
    )
    scripted = ScriptedCompletions(error)
    llm._client = client(scripted)
    with pytest.raises(LLMUnavailableError, match="OpenRouter") as caught:
        await llm.answer(MESSAGES)
    assert "amanhã" not in str(caught.value)
    assert len(scripted.calls) == 1
