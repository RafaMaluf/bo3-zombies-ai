"""Validate reviewed relations against canonical source text, images and ordering."""

import json

from app.config import settings
from app.guide_dependencies import DependencyError, DependencyIndex, compact_summary, map_catalog
from app.knowledge_base import KnowledgeBase
from app.source_planning import PlanningContext, plan_violations


def main():
    kb = KnowledgeBase(settings.maps_dir)
    index = DependencyIndex.load(kb)
    all_sources = {c.id: c for mid in kb.maps for c in map_catalog(kb, mid)}
    if set(index.source_notes) - all_sources.keys():
        raise DependencyError("Nota revisada aponta para fonte inexistente.")
    for view in index.source_views:
        if view["id"] not in all_sources or not view["id"].startswith(view["parent_id"] + ":view-"):
            raise DependencyError("Recorte revisado não pertence à fonte declarada.")
    for alias in index.document_aliases:
        map_id, path = alias.split(":", 1)
        canonical = index.canonical_document_path(map_id, path)
        if not any(c.path == canonical and c.map_id == map_id for c in all_sources.values()):
            raise DependencyError("Redirecionamento sem documento canônico.")
    for key, scopes in index.scope_aliases.items():
        if any(not aliases or key + ":" + scope not in index.root_sets
               for scope, aliases in scopes.items()):
            raise DependencyError("Nome de equipamento sem escopo revisado correspondente.")
    for id_ in index.reviewed_sources:
        index.validate_source(id_, all_sources)
    for rule in index.requirements:
        if rule.kind not in {"requires", "recommended", "illustrates"}:
            raise DependencyError("Tipo de relação inválido.")
        if len(rule.evidence) < 12 or rule.evidence not in all_sources[rule.consumer].content:
            raise DependencyError("Relação sem evidência textual.")
        if any(all_sources[s].map_id != all_sources[rule.consumer].map_id for s in rule.sources):
            raise DependencyError("Relação cruza mapas.")
    largest_plans: dict[str, int] = {}
    for roots in index.root_sets.values():
        if not roots:
            raise DependencyError("Escopo revisado vazio.")
        map_id = all_sources[roots[0]].map_id
        context = PlanningContext(map_catalog(kb, map_id), (), [])
        plan = index.resolve(roots, context)
        errors = plan_violations(plan, context)
        compact = compact_summary(plan, context)
        errors.extend(plan_violations(compact, context))
        def covered(candidate):
            return {id_ for s in candidate.steps
                    for id_ in [s.source_id, *s.supporting_ids, *s.grouped_source_ids]}
        if covered(plan) != covered(compact):
            errors.append("Resumo alterou a cobertura de fontes obrigatórias/ilustrações.")
        if errors:
            raise DependencyError(" ".join(errors))
        largest_plans[map_id] = max(largest_plans.get(map_id, 0), len(plan.steps))
    print(
        json.dumps(
            {
                "status": "ok",
                "catalog_sources": len(all_sources),
                "reviewed_sources": len(index.reviewed_sources),
                "reviewed_requirements": len(index.requirements),
                "root_scopes": len(index.root_sets),
                "reviewed_documents": len(index.reviewed),
                "reviewed_maps": len({s.split(":", 1)[0] for s in index.reviewed}),
                "source_views": len(index.source_views),
                "largest_plans_by_map": largest_plans,
            }
        )
    )


if __name__ == "__main__":
    main()
