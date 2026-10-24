"""Versioned, evidence-backed requirements; no map-specific routing in the resolver."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path

from app.domain import KnowledgeChunk
from app.guidance import guide_chunks


class DependencyError(ValueError):
    pass


def source_digest(chunk) -> str:
    return hashlib.sha256(
        json.dumps(
            [
                chunk.map_id,
                chunk.path,
                chunk.category,
                chunk.section_title,
                chunk.content,
                chunk.image_ids,
            ],
            ensure_ascii=False,
        ).encode()
    ).hexdigest()


def map_catalog(kb, map_id):
    chunks: list[KnowledgeChunk] = []
    for path in kb.maps[map_id].document_paths:
        document = [c for c in kb.chunks.values() if c.map_id == map_id and c.path == path]
        chunks.extend(
            guide_chunks(kb, map_id, path)
            if any(c.category == "main_ee" for c in document)
            else document
        )
    by_id = {c.id: c for c in chunks}
    for view in DependencyIndex.load(kb).source_views:
        parent = by_id.get(view["parent_id"])
        if parent is None:
            continue
        if source_digest(parent) != view["parent_digest"]:
            raise DependencyError("Recorte revisado desatualizado; revise a fonte original.")
        start, end = view["start_quote"], view["end_quote"]
        if parent.content.count(start) != 1 or parent.content.count(end) != 1:
            raise DependencyError("Limites do recorte não correspondem à fonte original.")
        left = parent.content.index(start)
        right = parent.content.index(end) + len(end)
        if right <= left or not set(view["image_ids"]) <= set(parent.image_ids):
            raise DependencyError("Recorte com texto ou imagens fora da fonte original.")
        if view["id"] in by_id:
            raise DependencyError("Recorte repete um ID existente.")
        derived = replace(
            parent, id=view["id"], section_title=view["title"], category="reference",
            content=parent.content[left:right], image_ids=tuple(view["image_ids"]),
        )
        chunks.append(derived)
        by_id[derived.id] = derived
    return tuple(chunks)


@dataclass(frozen=True)
class Requirement:
    consumer: str
    sources: tuple[str, ...]
    evidence: str
    kind: str = "requires"
    condition: str = ""


class DependencyIndex:
    def __init__(self, data):
        if data.get("version") != 1:
            raise DependencyError("Versão desconhecida do índice de dependências.")
        self.digests = data["source_digests"]
        self.reviewed = set(data["reviewed_documents"])
        self.root_sets = data.get("root_sets", {})
        self.completion_sets = data.get("completion_sets", [])
        self.source_notes = data.get("source_notes", {})
        self.document_aliases = data.get("document_aliases", {})
        self.source_views = data.get("source_views", [])
        self.scope_aliases = data.get("scope_aliases", {})
        self.requirements = tuple(
            Requirement(
                r["consumer"],
                tuple(r["sources"]),
                r["evidence"],
                r.get("kind", "requires"),
                r.get("condition", ""),
            )
            for r in data["requirements"]
        )
        self.reviewed_sources = set(data.get("reviewed_sources", ())) | {
            id_ for members in self.root_sets.values() for id_ in members
        } | {
            id_ for rule in self.requirements for id_ in (rule.consumer, *rule.sources)
        }

    def canonical_document_path(self, map_id, path):
        target = self.document_aliases.get(f"{map_id}:{path}")
        if target is None:
            return path
        target_map, _, target_path = target.partition(":")
        if target_map != map_id or not target_path:
            raise DependencyError("Redirecionamento aponta para fora do mapa.")
        return target_path

    @classmethod
    def load(cls, kb):
        cached = getattr(kb, "_guide_dependencies", None)
        if cached is None:
            path = Path(__file__).resolve().parent.parent / "assets" / "guide-dependencies.json"
            try:
                cached = cls(json.loads(path.read_text("utf-8")))
            except (OSError, ValueError, KeyError, TypeError) as error:
                raise DependencyError("Índice de dependências ausente ou inválido.") from error
            kb._guide_dependencies = cached
        return cached

    def roots(self, context, *, upgraded=False):
        if context.required_ids:
            catalog = {c.id: c for c in context.candidates}
            existing_paths = {catalog[id_].path for id_ in context.required_ids}
            extras = [p for p in context.objective_paths if p not in existing_paths]
            roots = []
            for path in extras:
                map_id = catalog[context.required_ids[0]].map_id
                ids = self.root_sets.get(f"{map_id}:{path}")
                if not ids:
                    return ()
                roots.extend(ids)
            return tuple(dict.fromkeys([*roots, *context.required_ids]))
        task = json.loads(context.messages[1]["content"].split("\n", 1)[1].split("\n\n", 1)[0])
        seeds = [context.candidates[int(i)] for i in task["seed_sources"]]
        paths = {f"{c.map_id}:{c.path}" for c in seeds}
        if context.objective_paths:
            paths = {f"{seeds[0].map_id}:{p}" for p in context.objective_paths}
        if len(paths) > 1:
            groups = [self.root_sets.get(key) for key in sorted(paths)]
            if upgraded or any(not group for group in groups):
                return ()
            return tuple(dict.fromkeys(id_ for group in groups for id_ in group))
        if len(paths) != 1:
            return ()
        key = next(iter(paths))
        question = task["question"].casefold()
        named_scopes = {
            scope for scope, aliases in self.scope_aliases.get(key, {}).items()
            if any(re.search(r"(?<!\w)" + re.escape(alias.casefold()) + r"(?!\w)", question)
                   for alias in aliases)
        }
        if len(named_scopes) > 1:
            return ()  # Let the semantic selector resolve compound/ambiguous objectives.
        if named_scopes:
            return tuple(self.root_sets.get(key + ":" + named_scopes.pop(), ()))
        scope = ":upgrade" if upgraded else ""
        if not scope:
            for pattern, candidate in (
                (r"teleport", ":teleporter"),
                (r"wundersphere|jump pad|landing pad|trampolim", ":travel"),
                (r"\b(?:energia|power|courant)\b", ":power"),
                (r"\b(?:entro|entrar|acesso)\b.*\bbunker\b", ":bunker"),
            ):
                if re.search(pattern, question) and not re.search(
                    r"pack[ -]a[ -]punch|\bpap\b", question
                ):
                    scope = candidate
                    break
        return tuple(self.root_sets.get(key + scope, ()))

    def covers(self, roots, catalog):
        return bool(roots) and all(id_ in catalog and id_ in self.reviewed_sources for id_ in roots)

    def validate_source(self, id_, catalog):
        if id_ not in catalog or self.digests.get(id_) != source_digest(catalog[id_]):
            raise DependencyError(
                f"Índice de dependências desatualizado para {id_}. Revise as fontes antes de usar."
            )

    def complete_requirements(self, completed, context):
        catalog = {c.id: c for c in context.candidates}
        result = set(completed)
        while True:
            previous = set(result)
            for rule in self.requirements:
                if rule.consumer in result and rule.kind == "requires" and not rule.condition:
                    result.update(rule.sources)
            for group in self.completion_sets:
                if set(group["when_all"]) <= result:
                    result.update(group["complete"])
            if result == previous:
                break
        for id_ in result:
            if id_ not in catalog or catalog[id_].category == "main_ee":
                raise DependencyError("Progresso não pode concluir fases ou fontes desconhecidas.")
            self.validate_source(id_, catalog)
        return tuple(sorted(result))

    def resolve(self, roots, context, *, completed=(), discoveries=()):
        from app.source_planning import PlannedSource, SourcePlan

        catalog = {c.id: c for c in context.candidates}
        roots = tuple(dict.fromkeys(roots))
        completed = set(completed)
        rules = [*self.requirements, *discoveries]
        by_consumer: dict[str, list[Requirement]] = {}
        for rule in rules:
            by_consumer.setdefault(rule.consumer, []).append(rule)
        visiting, selected, steps = set(), set(), []

        def visit(id_, via=None):
            if id_ in completed or id_ in selected:
                return
            if id_ in visiting:
                raise DependencyError("Ciclo nos requisitos obrigatórios do procedimento.")
            if id_ not in catalog:
                raise DependencyError("Dependência aponta para uma fonte fora do mapa.")
            visiting.add(id_)
            for rule in by_consumer.get(id_, ()):
                if rule.kind != "requires":
                    continue
                if rule not in discoveries:
                    self.validate_source(id_, catalog)
                if len(rule.evidence) < 12 or rule.evidence not in catalog[id_].content:
                    raise DependencyError("Relação sem evidência literal válida.")
                for target in rule.sources:
                    if rule not in discoveries:
                        self.validate_source(target, catalog)
                    visit(target, rule)
            visiting.remove(id_)
            selected.add(id_)
            is_root = id_ in roots
            steps.append(
                PlannedSource(
                    source_id=id_,
                    role="objective" if is_root else "prerequisite",
                    anchor_id="" if is_root else via.consumer,
                    before_source_id="" if is_root else via.consumer,
                    evidence="" if is_root else via.evidence,
                    condition="" if is_root else via.condition,
                )
            )

        for id_ in roots:
            self.validate_source(id_, catalog) if self.covers((id_,), catalog) else None
            visit(id_)
        # A conditional recipe keeps its condition all the way to its prerequisites.
        # Shared prerequisites may be reached through several alternative paths;
        # an unconditional path takes precedence over conditional ones.
        scopes: dict[str, set[tuple[str, ...]]] = {}

        def propagate(id_, conditions=()):
            if id_ in completed:
                return
            previous = scopes.setdefault(id_, set())
            if () in previous or conditions in previous:
                return
            if not conditions:
                previous.clear()
            previous.add(conditions)
            for rule in by_consumer.get(id_, ()):
                if rule.kind != "requires":
                    continue
                inherited = tuple(dict.fromkeys(
                    [*conditions, *([rule.condition] if rule.condition else [])]
                ))
                for target in rule.sources:
                    propagate(target, inherited)

        for id_ in roots:
            propagate(id_)
        for step in steps:
            alternatives = scopes.get(step.source_id, {()})
            step.condition = "" if () in alternatives else " OR ".join(
                "(" + " AND ".join(path) + ")" for path in sorted(alternatives)
            )
        for step in steps:
            for rule in by_consumer.get(step.source_id, ()):
                if rule.kind == "illustrates" and (
                    len(rule.evidence) < 12 or rule.evidence not in catalog[rule.consumer].content
                ):
                    raise DependencyError("Ilustração sem evidência literal válida.")
            step.supporting_ids = list(
                dict.fromkeys(
                    id_
                    for rule in by_consumer.get(step.source_id, ())
                    if rule.kind == "illustrates"
                    for id_ in rule.sources
                    if id_ not in selected
                )
            )
            for id_ in step.supporting_ids:
                self.validate_source(id_, catalog)
        if context.phase_mode:
            if any(
                catalog[s.source_id].category == "main_ee"
                and s.source_id not in context.required_ids
                for s in steps
            ):
                raise DependencyError("Dependência tenta avançar para outra fase do EE.")
        return SourcePlan(steps=steps, completed_source_ids=sorted(completed))


def compact_summary(plan, context):
    """Group adjacent supporting procedures without changing their dependency order."""
    catalog = {c.id: c for c in context.candidates}
    from app.source_planning import PlannedSource

    grouped: list[PlannedSource] = []
    aliases = {}
    for original in plan.steps:
        step = original.model_copy(deep=True)
        if (
            grouped
            and step.role == grouped[-1].role == "prerequisite"
            and (catalog[step.source_id].path == catalog[grouped[-1].source_id].path)
            and step.condition == grouped[-1].condition
        ):
            head = grouped[-1]
            head.grouped_source_ids.extend([step.source_id, *step.grouped_source_ids])
            head.supporting_ids.extend(step.supporting_ids)
            aliases[step.source_id] = head.source_id
        else:
            grouped.append(step)
    for step in grouped:
        members = {step.source_id, *step.grouped_source_ids}
        if step.anchor_id in members or step.before_source_id in members:
            # A -> B -> objective may collapse A and B into one setup block.
            # Anchor it to B's external consumer, not to a now-hidden group member.
            witness = next(
                (s for s in plan.steps if s.source_id in members
                 and s.anchor_id not in members
                 and (s.before_source_id or s.anchor_id) not in members), None,
            )
            if witness:
                step.anchor_id = witness.anchor_id
                step.evidence = witness.evidence
                step.before_source_id = witness.before_source_id or witness.anchor_id
        step.before_source_id = aliases.get(step.before_source_id, step.before_source_id)
        # A dependency between members is already encoded by their full text order.
        if step.before_source_id == step.source_id:
            step.before_source_id = next(
                (s.source_id for s in grouped if s.source_id in context.required_ids), ""
            )
    return plan.model_copy(update={"steps": grouped})
