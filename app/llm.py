from __future__ import annotations

import json
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, BadRequestError
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model

from app.answer_policy import AnswerContract, answer_violations
from app.config import Settings
from app.source_planning import (
    PlannedSource,
    PlanningContext,
    SourcePlan,
    has_completion_claim,
    plan_violations,
)

logger = logging.getLogger("krono.llm")


class StructuredModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeneratedBlock(StructuredModel):
    title: str = Field(default="", max_length=250)
    body: str = Field(max_length=30_000)
    source_ids: list[str] = Field(default_factory=list, max_length=30)


class OrderedSection(StructuredModel):
    title: str
    body: str = Field(min_length=1, max_length=30_000)


class LLMResponse(StructuredModel):
    answer: str = ""
    need_clarification: bool = False
    clarification_question: str = ""
    image_ids: list[str] = Field(default_factory=list)
    blocks: list[GeneratedBlock] = Field(default_factory=list, max_length=160)


class QueryResolution(StructuredModel):
    resolved_query: str = ""
    need_clarification: bool = False
    clarification_question: str = ""
    candidate_document_paths: list[str] = Field(default_factory=list)


class CompletionClaim(StructuredModel):
    source_ids: list[str] = Field(default_factory=list, max_length=160)
    evidence: str = ""


class CompletionFacts(StructuredModel):
    claims: list[CompletionClaim] = Field(default_factory=list, max_length=20)


class AnswerCoverage(StructuredModel):
    missing_facts: list[str] = Field(default_factory=list, max_length=40)
    contradictions: list[str] = Field(default_factory=list, max_length=40)


class LLMUnavailableError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class LLMContentError(LLMResponseError):
    """Invalid or incomplete content after bounded correction, not transport/configuration."""


class LLMOutputError(LLMResponseError):
    """A generation defect that may be repaired by one bounded regeneration."""


def response_schema(model: type[BaseModel], contract: AnswerContract | None = None) -> dict:
    schema = model.model_json_schema()

    def constrain(node):
        if isinstance(node, dict):
            for key in ("default", "maxLength", "minLength", "minItems", "maxItems"):
                node.pop(key, None)
            if node.get("type") == "object":
                node["additionalProperties"] = False
                node["required"] = list(node.get("properties", {}))
            for value in node.values():
                constrain(value)
        elif isinstance(node, list):
            for value in node:
                constrain(value)

    constrain(schema)
    if contract and contract.allowed_ids:
        schema["$defs"]["GeneratedBlock"]["properties"]["source_ids"]["items"]["enum"] = list(
            contract.allowed_ids
        )
    return schema


@dataclass(slots=True)
class LLMService:
    settings: Settings
    _client: AsyncOpenAI | None = field(init=False, repr=False, default=None)
    _paid_client: AsyncOpenAI | None = field(init=False, repr=False, default=None)
    _free_retry_after: float = field(init=False, repr=False, default=0.0)

    def __post_init__(self) -> None:
        if self.settings.paid_local_enabled:
            self._paid_client = AsyncOpenAI(
                api_key=self.settings.openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
                timeout=90.0,
                max_retries=0,
            )
        self._client = (
            AsyncOpenAI(
                api_key=self.settings.groq_api_key,
                base_url="https://api.groq.com/openai/v1",
                timeout=35.0,
                # Surface 429 immediately so the permitted local fallback can run.
                max_retries=0,
            )
            if self.settings.groq_api_key
            else None
        )
        if self.settings.llm_provider == "openrouter":
            self._client = self._paid_client

    async def _request_completion(self, messages, model, contract):
        provider = self.settings.llm_provider
        if provider == "groq" and self._paid_client and time.monotonic() < self._free_retry_after:
            return await self._provider_completion(
                self._paid_client, "openrouter", messages, model, contract
            )
        try:
            return await self._provider_completion(
                self._client, provider, messages, model, contract
            )
        except APIStatusError as error:
            if error.status_code != 429 or provider != "groq" or self._paid_client is None:
                raise
            try:
                cooldown = float(error.response.headers.get("retry-after", "60"))
            except ValueError:
                cooldown = 60.0
            self._free_retry_after = time.monotonic() + max(60.0, min(cooldown, 3600.0))
            logger.info("Free quota exhausted; using explicitly enabled local OpenRouter.")
            return await self._provider_completion(
                self._paid_client, "openrouter", messages, model, contract
            )

    async def _provider_completion(self, client, provider, messages, model, contract):
        model_name = "openai/gpt-oss-120b" if provider == "openrouter" else self.settings.groq_model
        options = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        if model_name.startswith("openai/gpt-oss") and provider != "openrouter":
            options["reasoning_effort"] = "low"
        if model_name in {"openai/gpt-oss-120b", "openai/gpt-oss-20b"}:
            options["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": model.__name__,
                    "strict": True,
                    "schema": response_schema(model, contract),
                },
            }
        if provider == "openrouter":
            options["max_tokens"] = 12_000
            options["extra_body"] = {
                "reasoning": {"effort": "low"},
                "provider": {
                    "require_parameters": True,
                    "only": ["deepinfra/bf16", "crusoe/bf16"],
                    "order": ["deepinfra/bf16", "crusoe/bf16"],
                    "max_price": {"prompt": 0.06, "completion": 0.25},
                },
            }
        response = await client.chat.completions.create(**options)
        self._record_usage(response, provider, model_name, model.__name__)
        return response

    def _record_usage(self, response, provider, model_name, stage):
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "upstream_provider": getattr(response, "provider", None),
            "model": model_name,
            "stage": stage,
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "reasoning_tokens": getattr(
                getattr(usage, "completion_tokens_details", None), "reasoning_tokens", None
            ),
            "cost_usd": getattr(usage, "cost", None),
        }
        logger.info("LLM usage: %s", json.dumps(record))
        if self.settings.app_env == "development":
            try:
                self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
                log_path = self.settings.cache_dir / "llm-usage.jsonl"
                with log_path.open("a", encoding="utf-8") as log:
                    log.write(json.dumps(record) + "\n")
            except OSError:
                logger.warning("Could not write local LLM usage log.")

    async def answer(
        self,
        messages: list[dict[str, str]],
        *,
        contract: AnswerContract | None = None,
    ) -> LLMResponse:
        def validate(parsed):
            if not parsed.need_clarification and not parsed.answer.strip() and not parsed.blocks:
                return ["The model returned an empty answer."]
            if parsed.need_clarification and not parsed.clarification_question.strip():
                return ["The model requested clarification without a question."]
            return answer_violations(parsed, contract) if contract else []

        if contract and contract.ordered and len(contract.requirements) > 1:
            bindings = {f"s{i}": r.id for i, r in enumerate(contract.requirements)}
            fields: dict[str, Any] = {key: (OrderedSection, ...) for key in bindings}
            sections = create_model(
                "RequiredSections",
                __base__=StructuredModel,
                **fields,
            )
            ordered_answer = create_model(
                "OrderedAnswer",
                __base__=StructuredModel,
                answer=(str, ...),
                sections=(sections, ...),
            )

            def normalize(parsed):
                return LLMResponse(
                    answer=parsed.answer,
                    blocks=[
                        GeneratedBlock(
                            title=getattr(parsed.sections, key).title,
                            body=getattr(parsed.sections, key).body,
                            source_ids=[id_],
                        )
                        for key, id_ in bindings.items()
                    ],
                )

            parsed = await self._validated_completion(
                [
                    *messages,
                    {
                        "role": "system",
                        "content": (
                            "For this ORDERED BATCH use OrderedAnswer JSON instead of generic "
                            "blocks: answer is a short introduction; sections is an object with "
                            "EVERY required sN key, each containing title and body. The server "
                            "binds source IDs and order automatically. Never merge required "
                            "sections, omit a key, or leave a body empty. Write complete "
                            "instructions at the requested detail. Bindings: "
                            + json.dumps(bindings)
                        ),
                    },
                ],
                ordered_answer,
                lambda value: validate(normalize(value)),
            )
            return normalize(parsed)
        return await self._validated_completion(messages, LLMResponse, validate, contract)

    async def resolve_query(
        self,
        messages: list[dict[str, str]],
    ) -> QueryResolution:
        def validate(parsed):
            if parsed.need_clarification and not parsed.clarification_question.strip():
                return ["Query resolution requested an empty clarification."]
            if not parsed.need_clarification and not parsed.resolved_query.strip():
                return ["Query resolution returned no query."]
            return []

        return await self._validated_completion(messages, QueryResolution, validate)

    async def completed_sources(self, context):
        candidates = {str(i): c for i, c in enumerate(context.candidates)}
        messages = [
            {
                "role": "system",
                "content": (
                    "Extract only procedures the USER explicitly states are already completed. "
                    "Return numeric source_ids and an exact quote from USER STATEMENTS proving it. "
                    "Completed upgraded equipment covers its base crafting and upgrade procedures, "
                    "including shared setup/finalization. Do not infer progress from "
                    "recommendations, assistant replies, hypotheticals or future goals. "
                    "Do not mark current main-quest "
                    "phases completed. If uncertain, return no claims."
                    "A source with multiple milestones is completed only when the user claims "
                    "all of them; partial progress does not complete the entire section."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "USER STATEMENTS": context.user_statements,
                        "catalog": {
                            i: f"{c.path}: {c.section_title}" for i, c in candidates.items()
                        },
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        def validate(facts):
            errors = []
            for claim in facts.claims:
                if (
                    not claim.evidence
                    or claim.evidence not in context.user_statements
                    or not (has_completion_claim(claim.evidence))
                ):
                    errors.append(
                        "Completion requires an exact explicit completed-state USER quote."
                    )
                if re.search(r"\b(?:não|nao|not|pas|falta|faltam)\b", claim.evidence, re.I):
                    errors.append("Do not treat negated or missing progress as completed.")
                if any(s not in candidates for s in claim.source_ids):
                    errors.append("Only offered IDs may be marked completed.")
            return errors

        facts = await self._validated_completion(messages, CompletionFacts, validate)
        return tuple(
            dict.fromkeys(
                candidates[s].id
                for claim in facts.claims
                for s in claim.source_ids
                if candidates[s].category != "main_ee"
            )
        )

    async def ensure_coverage(self, messages, generated, contract, *, sources=None, plan=None):
        """A separate source comparison checks semantics beyond the JSON contract."""
        instructions = (
            "Compare the proposed answer against the supplied sources and answer contract. "
            "Return AnswerCoverage JSON. Check EVERY required source. For DETAILED answers "
            "check all actionable steps, alternative spawn locations, numbers, conditions and "
            "order; do not accept a mere mention of the objective as explaining it. For SUMMARY "
            "require essential objectives, prerequisites and failure-critical conditions, not "
            "every location/detail. Honor explicitly completed prerequisites and brief optional "
            "recommendations. Do not require content assigned to other INTERNAL BATCHES. "
            "Calling an optional/recommended/useful item mandatory is a contradiction. "
            "In SUMMARY, alternative task lists need only their selection rule and essential "
            "goal/conditions; do not demand every possible random challenge or recipe. "
            "Do not require image IDs or filenames in prose: the server attaches the images. "
            "Do not require raw image-reference lines, flavor text, external links or headings. "
            "List concrete omissions and contradictions; no style preferences or new gameplay "
            "facts. Report unsupported gameplay assertions, including invented solo/co-op claims, "
            "as contradictions. Honor the execution outline: preparation is not a fully completed "
            "upgrade when a shared finalization stage still follows. "
            "Empty lists mean complete against these sources at the requested detail."
        )

        async def audit(answer):
            source_scope = (
                [
                    {
                        "source_id": c.chunk.id,
                        "title": c.chunk.section_title,
                        "content": c.chunk.content,
                    }
                    for c in sources
                ]
                if sources is not None
                else messages
            )
            return await self._validated_completion(
                [
                    {"role": "system", "content": instructions},
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "detail": contract.detail if contract else "direct",
                                "AUDIT ONLY THESE SOURCES": source_scope,
                                "source_rules": [
                                    {
                                        "id": s.source_id,
                                        "role": s.role,
                                        "condition": s.condition,
                                        "required_grouped_ids": s.grouped_source_ids,
                                    }
                                    for s in plan.steps
                                ]
                                if plan
                                else [],
                                "explicitly_completed_procedures": plan.completed_source_ids
                                if plan
                                else [],
                                "proposed_blocks": [b.model_dump() for b in answer.blocks],
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
                AnswerCoverage,
                lambda parsed: [],
            )

        report = await audit(generated)
        missing = [*report.missing_facts, *report.contradictions]
        if not missing:
            return generated
        logger.warning("Source coverage correction requested: %s", json.dumps(missing))
        repaired = await self.answer(
            [
                *messages,
                {
                    "role": "system",
                    "content": (
                        "Regenerate the entire batch, preserving all source requirements. Correct "
                        "these concrete source coverage defects: "
                        + json.dumps(missing, ensure_ascii=False)
                    ),
                },
            ],
            contract=contract,
        )
        check = await audit(repaired)
        if check.missing_facts or check.contradictions:
            raise LLMContentError(
                "Source coverage audit failed after one semantic correction: "
                + json.dumps(check.model_dump(), ensure_ascii=False)
            )
        return repaired

    async def plan_sources(self, context: PlanningContext) -> SourcePlan:
        if context.inspect_dependencies and context.required_ids:
            from app.dependency_discovery import procedure_members

            ids = list(context.required_ids)
            covered_paths = {c.path for c in context.candidates if c.id in ids}
            for path in context.objective_paths:
                if path not in covered_paths:
                    target = next(c for c in context.candidates if c.path == path)
                    ids.extend(c.id for c in procedure_members(target, context, ""))
            plan = SourcePlan(
                steps=[PlannedSource(source_id=id_, role="objective") for id_ in dict.fromkeys(ids)]
            )
        else:
            plan = await self._validated_completion(
                context.messages,
                SourcePlan,
                lambda parsed: plan_violations(context.canonical_plan(parsed), context),
            )
        plan = context.canonical_plan(plan)
        if context.inspect_dependencies and context.dependency_index is not None:
            from app.dependency_discovery import discover_dependencies

            plan = await discover_dependencies(self, context, plan)
        return plan

    async def _validated_completion(
        self,
        messages: list[dict[str, str]],
        model: type[BaseModel],
        validate: Callable,
        contract: AnswerContract | None = None,
    ):
        attempts = list(messages)
        for attempt in range(2):
            try:
                payload = await self._json_completion(attempts, model, contract)
                parsed = model.model_validate(payload, strict=True)
                violations = validate(parsed)
                if violations:
                    raise LLMOutputError(" ".join(violations[:12]))
                return parsed
            except (ValidationError, LLMOutputError) as error:
                if attempt:
                    raise LLMContentError(
                        f"Structured response failed after one correction: {error}"
                    ) from error
                diagnostics = (
                    [{"location": e["loc"], "type": e["type"]} for e in error.errors()]
                    if isinstance(error, ValidationError)
                    else str(error)
                )
                logger.warning(
                    "Regenerating %s (one correction): %s", model.__name__, diagnostics
                )
                attempts = [
                    *messages,
                    {
                        "role": "system",
                        "content": (
                            "Regenerate the entire response as valid JSON matching the schema. "
                            "Correct these validation failures without omitting source facts: "
                            f"{str(error)[:3500]}"
                        ),
                    },
                ]
        raise AssertionError("Unreachable generation state")

    async def _json_completion(
        self,
        messages: list[dict[str, str]],
        model: type[BaseModel] = LLMResponse,
        contract: AnswerContract | None = None,
    ) -> dict[str, object]:
        if self._client is None:
            raise LLMUnavailableError(
                "No permitted model API key is configured. The knowledge base is healthy, "
                "but chat generation is unavailable."
            )

        schema_instruction = {
            "role": "system",
            "content": (
                "OUTPUT CONTRACT FOR THIS CALL: return ONLY one JSON object matching the "
                "following exact schema. These field names override any generic output example. "
                "Do not invent alternative field names. Include every required field; use empty "
                "arrays/strings when applicable. Schema: "
                + json.dumps(response_schema(model, contract), ensure_ascii=False)
            ),
        }
        offset = 1 if messages and messages[0]["role"] == "system" else 0
        messages = [*messages[:offset], schema_instruction, *messages[offset:]]
        try:
            response = await self._request_completion(messages, model, contract)
        except BadRequestError as error:
            if error.code == "json_validate_failed":
                raise LLMOutputError("Provider rejected malformed generated JSON.") from error
            raise LLMResponseError(
                "Model request configuration was rejected (HTTP 400)."
            ) from error
        except APIStatusError as error:
            if error.request.url.host == "openrouter.ai":
                raise LLMUnavailableError(
                    "O crédito de desenvolvimento do OpenRouter acabou."
                    if error.status_code == 402
                    else f"OpenRouter indisponível no desenvolvimento (HTTP {error.status_code}). "
                    "Tente novamente em instantes."
                ) from error
            if error.status_code == 429:
                description = str(error).casefold()
                daily = any(
                    marker in description
                    for marker in (
                        "tokens per day",
                        "requests per day",
                        "daily",
                        "(tpd)",
                        "(rpd)",
                    )
                )
                raise LLMUnavailableError(
                    "Infelizmente, usamos APIs gratuitas e o limite diário de uso foi atingido. "
                    "Tente novamente amanhã."
                    if daily
                    else "A API gratuita atingiu o limite temporário de uso. "
                    "Aguarde alguns instantes e tente novamente."
                ) from error
            raise LLMUnavailableError(
                f"Model provider unavailable or request refused (HTTP {error.status_code})."
            ) from error
        except APIConnectionError as error:
            raise LLMUnavailableError("Could not connect to the model provider.") from error

        try:
            choice = response.choices[0]
            content = choice.message.content
        except (AttributeError, IndexError, TypeError) as error:
            raise LLMOutputError("The model returned no usable completion.") from error
        if getattr(choice, "finish_reason", None) == "length":
            raise LLMOutputError(
                "Response was truncated; return all required sections within capacity."
            )
        if not content:
            raise LLMOutputError("The model returned an empty response.")

        try:
            payload = json.loads(_strip_json_fence(content))
        except json.JSONDecodeError as error:
            raise LLMOutputError(
                f"The model returned invalid structured output: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise LLMOutputError("The model returned a non-object JSON value.")
        return payload


def _strip_json_fence(value: str) -> str:
    stripped = value.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL)
    return match.group(1).strip() if match else stripped
