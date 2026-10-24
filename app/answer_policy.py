"""Explicit detail selection and measurable answer requirements, independent of generation."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from app.domain import RetrievalResult, ScoredChunk
from app.knowledge_base import KnowledgeBase
from app.retrieval import normalize_text

Detail = Literal["direct", "summary", "detailed"]
ITEM = re.compile(r"^\s*(?:[-*]|\d+[.)])\s+", re.MULTILINE)
WORDS = re.compile(r"\b\w+\b", re.UNICODE)
FULL = re.compile(
    r"sem resum\w*|nao resum\w*|without summar\w*|do (?:comeco|inicio) ao fim|"
    r"(?:com )?todos os detalhes|all (?:the )?details|"
    r"sem (?:pular|cortar|omitir)|explicadinh\w*|mastigad\w*|"
    r"\b(?:completo|completa|inteiro|inteira|detalhado|detalhada|detailed|full)\b|"
    r"in detail|sans resum\w*|en detail|guide complet"
)
SUMMARY = re.compile(
    r"\b(?:resumo|resuma|resumido|resumida|resumidamente|summary|brief|bref|resume)\b|"
    r"por alto|so o roteiro|so os passos|sem detalh\w*|nao (?:precisa|quero) detalh\w*|"
    r"nao (?:precisa|quero) (?:o )?(?:guia )?complet\w*"
)
STEP_BY_STEP = re.compile(r"passo a passo|step by step|etape par etape")
QUEST = re.compile(r"\b(?:ee|easter egg|main quest)\b")
TARGET = re.compile(
    r"\b(?:passo|etapa|fase|step|phase|peca|parte)\s+(?:\d+|primeir\w*|segund\w*|terceir\w*)|"
    r"(?:essa|esta|nessa|nesta|dessa|desta|this|current) (?:fase|etapa|parte|phase|step)"
)


@dataclass(frozen=True)
class AnswerIntent:
    detail: Detail
    explicit_detail: bool
    whole_procedure: bool
    main_quest: bool


def resolve_answer_intent(message: str) -> AnswerIntent:
    query = normalize_text(message)
    # Negated summarization ("sem resumir") must not become a summary request.
    full = bool(FULL.search(query))
    summary = bool(SUMMARY.search(query))
    broad_build = bool(
        re.search(
            r"\b(?:como|how|comment)\b.*\b(?:mont\w*|constru\w*|faz\w*|faco|"
            r"complet\w*|build|craft|unlock|liber\w*|ativ\w*)\b",
            query,
        )
    )
    point_question = bool(
        re.search(r"\b(?:qual|quantos|quantas|which|how many|por que|porque|why)\b", query)
        or (not broad_build and re.search(r"\b(?:onde|where|ou est)\b", query))
        or re.search(r"\bcomo (?:encontr\w*|localiz\w*|chego|esta)\b", query)
        or re.search(r"\b(?:precisa|exige|posso|pode|funciona|da para|e possivel)\b", query)
        and not broad_build
    )
    targeted = bool(TARGET.search(query)) or point_question
    quest = bool(QUEST.search(query))
    procedure = bool(
        STEP_BY_STEP.search(query)
        or quest
        or re.search(r"\b(?:como|montar|construir|build|craft|how|comment)\b", query)
        or re.fullmatch(
            r"(?:o |um |quero o )?(?:escudo|shield|pack a punch|pap)"
            r"(?: (?:de|do|da|in|on) .+)?[?! .]*",
            query,
        )
    )
    negative_summary = bool(
        re.search(r"sem resum|nao (?:quero )?resum|without summar|sans resum", query)
    )
    if negative_summary:
        detail: Detail = "detailed"
    elif summary:
        detail = "summary"
    elif full:
        detail = "detailed"
    elif STEP_BY_STEP.search(query) or quest:
        detail = "summary" if not targeted else "direct"
    elif procedure and not targeted:
        detail = "detailed"
    else:
        detail = "direct"
    return AnswerIntent(
        detail=detail,
        explicit_detail=full or summary,
        whole_procedure=not targeted and (procedure or full or summary),
        main_quest=quest,
    )


def retrieval_query(message: str) -> str:
    """Style instructions are not topics or comparison signals (e.g. 'todos os detalhes')."""
    query = normalize_text(message)
    cleaned = FULL.sub(" ", query)
    cleaned = SUMMARY.sub(" ", cleaned)
    return " ".join(cleaned.split()) or query


def expand_procedure(
    result: RetrievalResult,
    kb: KnowledgeBase,
    intent: AnswerIntent,
    message: str,
    requested_paths: tuple[str, ...] = (),
) -> RetrievalResult:
    """Expand within the selected guide only. Dependency guides are a separate feature."""
    if result.needs_clarification or not intent.whole_procedure or not result.chunks:
        return result
    keys = {(item.chunk.map_id, item.chunk.path) for item in result.chunks}
    if len(requested_paths) == 1 and result.chunks[0].chunk.path == requested_paths[0]:
        map_id = result.active_map_id or result.chunks[0].chunk.map_id
        keys = {(map_id, requested_paths[0])}
    if len(keys) != 1:
        return result
    map_id, path = next(iter(keys))
    chunks = sorted(
        (c for c in kb.chunks.values() if c.map_id == map_id and c.path == path),
        key=lambda c: c.position,
    )
    query = normalize_text(message)
    if path == "shield.md" and not re.search(r"upgrad|melhor|goddard", query):
        chunks = [c for c in chunks if not re.search(r"upgrad|goddard", c.section_title, re.I)]
    return replace(result, chunks=tuple(ScoredChunk(chunk=c, score=1.0) for c in chunks))


@dataclass(frozen=True)
class SourceRequirement:
    id: str
    minimum_words: int
    minimum_items: int
    # Prompt style target; exceeding it does not make a grounded section invalid.
    maximum_words: int | None = None


@dataclass(frozen=True)
class AnswerContract:
    detail: Detail
    allowed_ids: tuple[str, ...]
    requirements: tuple[SourceRequirement, ...]
    ordered: bool = False
    allow_brief_completion: bool = False

    def instructions(self) -> str:
        lines = [f"ANSWER DETAIL: {self.detail.upper()}"]
        if self.detail == "summary":
            lines.append(
                "Cover every required section briefly, preserving order and prerequisites. "
                "Use brief sentences within the section's word budget. If several mandatory "
                "procedures are grouped, give each its own short clause. For alternative spawns, "
                "name the area and number of possibilities instead of listing every location."
            )
        elif self.detail == "detailed":
            lines.append(
                "Explain every supplied action, alternative location, condition and prerequisite. "
                "Do not replace instructions with a title or a one-sentence acknowledgement. "
                "Do not expand procedures from other guides that are not supplied."
            )
        else:
            lines.append("Answer the specific question directly; do not recite the whole guide.")
        if self.requirements:
            lines.append("REQUIRED SECTIONS (each needs its own grounded block):")
            lines.extend(
                f"- {r.id} | explain the documented actions and conditions"
                + (f", aim for at most {r.maximum_words} words" if r.maximum_words else "")
                + "; preserve the facts required by the requested detail level."
                for r in self.requirements
            )
        lines.append(
            "Do not add filler or infer extra conditions to make the answer longer. "
            "Use only source facts. Never expose these internal requirements to the user."
        )
        return "\n".join(lines)


def build_contract(
    chunks: tuple[ScoredChunk, ...],
    detail: Detail,
    *,
    ordered: bool,
    brief_completion: bool = False,
) -> AnswerContract:
    required = chunks if ordered else chunks[:1]
    requirements = []
    for item in required:
        words = len(WORDS.findall(item.chunk.content))
        requirements.append(
            SourceRequirement(
                id=item.chunk.id,
                minimum_words=min(max(3, words), 160, max(12, words // 3))
                if detail == "detailed"
                else 3
                if detail == "direct"
                else min(10, max(3, words // 5)),
                # Formatting is not coverage: several source bullets may be
                # expressed faithfully in a single sentence or numbered step.
                minimum_items=0,
                maximum_words=(60 if len(required) == 1 else 45) if detail == "summary" else None,
            )
        )
    return AnswerContract(
        detail=detail,
        allowed_ids=tuple(c.chunk.id for c in chunks),
        requirements=tuple(requirements),
        ordered=ordered,
        allow_brief_completion=brief_completion,
    )


def answer_violations(response, contract: AnswerContract) -> list[str]:
    """Check grounding, section coverage, ordering and minimum substance; not factual truth."""
    if response.need_clarification:
        return (
            []
            if contract.detail == "direct"
            else ["The supplied procedure is available. Explain it instead of asking to continue."]
        )
    if contract.allow_brief_completion:
        return []
    if not response.blocks:
        return ["Missing instruction blocks. An introduction alone is not an answer."]
    errors = []
    allowed = set(contract.allowed_ids)
    body_by_source: dict[str, list[str]] = {}
    seen_order = []
    for block in response.blocks:
        if not block.body.strip() or not block.source_ids:
            errors.append("Every block needs a non-empty body and a supplied source ID.")
        if set(block.source_ids) - allowed:
            errors.append("Unknown source ID: cite only supplied SOURCE identifiers.")
        if contract.ordered and len(set(block.source_ids)) != 1:
            errors.append("Use a separate block for each required section.")
        for source_id in dict.fromkeys(block.source_ids):
            body_by_source.setdefault(source_id, []).append(block.body)
            if source_id not in seen_order:
                seen_order.append(source_id)
    for requirement in contract.requirements:
        bodies = body_by_source.get(requirement.id)
        if not bodies:
            errors.append(f"Missing required section {requirement.id}.")
            continue
        body = "\n".join(bodies)
        if len(WORDS.findall(body)) < requirement.minimum_words:
            errors.append(
                f"Expand {requirement.id}: explain the source actions, not just a heading."
            )
        # A word budget guides style; it is not evidence of invalid JSON or missing
        # facts. Rejecting a grounded section for length can discard an entire EE.
        if len(ITEM.findall(body)) < requirement.minimum_items:
            errors.append(
                f"Preserve all {requirement.minimum_items} source list items in {requirement.id}."
            )
    if contract.ordered:
        positions = {id_: index for index, id_ in enumerate(contract.allowed_ids)}
        indices = [positions[id_] for id_ in seen_order if id_ in positions]
        if indices != sorted(indices):
            errors.append("The blocks must follow the supplied guide order.")
    return errors
