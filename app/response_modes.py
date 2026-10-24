"""Single-guide scope without sacrificing the selected procedure or image groups."""

import re
from dataclasses import replace

from app.guide_dependencies import DependencyIndex
from app.source_planning import PlannedSource, SourcePlan, apply_plan, planning_context


def single_guide(result, requested_paths=()):
    if not result.chunks:
        return result
    available = {item.chunk.path for item in result.chunks}
    path = next((p for p in requested_paths if p in available), result.chunks[0].chunk.path)
    map_id = result.active_map_id or result.chunks[0].chunk.map_id
    return replace(
        result,
        chunks=tuple(c for c in result.chunks if c.chunk.path == path and c.chunk.map_id == map_id),
    )


def quick_procedure(kb, result, question, detail, language, objective_paths):
    """Use reviewed relationships locally; never send dependency guides to a model."""
    context = planning_context(
        kb, result, question, detail, language, objective_paths=objective_paths
    )
    index = DependencyIndex.load(kb)
    roots = index.roots(
        context,
        upgraded=bool(
            re.search(r"upgrad|\bmelhor(?:ar|ad[oa]s?|ias?)\b|eletrific", question, re.I)
        ),
    )
    catalog = {c.id: c for c in context.candidates}
    path = result.chunks[0].chunk.path
    if not index.covers(roots, catalog):
        return result, None, len(objective_paths) > 1, context
    expanded = index.resolve(roots, context)
    selected = []
    for step in expanded.steps:
        if catalog[step.source_id].path != path:
            continue
        selected.append(
            PlannedSource(
                source_id=step.source_id,
                role="objective",
                condition=step.condition,
                supporting_ids=[i for i in step.supporting_ids if catalog[i].path == path],
                grouped_source_ids=[i for i in step.grouped_source_ids if catalog[i].path == path],
            )
        )
    if not selected:
        return result, None, len(objective_paths) > 1, context
    plan = SourcePlan(steps=selected)
    offer = len(objective_paths) > 1 or any(
        catalog[id_].path != path
        for step in expanded.steps
        for id_ in [step.source_id, *step.supporting_ids, *step.grouped_source_ids]
    )
    scoped = replace(context, required_ids=tuple(s.source_id for s in selected))
    return apply_plan(plan, scoped, result), plan, offer, scoped
