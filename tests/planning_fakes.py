"""Planner fake for transport/presentation tests, not planning assertions."""

import json

from app.source_planning import PlannedSource, SourcePlan


class SeedPlanner:
    async def completed_sources(self, context):
        return ()

    async def plan_sources(self, context):
        task = json.loads(context.messages[-1]["content"].split("\n\nMAP CATALOG", 1)[0][5:])
        ids = context.required_ids or tuple(
            context.candidates[int(i)].id for i in task["seed_sources"]
        )
        if len(context.objective_paths) > 1:
            ids = tuple(
                dict.fromkeys(
                    [*ids, *(c.id for c in context.candidates if c.path in context.objective_paths)]
                )
            )
        return SourcePlan(steps=[PlannedSource(source_id=i, role="objective") for i in ids])
