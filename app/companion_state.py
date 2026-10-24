"""Deterministic objective catalog and match transitions. No model calls or I/O."""

import hashlib
import json

from app.companion_models import CompanionCatalog, MatchState, Objective, ProgressChange
from app.domain import RetrievalResult, ScoredChunk
from app.guidance import ORIGINS_TITLES, guide_chunks
from app.guide_dependencies import DependencyIndex
from app.source_planning import planning_context


def build_catalog(kb, map_id: str, language="pt-BR") -> CompanionCatalog:
    if map_id not in kb.maps:
        raise ValueError("Mapa desconhecido.")
    paths = {c.path for c in kb.chunks.values() if c.map_id == map_id and c.category == "main_ee"}
    if len(paths) != 1:
        raise ValueError("Este mapa não possui um Easter Egg principal único na base.")
    path = paths.pop()
    phases = guide_chunks(kb, map_id, path)
    context = planning_context(
        kb,
        RetrievalResult(
            chunks=tuple(ScoredChunk(c, 1) for c in phases),
            active_map_id=map_id,
            explicit_map_ids=(map_id,),
            needs_clarification=False,
            clarification_question="",
            suggested_map_ids=(),
        ),
        "Explain the main Easter Egg",
        "detailed",
        language,
        required_ids=tuple(c.id for c in phases),
    )
    index = DependencyIndex.load(kb)
    plan = index.resolve(tuple(c.id for c in phases), context)
    essential = {s.source_id for s in plan.steps}
    selected = set(essential)
    for document_path in kb.maps[map_id].document_paths:
        roots = index.root_sets.get(f"{map_id}:{document_path}", ())
        if not roots or any(i in selected for i in roots):
            continue
        extra = index.resolve(tuple(roots), context)
        for step in extra.steps:
            if step.source_id not in selected:
                plan.steps.append(step)
                selected.add(step.source_id)
    sources = {c.id: c for c in context.candidates}
    main_ids = {c.id for c in phases}
    groups = {}
    for step in plan.steps:
        source = sources[step.source_id]
        # Main quest phases remain separate. Related equipment sections form a
        # single executable objective, with every piece/photo retained.
        key = step.source_id if step.source_id in main_ids else f"{map_id}:equipment:{source.path}"
        groups[step.source_id] = key

    def assemble():
        objectives = {}
        for step in plan.steps:
            source = sources[step.source_id]
            key = groups[step.source_id]
            if key not in objectives:
                title = source.section_title
                if step.source_id in main_ids and map_id == "origins":
                    titles = ORIGINS_TITLES.get(language.split("-")[0], ORIGINS_TITLES["en"])
                    title = titles[list(c.id for c in phases).index(step.source_id)]
                objectives[key] = Objective(
                    id=key,
                    title=title,
                    source_ids=[],
                    main=step.source_id in main_ids,
                    condition=step.condition,
                    optional=step.source_id not in essential,
                )
            obj = objectives[key]
            if step.source_id in essential:
                obj.optional = False
            obj.source_ids.extend([step.source_id, *step.supporting_ids])
            # A shared objective reached unconditionally is not conditional.
            if not step.condition:
                obj.condition = ""
        for rule in index.requirements:
            if rule.kind != "requires" or rule.condition or rule.consumer not in groups:
                continue
            obj = objectives[groups[rule.consumer]]
            for source_id in rule.sources:
                other = groups.get(source_id)
                if other and other != obj.id and other not in obj.requires:
                    obj.requires.append(other)
        for obj in objectives.values():
            obj.source_ids = list(dict.fromkeys(obj.source_ids))
        return list(objectives.values())

    objectives = assemble()

    # Collapsing equipment sections can introduce a cycle even though the
    # source graph is acyclic. Split such documents instead of inventing order.
    def cyclic(items):
        remaining = {o.id: set(o.requires) for o in items}
        while remaining:
            ready = {key for key, needs in remaining.items() if not needs & remaining.keys()}
            if not ready:
                return True
            remaining = {k: v for k, v in remaining.items() if k not in ready}
        return False

    if cyclic(objectives):
        groups = {step.source_id: step.source_id for step in plan.steps}
        objectives = assemble()
    if cyclic(objectives):
        raise ValueError("Os objetivos possuem dependências circulares.")
    # Requiring one section does not prove that a whole grouped recipe is complete.
    core: dict[str, set[str]] = {}
    for step in plan.steps:
        core.setdefault(groups[step.source_id], set()).add(step.source_id)
    for objective in objectives:
        closure = set(objective.source_ids)
        while True:
            previous = set(closure)
            for rule in index.requirements:
                if rule.kind == "requires" and not rule.condition and rule.consumer in closure:
                    closure.update(rule.sources)
            if closure == previous:
                break
        objective.implies = [
            o.id
            for o in objectives
            if o.id != objective.id and not o.condition and core[o.id] <= closure
        ]
    number = 0
    for objective in objectives:
        if objective.main:
            number += 1
            objective.number = number
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                (
                    o.id,
                    o.source_ids,
                    o.requires,
                    o.implies,
                    o.condition,
                    o.optional,
                    o.main,
                    [(sources[i].content, sources[i].image_ids) for i in o.source_ids],
                )
                for o in objectives
            ],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    return CompanionCatalog(
        map_id=map_id,
        map_name=kb.maps[map_id].display_name,
        document_path=path,
        version=fingerprint,
        objectives=objectives,
    )


def validate_state(state: MatchState, catalog: CompanionCatalog) -> None:
    ids = {o.id for o in catalog.objectives}
    if state.map_id != catalog.map_id or state.catalog_version != catalog.version:
        raise ValueError("O guia mudou desde a partida salva. Inicie uma nova partida.")
    used = (
        set(state.statuses) | set(state.applicability) | set(state.partial) | set(state.return_to)
    )
    if state.focus:
        used.add(state.focus)
    if (
        used - ids
        or len(state.partial) > len(ids)
        or any(len(v) > 500 for v in state.partial.values())
    ):
        raise ValueError("Estado contém objetivos ou detalhes desconhecidos.")
    by_id = {o.id: o for o in catalog.objectives}
    if any(not by_id[i].condition and not value for i, value in state.applicability.items()):
        raise ValueError("Um objetivo obrigatório não pode ser descartado.")


def applicable(state, objective):
    return state.applicability.get(objective.id, True)


def missing_requirements(state, catalog, objective_id):
    by_id = {o.id: o for o in catalog.objectives}
    return [
        i
        for i in by_id[objective_id].requires
        if applicable(state, by_id[i]) and state.statuses.get(i) != "complete"
    ]


def next_objective(state, catalog):
    main = [o for o in catalog.objectives if o.main]
    if main and all(state.statuses.get(o.id) == "complete" for o in main):
        return None
    for objective in catalog.objectives:
        if (
            not objective.optional
            and applicable(state, objective)
            and state.statuses.get(objective.id) != "complete"
        ):
            if not missing_requirements(state, catalog, objective.id):
                return objective.id
    return None


def affected_completions(state, catalog, reset):
    affected = set(reset)
    while True:
        previous = set(affected)
        affected.update(
            o.id
            for o in catalog.objectives
            if set(o.requires) & affected and state.statuses.get(o.id) == "complete"
        )
        if affected == previous:
            return sorted(affected - set(reset))


def transition(
    state: MatchState, catalog: CompanionCatalog, change: ProgressChange, *, confirmed=False
) -> MatchState:
    validate_state(state, catalog)
    by_id = {o.id: o for o in catalog.objectives}
    used = (
        set(change.completed)
        | set(change.pending)
        | set(change.applicability)
        | set(change.partial)
    )
    if change.focus:
        used.add(change.focus)
    reset = set(change.pending) | set(change.partial)
    navigate = bool(change.completed or reset or change.from_start or change.applicability)
    if used - by_id.keys() or set(change.completed) & reset:
        raise ValueError("Atualização inválida dos objetivos.")
    if any(not by_id[i].condition for i in change.applicability):
        raise ValueError("Aplicabilidade só pode alterar objetivos condicionais.")
    if change.intent in {"question", "consult", "help", "unclear", "status"} and (
        change.completed
        or change.pending
        or change.from_start
        or change.applicability
        or change.partial
        or change.player_count is not None
    ):
        raise ValueError("Uma consulta não pode alterar conclusões.")
    result = state.model_copy(deep=True)
    affected = affected_completions(state, catalog, reset)
    if affected and not confirmed:
        result.confirmation = change
        return result
    result.confirmation = None
    if change.player_count is not None and change.player_count != result.player_count:
        result.player_count = change.player_count
        result.applicability = {}  # Revisit route eligibility; retain actual completed actions.
    if change.from_start:
        result.statuses = {o.id: "pending" for o in catalog.objectives}
        result.partial = {}
        result.return_to = []
    for i in [*reset, *(affected if confirmed else [])]:
        result.statuses[i] = "pending"
    # Derive only unconditional reviewed prerequisites, never earlier indices.
    completed = set(change.completed)
    while True:
        previous = set(completed)
        completed.update(
            i
            for goal in tuple(completed)
            for i in by_id[goal].implies
            if not by_id[i].condition and i not in reset
        )
        if completed == previous:
            break
    for i in completed:
        result.statuses[i] = "complete"
        result.partial.pop(i, None)
    result.applicability.update(change.applicability)
    result.partial.update(change.partial)
    if change.focus:
        if (change.intent == "help" or by_id[change.focus].optional) and (
            result.focus and result.focus != change.focus and change.intent != "consult"
        ):
            if len(result.return_to) >= 12:
                raise ValueError("Conclua a ajuda atual antes de abrir outra.")
            result.return_to.append(result.focus)
        result.focus = change.focus
    elif (
        result.focus in completed
        or change.from_start
        or (result.focus and result.applicability.get(result.focus) is False)
        or (not result.focus and navigate)
    ):
        result.focus = None
        while result.return_to and not result.focus:
            candidate = result.return_to.pop()
            if result.statuses.get(candidate) != "complete":
                result.focus = candidate
        result.focus = result.focus or next_objective(result, catalog)
    if not result.focus and (result.stage != "position" or navigate):
        result.stage = "finished"
    elif result.focus:
        result.stage = "active"
    result.revision += 1
    validate_state(result, catalog)
    return result
