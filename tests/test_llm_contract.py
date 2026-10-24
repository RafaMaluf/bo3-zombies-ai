import json
from types import SimpleNamespace

import httpx
import pytest
from openai import AuthenticationError, BadRequestError, RateLimitError

from app.answer_policy import AnswerContract, SourceRequirement
from app.config import Settings
from app.domain import KnowledgeChunk
from app.llm import LLMResponse, LLMResponseError, LLMService, LLMUnavailableError, response_schema
from app.source_planning import PlanningContext


def completion(payload, finish_reason="stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=payload if isinstance(payload, str) else json.dumps(payload)
                ),
                finish_reason=finish_reason,
            )
        ]
    )


class ScriptedCompletions:
    def __init__(self, *responses):
        self.responses = responses
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        value = self.responses[min(len(self.calls) - 1, len(self.responses) - 1)]
        if isinstance(value, Exception):
            raise value
        return value


def service(*responses, model="openai/gpt-oss-120b"):
    llm = LLMService(Settings(groq_api_key="test", groq_model=model))
    scripted = ScriptedCompletions(*responses)
    llm._client = SimpleNamespace(chat=SimpleNamespace(completions=scripted))
    return llm, scripted


CONTRACT = AnswerContract(
    "detailed", ("guide:part-1",), (SourceRequirement("guide:part-1", 8, 0),), ordered=True
)
GOOD = {
    "answer": "",
    "need_clarification": False,
    "clarification_question": "",
    "image_ids": [],
    "blocks": [
        {
            "title": "Peça",
            "body": "Procure a peça junto à escada e depois monte o equipamento na bancada.",
            "source_ids": ["guide:part-1"],
        }
    ],
}
MESSAGES = [{"role": "user", "content": "Explique esta fase usando os trechos fornecidos."}]


@pytest.mark.asyncio
async def test_summary_over_word_target_does_not_retry_or_fail_valid_json():
    contract = AnswerContract(
        "summary", ("guide:part-1",),
        (SourceRequirement("guide:part-1", 3, 0, maximum_words=10),), ordered=True,
    )
    llm, scripted = service(completion(GOOD))
    result = await llm.answer(MESSAGES, contract=contract)
    assert result.blocks[0].body == GOOD["blocks"][0]["body"]
    assert len(scripted.calls) == 1


@pytest.mark.asyncio
async def test_ordered_batch_requires_each_section_and_server_binds_source_order():
    contract = AnswerContract(
        "detailed",
        ("a", "b"),
        (
            SourceRequirement("a", 3, 0),
            SourceRequirement("b", 3, 0),
        ),
        ordered=True,
    )
    payload = {
        "answer": "",
        "sections": {
            "s1": {"title": "Segundo", "body": "Monte o equipamento na bancada."},
            "s0": {"title": "Primeiro", "body": "Colete todas as peças necessárias."},
        },
    }
    llm, scripted = service(completion(payload))
    result = await llm.answer(MESSAGES, contract=contract)
    assert [b.source_ids for b in result.blocks] == [["a"], ["b"]]
    schema = scripted.calls[0]["response_format"]["json_schema"]["schema"]
    assert schema["$defs"]["RequiredSections"]["required"] == ["s0", "s1"]
    assert "source_ids" not in schema["$defs"]["OrderedSection"]["properties"]


@pytest.mark.asyncio
async def test_missing_ordered_section_is_repaired_without_accepting_a_partial_batch():
    contract = AnswerContract(
        "detailed",
        ("a", "b"),
        (
            SourceRequirement("a", 3, 0),
            SourceRequirement("b", 3, 0),
        ),
        ordered=True,
    )
    missing = {
        "answer": "",
        "sections": {
            "s0": {"title": "Primeiro", "body": "Colete todas as peças necessárias."},
        },
    }
    full = {
        "answer": "",
        "sections": {
            **missing["sections"],
            "s1": {"title": "Segundo", "body": "Monte o equipamento na bancada."},
        },
    }
    llm, scripted = service(completion(missing), completion(full))
    result = await llm.answer(MESSAGES, contract=contract)
    assert len(result.blocks) == 2
    assert len(scripted.calls) == 2


def test_strict_schema_requires_all_fields_and_only_offered_source_ids():
    schema = response_schema(LLMResponse, CONTRACT)
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    block = schema["$defs"]["GeneratedBlock"]
    assert block["additionalProperties"] is False
    assert block["properties"]["source_ids"]["items"]["enum"] == ["guide:part-1"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad",
    [
        completion('{"answer":'),
        completion({"answer": "Fase iniciada."}),
        completion({**GOOD, "blocks": []}),
        completion(GOOD, finish_reason="length"),
        completion(
            {**GOOD, "blocks": [{"title": "Peça", "body": "Pronto.", "source_ids": ["invented"]}]}
        ),
    ],
)
async def test_output_defects_are_corrected_once_with_validation_feedback(bad):
    llm, scripted = service(bad, completion(GOOD))
    result = await llm.answer(MESSAGES, contract=CONTRACT)
    assert result.blocks
    assert len(scripted.calls) == 2
    assert scripted.calls[0]["response_format"]["json_schema"]["strict"] is True
    assert scripted.calls[1]["messages"][-1]["role"] == "system"
    assert MESSAGES == [
        {"role": "user", "content": "Explique esta fase usando os trechos fornecidos."}
    ]


@pytest.mark.asyncio
async def test_repeated_failure_stops_after_one_correction():
    llm, scripted = service(completion({"answer": "Pronto."}))
    with pytest.raises(LLMResponseError, match="after one correction"):
        await llm.answer(MESSAGES, contract=CONTRACT)
    assert len(scripted.calls) == 2


def provider_error(error_class, status, code):
    return error_class(
        "Provider error",
        response=httpx.Response(
            status, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
        ),
        body={"code": code, "message": "Provider error"},
    )


@pytest.mark.asyncio
async def test_provider_json_validation_error_is_regenerated():
    llm, scripted = service(
        provider_error(BadRequestError, 400, "json_validate_failed"), completion(GOOD)
    )
    assert (await llm.answer(MESSAGES, contract=CONTRACT)).blocks
    assert len(scripted.calls) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        provider_error(AuthenticationError, 401, "invalid_api_key"),
        provider_error(RateLimitError, 429, "rate_limit_exceeded"),
    ],
)
async def test_authentication_and_quota_errors_do_not_trigger_format_correction(error):
    llm, scripted = service(error)
    with pytest.raises(LLMUnavailableError):
        await llm.answer(MESSAGES, contract=CONTRACT)
    assert len(scripted.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_message,daily",
    [
        ("Rate limit reached on tokens per day (TPD)", True),
        ("Rate limit reached on requests per day (RPD)", True),
        ("Rate limit reached on tokens per minute (TPM)", False),
    ],
)
async def test_free_quota_message_distinguishes_daily_and_temporary_limits(provider_message, daily):
    error = RateLimitError(
        provider_message,
        response=httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com")),
        body={"code": "rate_limit_exceeded", "message": provider_message},
    )
    llm, scripted = service(error)
    with pytest.raises(LLMUnavailableError) as caught:
        await llm.answer(MESSAGES, contract=CONTRACT)
    assert ("amanhã" in str(caught.value)) is daily
    assert "gratuita" in str(caught.value)
    assert len(scripted.calls) == 1


@pytest.mark.asyncio
async def test_invalid_request_configuration_is_not_retried_as_generated_json():
    llm, scripted = service(provider_error(BadRequestError, 400, "invalid_request"))
    with pytest.raises(LLMResponseError, match="configuration"):
        await llm.answer(MESSAGES, contract=CONTRACT)
    assert len(scripted.calls) == 1


@pytest.mark.asyncio
async def test_other_models_keep_json_mode_with_the_same_content_validation():
    llm, scripted = service(completion(GOOD), model="another-model")
    assert (await llm.answer(MESSAGES, contract=CONTRACT)).blocks
    assert scripted.calls[0]["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
@pytest.mark.parametrize("defect", ["file-question", "unknown-source", "missing-phase"])
async def test_source_planning_repairs_invalid_selection_and_never_asks_for_files(defect):
    root = KnowledgeChunk(
        "root",
        "map",
        "Map",
        "pap.md",
        "pap",
        "",
        "Procedure",
        "Complete the documented procedure.",
        (),
        0,
    )
    context = PlanningContext((root,), ("root",), MESSAGES)
    step = {
        "source_id": "0",
        "role": "objective",
        "supporting_ids": [],
        "anchor_id": "",
        "before_source_id": "",
        "evidence": "",
    }
    good = {"steps": [step]}
    if defect == "file-question":
        bad = {
            "need_clarification": True,
            "clarification_question": "Qual arquivo devo usar?",
            "steps": [],
        }
    elif defect == "unknown-source":
        bad = {**good, "steps": [{**step, "source_id": "other-map"}]}
    else:
        bad = {**good, "steps": []}
    llm, scripted = service(completion(bad), completion(good))
    selected = await llm.plan_sources(context)
    assert selected.steps[0].source_id == "root"
    assert len(scripted.calls) == 2
    assert scripted.calls[0]["response_format"]["json_schema"]["name"] == "SourcePlan"
