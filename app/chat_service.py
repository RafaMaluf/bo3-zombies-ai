"""Conversation orchestration, independent of FastAPI request and application state."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import replace

from fastapi import HTTPException

from app.answer_policy import (
    build_contract,
    expand_procedure,
    resolve_answer_intent,
    retrieval_query,
)
from app.chat_progress import report_progress
from app.config import settings
from app.conversation import (
    build_resolution_messages,
    clarification_for_options,
    deterministic_follow_up_options,
    document_catalog,
    history_without_duplicate_current_message,
    should_resolve_follow_up,
    source_anchored_query,
    validated_document_options,
)
from app.domain import ImageAsset, ScoredChunk
from app.guidance import prepare_guidance
from app.guide_dependencies import DependencyError, DependencyIndex, compact_summary
from app.knowledge_base import KnowledgeBase
from app.language import resolve_response_language
from app.llm import LLMContentError, LLMResponse, LLMResponseError, LLMService, LLMUnavailableError
from app.presentation import present_blocks
from app.prompt_builder import build_answer_prompt
from app.retrieval import SearchEngine
from app.schemas import ChatRequest, ChatResponse, MapSwitchAction, RelevantImage, SelectedSource
from app.source_planning import (
    PlanCapacityError,
    SourcePlan,
    apply_plan,
    has_completion_claim,
    plan_instructions,
    plan_violations,
    planning_context,
)

logger = logging.getLogger("krono.chat")
IMAGE_ID_PATTERN = re.compile(r"`?img_[a-f0-9]{16}`?", flags=re.IGNORECASE)


async def _match_status(req, llm, language, catalog, kb):
    from app.companion_interpret import interpret_progress

    try:
        status = await interpret_progress(
            llm,
            req.message,
            req.match_state.model_copy(update={"language": language}),
            catalog,
            kb,
        )
    except LLMUnavailableError as error:
        raise HTTPException(503, str(error)) from error
    except LLMResponseError as error:
        raise HTTPException(
            502, "Não foi possível consultar a partida. Tente novamente."
        ) from error
    if status.intent == "status":
        return ChatResponse(
            answer=status.reply, introduction=status.reply, active_map_id=catalog.map_id
        )
    return None


async def _generate_plan(
    llm: LLMService,
    plan: SourcePlan,
    retrieval,
    knowledge_base,
    question,
    history,
    detail,
    language,
    guide_instructions,
    _budget=None,
    _outline=None,
    *,
    _batch_mode="sequential",
    _part_index=0,
    _part_count=None,
) -> LLMResponse:
    """Generate bounded batches; return only after every batch succeeds."""
    batches = []
    batch: list[ScoredChunk] = []
    chars = 0
    for item in retrieval.chunks:
        size = len(item.chunk.content) + 600
        if _batch_mode != "single" and batch and (len(batch) >= 8 or chars + size > 10_000):
            batches.append(tuple(batch))
            batch, chars = [], 0
        batch.append(item)
        chars += size
    if batch:
        batches.append(tuple(batch))
    if len(batches) > 16:
        raise PlanCapacityError("O guia é muito extenso. Peça uma fase específica para aprofundar.")
    combined = LLMResponse()
    if _budget is None:
        _budget = [0]
    if _outline is None:
        _outline = tuple(c.chunk.section_title for c in retrieval.chunks)
    if _batch_mode not in {"sequential", "single", "parallel"}:
        raise ValueError("Unknown generation experiment mode")
    if _batch_mode == "parallel":
        semaphore = asyncio.Semaphore(4)

        def combine(parts):
            return LLMResponse(
                answer=parts[0].answer if parts else "",
                blocks=[block for part in parts for block in part.blocks],
                image_ids=[id_ for part in parts for id_ in part.image_ids],
            )

        async def generate_part(index, chunks):
            async with semaphore:
                ids = {c.chunk.id for c in chunks}
                part = plan.model_copy(
                    update={"steps": [s for s in plan.steps if s.source_id in ids]}
                )
                return await _generate_plan(
                    llm,
                    part,
                    replace(retrieval, chunks=chunks),
                    knowledge_base,
                    question,
                    history,
                    detail,
                    language,
                    guide_instructions,
                    _budget,
                    _outline,
                    _batch_mode="single",
                    _part_index=index,
                    _part_count=len(batches),
                )

        tasks = [asyncio.create_task(generate_part(i, c)) for i, c in enumerate(batches)]
        try:
            parts = await asyncio.gather(*tasks)
        except BaseException:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return combine(parts)
    for index, chunks in enumerate(batches):
        _budget[0] += 1
        if _budget[0] > 16:
            raise PlanCapacityError("O procedimento excedeu a capacidade de geração verificada.")
        ids = {c.chunk.id for c in chunks}
        part = plan.model_copy(update={"steps": [s for s in plan.steps if s.source_id in ids]})
        contract = build_contract(chunks, detail, ordered=True)
        if detail == "summary":
            limits = {s.source_id: 180 if s.grouped_source_ids else 120 for s in part.steps}
            contract = replace(
                contract,
                requirements=tuple(
                    replace(r, maximum_words=limits[r.id]) for r in contract.requirements
                ),
            )
        recommended = {s.source_id for s in part.steps if s.role == "recommended"}
        contract = replace(
            contract,
            requirements=tuple(
                replace(r, minimum_words=3, minimum_items=0, maximum_words=45)
                if r.id in recommended
                else r
                for r in contract.requirements
            ),
        )
        whole_answer = _batch_mode == "single" and _part_count is None
        outline_label = (
            "FULL EXECUTION OUTLINE (cover all stages in this answer): "
            if whole_answer
            else "FULL EXECUTION OUTLINE (context only; other batches explain other stages): "
        )
        scope = (
            "This is the ENTIRE answer, not one part. Explain ALL supplied sources at the "
            "requested detail, including every mandatory grouped procedure and finalization. "
            "No later generation will fill missing instructions. Do not ask to continue. "
            if whole_answer
            else f"INTERNAL BATCH {index + _part_index + 1}/"
            f"{_part_count or len(batches)}: explain only these sources. "
            "Other batches cover the other steps. Do not recap or ask to continue. "
        )
        prompt = build_answer_prompt(
            user_message=question,
            history=[m.model_copy(update={"content": m.content[:1600]}) for m in history[-2:]],
            scored_chunks=chunks,
            knowledge_base=knowledge_base,
            max_context_chars=sum(len(c.chunk.content) + 600 for c in chunks) + 1000,
            max_candidate_images=sum(len(c.chunk.image_ids) for c in chunks),
            response_language=language,
            guide_instructions="\n".join(
                [
                    guide_instructions,
                    plan_instructions(part, detail),
                    outline_label + " -> ".join(_outline),
                    scope
                    + "Never mention internal batches, files, source IDs or implementation details "
                    "to the player. Shared finalization stages appear later in this SAME answer; "
                    "do not claim an item is fully upgraded before that finalization. "
                    "Do not add unsupported solo/co-op claims when the source states none. "
                    + ("Keep answer introduction empty." if index + _part_index else ""),
                ]
            ),
            answer_contract=contract,
            include_image_catalog=False,
        )
        try:
            report_progress("generating")
            result = await llm.answer(prompt.messages, contract=contract)
            if settings.answer_audit_enabled and hasattr(llm, "ensure_coverage"):
                report_progress("reviewing")
                result = await llm.ensure_coverage(
                    prompt.messages, result, contract, sources=chunks, plan=part
                )
        except LLMContentError:
            if len(chunks) < 2:
                raise
            logger.warning("Splitting an incomplete batch into smaller verified batches.")
            children = []
            middle = len(chunks) // 2
            for subset in (chunks[:middle], chunks[middle:]):
                child_ids = {c.chunk.id for c in subset}
                child_plan = part.model_copy(
                    update={"steps": [s for s in part.steps if s.source_id in child_ids]}
                )
                children.append(
                    await _generate_plan(
                        llm,
                        child_plan,
                        replace(retrieval, chunks=subset),
                        knowledge_base,
                        question,
                        history,
                        detail,
                        language,
                        guide_instructions
                        + "\nFull procedure continues in other verified batches.",
                        _budget,
                        _outline,
                    )
                )
            result = LLMResponse(
                answer=children[0].answer, blocks=[b for c in children for b in c.blocks]
            )
        if result.need_clarification:
            raise LLMResponseError("A planned procedure was replaced by a clarification.")
        if index == 0:
            combined.answer = result.answer
        combined.blocks.extend(result.blocks)
        combined.image_ids.extend(result.image_ids)
    return combined


async def _search(
    search_engine: SearchEngine,
    query: str,
    active_map_id: str | None,
    limit: int,
):
    report_progress("searching")
    # Semantic retrieval performs a short network request. Keep it away from
    # FastAPI's event loop while preserving the synchronous deterministic API
    # used by the retrieval test suite.
    return await asyncio.to_thread(
        search_engine.search,
        retrieval_query(query),
        active_map_id,
        limit,
    )


def _select_image_assets(
    requested_ids: list[str],
    available_assets: tuple[ImageAsset, ...],
    limit: int,
) -> list[ImageAsset]:
    allowed = {asset.id: asset for asset in available_assets}
    selected = []
    seen_ids: set[str] = set()
    for image_id in requested_ids:
        asset = allowed.get(image_id)
        if asset is None or asset.id in seen_ids:
            continue
        selected.append(asset)
        seen_ids.add(asset.id)
        if len(selected) >= limit:
            return selected

    target_count = min(limit, 6)
    if selected:
        selected_documents = {asset.document_path for asset in selected}
        selected_sections = {(asset.document_path, asset.section) for asset in selected}
        for asset in available_assets:
            if (
                asset.id in seen_ids
                or asset.document_path not in selected_documents
                or (asset.document_path, asset.section) not in selected_sections
            ):
                continue
            selected.append(asset)
            seen_ids.add(asset.id)
            if len(selected) >= target_count:
                break
        return selected

    if not available_assets:
        return selected

    # Models occasionally omit images even for visual procedures. Fall back
    # to one asset per section from the highest-ranked visual document instead
    # of leaking loosely related images from another guide.
    seen_sections: set[tuple[str, str]] = set()
    preferred_document = available_assets[0].document_path
    for asset in available_assets:
        if asset.document_path != preferred_document:
            continue
        section_key = (asset.map_id, asset.section)
        if section_key in seen_sections:
            continue
        selected.append(asset)
        seen_sections.add(section_key)
        seen_ids.add(asset.id)
        if len(selected) >= target_count:
            break

    # A location guide can keep every screenshot in one section. Once section
    # diversity is covered, fill the remaining slots from the same document.
    for asset in available_assets:
        if asset.document_path != preferred_document or asset.id in seen_ids:
            continue
        selected.append(asset)
        seen_ids.add(asset.id)
        if len(selected) >= target_count:
            break
    return selected


def _strip_internal_image_references(answer: str) -> str:
    lines = [line for line in answer.splitlines() if not IMAGE_ID_PATTERN.search(line)]
    orphaned_tail_markers = {
        "---",
        "images",
        "imagens",
        "imagens de apoio",
        "supporting images",
    }
    while lines:
        marker = lines[-1].strip().strip("*# ").casefold()
        if not marker or marker in orphaned_tail_markers:
            lines.pop()
            continue
        break
    return "\n".join(lines).rstrip()


async def answer_chat(
    req: ChatRequest,
    knowledge_base: KnowledgeBase,
    search_engine: SearchEngine,
    llm: LLMService,
    image_url: Callable[[str, str], str],
) -> ChatResponse:
    report_progress("understanding")
    if knowledge_base.errors:
        raise HTTPException(
            status_code=503,
            detail=(
                "The knowledge base has validation errors. Run `python -m scripts.validate_kb`."
            ),
        )

    history = history_without_duplicate_current_message(
        req.conversation_history,
        req.message,
        settings.max_history_messages,
    )
    response_language = resolve_response_language(
        req.message,
        history,
        req.preferred_language,
    )
    requested_map_switch_id = search_engine.requested_map_switch_id(
        req.message,
        req.active_map_id,
    )
    if requested_map_switch_id is not None and req.active_map_id is not None:
        return ChatResponse(
            active_map_id=req.active_map_id,
            map_switch=MapSwitchAction(
                current_map_id=req.active_map_id,
                requested_map_id=requested_map_switch_id,
            ),
        )

    request_map_id = req.active_map_id if req.active_map_id in knowledge_base.maps else None
    if request_map_id is None:
        explicit_maps = search_engine.explicit_map_ids(req.message)
        if len(explicit_maps) == 1:
            request_map_id = explicit_maps[0]
        elif not explicit_maps and req.match_state:
            request_map_id = req.match_state.map_id

    match_instructions = ""
    match_completed: tuple[str, ...] = ()
    if req.match_state and request_map_id == req.match_state.map_id:
        from app.companion_state import build_catalog, validate_state

        try:
            match_catalog = build_catalog(knowledge_base, request_map_id, response_language)
            validate_state(req.match_state, match_catalog)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        from app.companion_interpret import common_status_query

        if common_status_query(req.message):
            status_response = await _match_status(
                req,
                llm,
                response_language,
                match_catalog,
                knowledge_base,
            )
            if status_response:
                return status_response
        match_completed = tuple(
            i
            for o in match_catalog.objectives
            if not o.main and req.match_state.statuses.get(o.id) == "complete"
            for i in o.source_ids
        )
        match_instructions = (
            "MATCH CONTEXT (player-reported data; do not change progress from a question): "
            + json.dumps(
                {
                    "players": req.match_state.player_count,
                    "objectives": [
                        {"title": o.title, "status": req.match_state.statuses.get(o.id, "unknown")}
                        for o in match_catalog.objectives
                        if not o.optional or o.id in req.match_state.statuses
                    ],
                    "partial": req.match_state.partial,
                },
                ensure_ascii=False,
            )
            + ". Unknown is not completed. Distinguish missing from unconfirmed objectives."
        )

    requested_paths = search_engine.explicit_document_paths(
        req.message,
        request_map_id,
    )
    objective_path_candidates = list(requested_paths)
    if request_map_id and re.search(r"pack[ -]a[ -]punch|\bpap\b", req.message, re.I):
        pap_paths = {
            c.path
            for c in knowledge_base.chunks.values()
            if c.map_id == request_map_id and c.category == "pap"
        }
        if len(pap_paths) == 1:
            objective_path_candidates.extend(pap_paths)
    objective_paths = tuple(dict.fromkeys(objective_path_candidates))
    try:
        guide_context = prepare_guidance(req, knowledge_base, search_engine, response_language)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if guide_context:
        response_language = guide_context.progress.state.language or response_language
    retrieval = (
        guide_context.retrieval
        if guide_context
        else await _search(
            search_engine,
            req.message,
            request_map_id,
            settings.max_retrieved_chunks,
        )
    )

    planning_question = req.message
    resolved_multiple = False
    explicit_objective = bool(requested_paths) or bool(
        re.search(
            r"\b(?:pack[ -]a[ -]punch|pap|easter egg|ee|main quest)\b",
            retrieval_query(req.message),
        )
    )
    if (
        not guide_context
        and not explicit_objective
        and should_resolve_follow_up(
            req.message,
            history,
            req.active_map_id,
            retrieval,
        )
    ):
        active_record = knowledge_base.maps.get(req.active_map_id or "")
        documents = document_catalog(knowledge_base, req.active_map_id or "")
        if active_record is not None and documents:
            deterministic_options = deterministic_follow_up_options(
                req.message,
                history,
                documents,
            )
            if deterministic_options:
                objective_paths = tuple(item.path for item in deterministic_options)
                planning_question = (
                    req.message
                    + "\nObjectives to cover: "
                    + ", ".join(item.label for item in deterministic_options)
                )
                retrieval = await _search(
                    search_engine,
                    planning_question,
                    req.active_map_id,
                    settings.max_retrieved_chunks,
                )
                resolved_multiple = True
            else:
                anchored_query = source_anchored_query(
                    req.message,
                    history,
                    documents,
                )
                resolution_messages = build_resolution_messages(
                    message=req.message,
                    history=history,
                    map_name=active_record.display_name,
                    catalog=documents,
                    response_language=response_language,
                )
                try:
                    report_progress("understanding")
                    resolution = await llm.resolve_query(resolution_messages)
                except (LLMUnavailableError, LLMResponseError):
                    logger.warning("Could not resolve ambiguous follow-up", exc_info=True)
                    if anchored_query:
                        anchored_retrieval = await _search(
                            search_engine,
                            anchored_query,
                            req.active_map_id,
                            settings.max_retrieved_chunks,
                        )
                        if not anchored_retrieval.needs_clarification:
                            retrieval = anchored_retrieval
                            planning_question = anchored_query
                else:
                    if resolution.need_clarification:
                        options = validated_document_options(
                            resolution.candidate_document_paths,
                            documents,
                            req.message,
                        )
                        if options:
                            objective_paths = tuple(item.path for item in options)
                            planning_question = (
                                req.message
                                + "\nObjectives to cover: "
                                + ", ".join(item.label for item in options)
                            )
                            retrieval = await _search(
                                search_engine,
                                planning_question,
                                req.active_map_id,
                                settings.max_retrieved_chunks,
                            )
                            resolved_multiple = True
                            anchored_query = ""
                        elif not anchored_query:
                            return ChatResponse(
                                need_clarification=True,
                                clarification_question=clarification_for_options(
                                    req.message,
                                    active_record.display_name,
                                    options,
                                    resolution.clarification_question,
                                ),
                                suggested_queries=[item.label for item in options],
                                active_map_id=req.active_map_id,
                            )
                    else:
                        resolved_retrieval = await _search(
                            search_engine,
                            resolution.resolved_query,
                            req.active_map_id,
                            settings.max_retrieved_chunks,
                        )
                        if not resolved_retrieval.needs_clarification:
                            retrieval = resolved_retrieval
                            planning_question = resolution.resolved_query
                            anchored_query = ""

                    if anchored_query:
                        anchored_retrieval = await _search(
                            search_engine,
                            anchored_query,
                            req.active_map_id,
                            settings.max_retrieved_chunks,
                        )
                        if not anchored_retrieval.needs_clarification:
                            retrieval = anchored_retrieval
                            planning_question = anchored_query

    if retrieval.needs_clarification:
        if req.match_state and request_map_id == req.match_state.map_id:
            status_response = await _match_status(
                req,
                llm,
                response_language,
                match_catalog,
                knowledge_base,
            )
            if status_response:
                return status_response
        return ChatResponse(
            need_clarification=True,
            clarification_question=retrieval.clarification_question,
            suggested_map_ids=list(retrieval.suggested_map_ids),
            active_map_id=retrieval.active_map_id or req.active_map_id,
        )

    intent = resolve_answer_intent(req.message)
    quick_mode = req.response_mode == "quick" and not req.guide_action and not req.guide_state
    offer_complete = False
    if quick_mode:
        from app.response_modes import single_guide

        retrieval = single_guide(retrieval, objective_paths)
    if not guide_context:
        retrieval = expand_procedure(
            retrieval,
            knowledge_base,
            intent,
            req.message,
            requested_paths=search_engine.explicit_document_paths(
                req.message,
                retrieval.active_map_id or request_map_id,
            ),
        )
    detail = guide_context.detail if guide_context else intent.detail
    if resolved_multiple and not intent.explicit_detail:
        detail = "summary"
    complete_procedure = bool(guide_context) or intent.whole_procedure or resolved_multiple
    source_plan = None
    should_plan = (complete_procedure or len(objective_paths) > 1) and not (
        guide_context and guide_context.progress.mode == "finished"
    )
    if should_plan and retrieval.chunks and quick_mode:
        from app.response_modes import quick_procedure

        try:
            retrieval, source_plan, offer_complete, context = quick_procedure(
                knowledge_base,
                retrieval,
                planning_question,
                detail,
                response_language,
                (retrieval.chunks[0].chunk.path,),
            )
        except (PlanCapacityError, DependencyError, ValueError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        offer_complete = offer_complete or len(objective_paths) > 1
    elif should_plan and retrieval.chunks:
        report_progress("planning")
        try:
            context = planning_context(
                knowledge_base,
                retrieval,
                planning_question,
                detail,
                response_language,
                required_ids=tuple(c.chunk.id for c in retrieval.chunks) if guide_context else (),
                phase_mode=bool(guide_context and guide_context.progress.mode == "phase"),
                max_chars=settings.max_plan_context_chars,
                recent_context="\n".join(f"{m.role}: {m.content[:500]}" for m in history[-3:]),
                user_statements="\n".join(
                    [m.content for m in history[-3:] if m.role == "user"] + [req.message]
                ),
                objective_paths=objective_paths,
            )
            dependency_index = DependencyIndex.load(knowledge_base)
            roots = dependency_index.roots(
                context,
                upgraded=bool(
                    re.search(
                        r"upgrad|\bmelhor(?:ar|ad[oa]s?|ias?)\b|eletrific", planning_question, re.I
                    )
                ),
            )
            catalog = {c.id: c for c in context.candidates}
            completed = tuple(
                i
                for i in match_completed
                if i not in roots and catalog[i].path not in context.objective_paths
            )
            if has_completion_claim(context.user_statements):
                completed = tuple(set(completed) | set(await llm.completed_sources(context)))
                completed = dependency_index.complete_requirements(completed, context)
            if dependency_index.covers(roots, catalog):
                source_plan = dependency_index.resolve(roots, context, completed=completed)
            else:
                source_plan = await llm.plan_sources(context)
                original = {s.source_id: s for s in source_plan.steps}
                expanded = dependency_index.resolve(tuple(original), context, completed=completed)
                source_plan = expanded.model_copy(
                    update={"steps": [original.get(s.source_id, s) for s in expanded.steps]}
                )
            if detail == "summary":
                source_plan = compact_summary(source_plan, context)
            violations = plan_violations(source_plan, context)
            if violations:
                raise DependencyError(
                    "Plano de dependências inconsistente: " + " ".join(violations)
                )
            retrieval = apply_plan(
                source_plan,
                context,
                retrieval,
            )
            if len(retrieval.chunks) > settings.max_plan_sources:
                raise PlanCapacityError(
                    "Este procedimento excede o limite de uma resposta. "
                    "Peça uma fase específica para receber todos os detalhes."
                )
        except (PlanCapacityError, DependencyError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except LLMUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except LLMResponseError as error:
            logger.exception("Source planning failed")
            raise HTTPException(
                status_code=502,
                detail="Não foi possível organizar as fontes da resposta. Tente novamente.",
            ) from error
        complete_procedure = True
    contract = build_contract(
        retrieval.chunks,
        detail,
        ordered=complete_procedure,
        brief_completion=bool(guide_context and guide_context.progress.mode == "finished"),
    )
    generation_question = req.message
    if quick_mode:
        match_instructions += (
            "\nQUICK MODE: explain only the supplied guide. Briefly identify prerequisite "
            "procedures mentioned by this source, but do not invent their missing instructions. "
            "Keep the requested detail level and all supplied alternative locations."
        )
    if guide_context and guide_context.navigation and guide_context.progress.mode == "phase":
        generation_question = (
            "Explain the CURRENT PHASE shown in GUIDE MODE with actionable instructions. "
            "The user's navigation action has already been processed by the application. "
            "Do not merely acknowledge it and do not claim the current phase is completed."
        )
    prompt = build_answer_prompt(
        user_message=generation_question,
        history=history,
        scored_chunks=retrieval.chunks,
        knowledge_base=knowledge_base,
        max_context_chars=max(
            settings.max_context_chars,
            sum(len(item.chunk.content) + 600 for item in retrieval.chunks)
            if complete_procedure
            else 0,
        ),
        max_candidate_images=max(
            settings.max_candidate_images,
            settings.max_block_images,
            sum(len(c.chunk.image_ids) for c in retrieval.chunks) if source_plan else 0,
        ),
        response_language=response_language,
        guide_instructions="\n".join(
            filter(
                None,
                [
                    guide_context.instructions if guide_context else "",
                    plan_instructions(source_plan, detail) if source_plan else "",
                    match_instructions,
                ],
            )
        ),
        answer_contract=contract,
    )

    try:
        report_progress("generating")
        generated = (
            await _generate_plan(
                llm,
                source_plan,
                retrieval,
                knowledge_base,
                generation_question,
                history,
                detail,
                response_language,
                (guide_context.instructions if guide_context else "") + "\n" + match_instructions,
                _batch_mode="parallel",
            )
            if source_plan
            else await llm.answer(prompt.messages, contract=contract)
        )
    except PlanCapacityError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except LLMUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except LLMResponseError as error:
        logger.exception("Chat generation failed")
        raise HTTPException(
            status_code=502,
            detail="The model failed to generate a valid answer. Try again.",
        ) from error

    report_progress("finalizing")
    blocks = (
        []
        if generated.need_clarification
        else present_blocks(
            generated.blocks,
            prompt,
            lambda image_id, variant: image_url(image_id, variant),
            _strip_internal_image_references,
            max_images=max(settings.max_block_images, len(prompt.images))
            if source_plan
            else settings.max_block_images,
        )
    )
    if generated.blocks and not blocks and not generated.answer.strip():
        raise HTTPException(status_code=502, detail="The answer did not cite valid sources.")
    selected_assets = (
        []
        if blocks
        else _select_image_assets(
            requested_ids=generated.image_ids,
            available_assets=prompt.images,
            limit=settings.max_response_images,
        )
    )
    relevant_images: list[RelevantImage] = []
    for asset in selected_assets:
        relevant_images.append(
            RelevantImage(
                id=asset.id,
                map_id=asset.map_id,
                path=asset.path,
                caption=asset.caption,
                section=asset.section,
                thumbnail_url=image_url(asset.id, "thumb"),
                full_url=image_url(asset.id, "full"),
            )
        )
    if blocks:
        relevant_images = [image for block in blocks for image in block.images]
    introduction = _strip_internal_image_references(generated.answer)
    answer = "\n\n".join(
        filter(
            None,
            [
                introduction,
                *(
                    f"## {block.title}\n\n{block.body}" if block.title else block.body
                    for block in blocks
                ),
            ],
        )
    )
    sources = [
        SelectedSource(
            chunk_id=item.chunk.id,
            map_id=item.chunk.map_id,
            map_name=item.chunk.map_name,
            path=item.chunk.path,
            section=item.chunk.section_title,
            score=item.score,
        )
        for item in prompt.chunks
    ]
    if source_plan:
        selected_ids = {s.chunk_id for s in sources}
        candidates = {c.id: c for c in context.candidates}
        for step in source_plan.steps:
            for id_ in [*step.supporting_ids, *step.grouped_source_ids]:
                if id_ not in selected_ids:
                    c = candidates[id_]
                    sources.append(
                        SelectedSource(
                            chunk_id=c.id,
                            map_id=c.map_id,
                            map_name=c.map_name,
                            path=c.path,
                            section=c.section_title,
                            score=1.0,
                        )
                    )
                    selected_ids.add(id_)

    return ChatResponse(
        answer=answer,
        introduction=introduction,
        blocks=blocks,
        guide=guide_context.progress if guide_context else None,
        need_clarification=generated.need_clarification,
        clarification_question=generated.clarification_question,
        sources=sources,
        relevant_images=relevant_images,
        active_map_id=retrieval.active_map_id,
        offer_complete=offer_complete,
    )
