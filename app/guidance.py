"""Deterministic guide navigation. Only explicit user actions change progress."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal, cast

from app.answer_policy import Detail, resolve_answer_intent
from app.chunking import extract_image_paths, remove_image_reference_lines
from app.domain import KnowledgeChunk, RetrievalResult, ScoredChunk
from app.knowledge_base import KnowledgeBase
from app.retrieval import SearchEngine, normalize_text
from app.schemas import ChatRequest, GuidePhase, GuideProgress, GuideState

INLINE_STEP = re.compile(r"^Step (?:one|two|three|four|five|six|seven|eight):", re.MULTILINE)
ORIGINS_TITLES = {
    "pt": [
        "Preparação",
        "Construir e melhorar os quatro cajados",
        "Posicionar os cajados",
        "Abrir a passagem com o G-Strike",
        "Enviar o Maxis Drone e enfrentar os Panzers",
        "Recuperar o Maxis Drone",
        "Melhorar os punhos",
        "Libertar Samantha",
        "Finalizar",
    ],
    "en": [
        "Preparation",
        "Build and upgrade all four staffs",
        "Place the staffs",
        "Open the passage with G-Strike",
        "Send the Maxis Drone and defeat the Panzers",
        "Recover the Maxis Drone",
        "Upgrade the fists",
        "Free Samantha",
        "Finish",
    ],
    "fr": [
        "Préparation",
        "Construire et améliorer les quatre bâtons",
        "Placer les bâtons",
        "Ouvrir le passage avec le G-Strike",
        "Envoyer le Maxis Drone et vaincre les Panzers",
        "Récupérer le Maxis Drone",
        "Améliorer les poings",
        "Libérer Samantha",
        "Terminer",
    ],
}


@dataclass(frozen=True)
class GuideContext:
    progress: GuideProgress
    retrieval: RetrievalResult
    instructions: str
    detail: Detail = "detailed"
    navigation: bool = False


def guide_chunks(kb: KnowledgeBase, map_id: str, path: str) -> tuple[KnowledgeChunk, ...]:
    chunks = sorted(
        (c for c in kb.chunks.values() if c.map_id == map_id and c.path == path),
        key=lambda c: c.position,
    )
    result: list[KnowledgeChunk] = []
    raw_sections: dict[str, str] = {}
    if map_id == "origins" and chunks:
        # KnowledgeChunk.content intentionally strips image reference lines.
        # Split the original section to retain the exact image-to-step binding.
        document = (kb.maps[map_id].directory / path).read_text("utf-8")
        for section in re.split(r"^##\s+", document, flags=re.MULTILINE)[1:]:
            title, _, body = section.partition("\n")
            raw_sections[title.strip()] = body.strip()
    for chunk in chunks:
        if (
            "cheat sheet" in chunk.section_title.casefold()
            or "cheatsheet" in chunk.section_title.casefold()
            or "summary" in chunk.section_title.casefold()
        ):
            continue
        raw_content = raw_sections.get(chunk.section_title, chunk.content)
        matches = list(INLINE_STEP.finditer(raw_content)) if map_id == "origins" else []
        if not matches:
            result.append(chunk)
            continue
        offsets = [0, *(m.start() for m in matches), len(raw_content)]
        for index, (start, end) in enumerate(zip(offsets[:-1], offsets[1:], strict=True)):
            content = raw_content[start:end].strip()
            paths = set(extract_image_paths(content))
            image_ids = tuple(i for i in chunk.image_ids if kb.images[i].path in paths)
            result.append(
                replace(
                    chunk,
                    id=f"{chunk.id}:phase-{index}",
                    content=remove_image_reference_lines(content),
                    section_title="Preparation" if index == 0 else content.splitlines()[0],
                    position=index,
                    image_ids=image_ids,
                )
            )
    return tuple(result)


def prepare_guidance(
    req: ChatRequest,
    kb: KnowledgeBase,
    search: SearchEngine,
    language: str,
) -> GuideContext | None:
    if req.guide_action == "stop":
        return None
    map_id = req.active_map_id
    if map_id not in kb.maps:
        explicit = search.explicit_map_ids(req.message)
        map_id = explicit[0] if len(explicit) == 1 else None
    state = req.guide_state.model_copy(deep=True) if req.guide_state else None
    if state and state.map_id != map_id:
        state = None
    new_guide = state is None
    query = normalize_text(req.message)
    intent = resolve_answer_intent(req.message)
    action = req.guide_action
    if state:
        paths = search.explicit_document_paths(req.message, map_id)
        if not action and paths and state.document_path not in paths:
            return None
        if not action and not intent.main_quest and re.search(r"\b(?:pack a punch|pap)\b", query):
            # Pack-a-Punch is a generic catalog term, not a filename alias.
            # A new objective must not be trapped inside the active EE phase.
            return None
        if not action:
            if query in {"conclui", "ja fiz isso", "conclui esta fase", "done", "termine"}:
                action = "complete"
            elif query in {"proximo", "proxima", "next", "suivant"}:
                action = "jump"
                req = req.model_copy(update={"guide_phase": state.phase + 1})
            elif query in {"ver roteiro", "roteiro", "overview", "plan"}:
                action = "overview"
            elif intent.explicit_detail and intent.whole_procedure:
                action = "full" if intent.detail == "detailed" else "overview"
            elif intent.main_quest and intent.whole_procedure:
                action = "full" if intent.detail == "detailed" else "overview"
    else:
        if action:
            raise ValueError("A guide action requires a valid guide for the active map.")
        broad_quest = intent.main_quest and intent.whole_procedure
        if not map_id or not broad_quest:
            return None
        main_paths = {
            c.path for c in kb.chunks.values() if c.map_id == map_id and c.category == "main_ee"
        }
        requested = set(search.explicit_document_paths(req.message, map_id))
        if requested - main_paths or len(main_paths) != 1:
            return None
        state = GuideState(map_id=map_id, document_path=next(iter(main_paths)))
        action = "full" if intent.detail == "detailed" else "overview"

    assert state is not None
    if (new_guide and re.search(r"\bsolo\b", query)) or re.search(
        r"\b(?:estou|jogando|vou jogar) solo\b", query
    ):
        state.player_count = 1
    else:
        count = re.search(r"\bsomos ([1-4])\b", query)
        if new_guide and not count:
            count = re.search(r"\b([1-4]) (?:jogadores|players|pessoas|joueurs)\b", query)
        if count:
            state.player_count = int(count.group(1))
    canonical = [
        c for c in kb.chunks.values() if c.map_id == state.map_id and c.path == state.document_path
    ]
    if not canonical or any(c.category != "main_ee" for c in canonical):
        raise ValueError("Unknown main quest guide.")
    phases = guide_chunks(kb, state.map_id, state.document_path)
    if len(phases) < 6:
        if req.guide_action:
            raise ValueError("This guide does not support phase navigation.")
        return None
    if state.phase >= len(phases):
        raise ValueError("Unknown guide phase.")
    state.completed_phases = sorted(set(i for i in state.completed_phases if 0 <= i < len(phases)))
    mode = "phase"
    if action == "start":
        state.phase = 0
    elif action == "jump":
        if req.guide_phase is None or req.guide_phase >= len(phases):
            raise ValueError("Unknown guide phase.")
        state.phase = req.guide_phase
    elif action == "complete":
        state.completed_phases = sorted(set([*state.completed_phases, state.phase]))
        if state.phase + 1 < len(phases):
            state.phase += 1
        else:
            mode = "finished"
    elif action in {"overview", "full"}:
        mode = action
    # Button labels and game terms are poor language-detection inputs. Preserve
    # the guide's established locale during navigation actions.
    if action and state.language:
        language = state.language
    state.language = language
    detail: Detail = (
        "summary"
        if mode == "overview"
        else "detailed"
        if mode == "full" or action
        else intent.detail
    )
    labels = ORIGINS_TITLES.get(language[:2], ORIGINS_TITLES["en"])
    titles = (
        labels
        if state.map_id == "origins" and len(phases) == len(labels)
        else [c.section_title for c in phases]
    )
    progress = GuideProgress(
        state=state,
        mode=cast(Literal["overview", "phase", "full", "finished"], mode),
        phases=[
            GuidePhase(index=i, title=title, completed=i in state.completed_phases)
            for i, title in enumerate(titles)
        ],
    )
    selected = phases if mode in {"overview", "full"} else (phases[state.phase],)
    images_allowed = mode != "finished"
    selected = tuple(
        replace(c, image_ids=() if not images_allowed else c.image_ids) for c in selected
    )
    instructions = (
        f"GUIDE MODE: {mode}\nCURRENT PHASE: {state.phase + 1}/{len(phases)}\n"
        f"PLAYERS: {state.player_count or 'unknown; explain relevant solo/co-op differences'}\n"
        f"COMPLETED PHASE INDICES (zero-based): {state.completed_phases}\n"
        "Never imply a phase is completed unless listed as completed.\n"
    )
    if mode == "overview":
        instructions += (
            "Give prerequisites and a short complete roadmap, one brief block per phase. "
            "Do not give the full walkthrough yet. The UI offers start, jump and full guide.\n"
        )
    elif mode == "full":
        instructions += (
            "Explain every supplied phase in order, with one or more blocks per phase.\n"
        )
    elif mode == "finished":
        instructions += (
            "The user explicitly completed the final phase. Acknowledge completion briefly.\n"
        )
    else:
        instructions += (
            "Explain only the current phase or answer the user's question about it. "
            "Do not advance or request permission to continue; the UI has navigation controls. "
            "If a prerequisite procedure is absent from the excerpts, say so "
            "instead of inventing it.\n"
        )
    return GuideContext(
        progress=progress,
        retrieval=RetrievalResult(
            chunks=tuple(ScoredChunk(chunk=c, score=1.0) for c in selected),
            active_map_id=state.map_id,
            explicit_map_ids=(state.map_id,),
            needs_clarification=False,
            clarification_question="",
            suggested_map_ids=(),
        ),
        instructions=instructions,
        detail=detail,
        navigation=bool(action),
    )
