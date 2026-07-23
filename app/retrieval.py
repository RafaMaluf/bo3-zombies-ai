from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter, defaultdict

from app.domain import (
    KnowledgeChunk,
    RetrievalResult,
    ScoredChunk,
)
from app.knowledge_base import KnowledgeBase

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
COMPARISON_TERMS = {
    "compare",
    "comparison",
    "versus",
    "difference",
    "differences",
    "comparar",
    "comparacao",
    "diferenca",
    "diferencas",
    "melhor",
    "pior",
    "todos",
    "todas",
    "maps",
    "mapas",
}
STOP_WORDS = {
    "a",
    "as",
    "and",
    "ao",
    "aos",
    "are",
    "como",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "eu",
    "for",
    "from",
    "how",
    "i",
    "is",
    "me",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "of",
    "on",
    "or",
    "os",
    "para",
    "por",
    "que",
    "the",
    "to",
    "um",
    "uma",
    "what",
    "with",
}
TOPIC_EXPANSIONS = {
    "pack a punch": ("pap", "pack", "punch"),
    "pack-a-punch": ("pap", "pack", "punch"),
    "easter egg": ("easter", "egg", "main", "ee"),
    "main quest": ("main", "quest", "easter", "egg"),
    "wonder weapon": ("wonder", "weapon"),
    "arma especial": ("wonder", "weapon"),
    "escudo": ("shield",),
    "energia": ("power",),
    "ligar a energia": ("power",),
}
TOKEN_EXPANSIONS = {
    "peca": ("part", "piece"),
    "pecas": ("parts", "pieces"),
    "primeira": ("first", "part", "1"),
    "primeiro": ("first", "part", "1"),
    "segunda": ("second", "part", "2"),
    "segundo": ("second", "part", "2"),
    "terceira": ("third", "part", "3"),
    "terceiro": ("third", "part", "3"),
    "quarta": ("fourth", "part", "4"),
    "quarto": ("fourth", "part", "4"),
}


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    return " ".join(TOKEN_PATTERN.findall(ascii_value.lower()))


def tokenize(value: str) -> list[str]:
    return [
        token
        for token in normalize_text(value).split()
        if token not in STOP_WORDS and (len(token) > 1 or token.isdigit())
    ]


class SearchEngine:
    def __init__(self, knowledge_base: KnowledgeBase) -> None:
        self.knowledge_base = knowledge_base
        self._chunks = tuple(knowledge_base.chunks.values())
        self._tokens: dict[str, list[str]] = {}
        self._term_frequencies: dict[str, Counter[str]] = {}
        self._document_frequency: Counter[str] = Counter()
        self._average_length = 1.0
        self._alias_to_map = self._build_alias_index()
        self._build_index()

    def _build_alias_index(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for record in self.knowledge_base.maps.values():
            for alias in record.aliases:
                normalized = normalize_text(alias)
                if normalized:
                    aliases[normalized] = record.map_id
        return aliases

    def _build_index(self) -> None:
        total_length = 0
        for chunk in self._chunks:
            # Repetition acts as a transparent field boost while keeping the
            # BM25 implementation dependency-free.
            searchable_text = " ".join(
                [
                    f"{chunk.map_name} " * 2,
                    f"{chunk.category} " * 3,
                    f"{chunk.section_title} " * 4,
                    f"{chunk.file_summary} " * 2,
                    chunk.content,
                ]
            )
            tokens = tokenize(searchable_text)
            self._tokens[chunk.id] = tokens
            frequencies = Counter(tokens)
            self._term_frequencies[chunk.id] = frequencies
            self._document_frequency.update(frequencies.keys())
            total_length += len(tokens)
        if self._chunks:
            self._average_length = total_length / len(self._chunks)

    def explicit_map_ids(self, query: str) -> tuple[str, ...]:
        normalized_query = normalize_text(query)
        found: list[str] = []
        for alias, map_id in sorted(
            self._alias_to_map.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            # "de" is a useful community abbreviation for Der Eisendrache,
            # but it is also one of the most common Portuguese words.
            if len(alias) <= 2 and normalized_query != alias:
                continue
            pattern = rf"(?:^|\s){re.escape(alias)}(?:$|\s)"
            if re.search(pattern, normalized_query) and map_id not in found:
                found.append(map_id)
        return tuple(found)

    def search(
        self,
        query: str,
        active_map_id: str | None,
        limit: int,
    ) -> RetrievalResult:
        explicit_maps = self.explicit_map_ids(query)
        valid_active_map = active_map_id if active_map_id in self.knowledge_base.maps else None

        if explicit_maps:
            allowed_maps = set(explicit_maps)
        elif valid_active_map:
            allowed_maps = {valid_active_map}
        else:
            allowed_maps = set(self.knowledge_base.maps)

        query_tokens = self._expanded_query_tokens(query)
        scored: list[ScoredChunk] = []
        for chunk in self._chunks:
            if chunk.map_id not in allowed_maps:
                continue
            score = self._score_chunk(query_tokens, chunk)
            if score > 0:
                scored.append(ScoredChunk(chunk=chunk, score=score))
        scored.sort(key=lambda item: (-item.score, item.chunk.position))

        if not scored:
            suggestions = tuple(sorted(allowed_maps))
            return RetrievalResult(
                chunks=(),
                active_map_id=valid_active_map,
                explicit_map_ids=explicit_maps,
                needs_clarification=True,
                clarification_question=(
                    "Não encontrei esse assunto na base. Qual mapa e qual objetivo "
                    "você quer consultar?"
                ),
                suggested_map_ids=suggestions,
            )

        map_scores: dict[str, float] = defaultdict(float)
        for item in scored[: max(limit * 3, 18)]:
            map_scores[item.chunk.map_id] = max(
                map_scores[item.chunk.map_id],
                item.score,
            )
        ranked_maps = sorted(
            map_scores,
            key=lambda map_id: map_scores[map_id],
            reverse=True,
        )

        if (
            not explicit_maps
            and not valid_active_map
            and len(ranked_maps) > 1
            and not self._is_comparison_query(query)
        ):
            top_score = map_scores[ranked_maps[0]]
            second_score = map_scores[ranked_maps[1]]
            unique_topic = top_score >= (second_score * 1.8 + 1.0)
            if not unique_topic:
                return RetrievalResult(
                    chunks=(),
                    active_map_id=None,
                    explicit_map_ids=(),
                    needs_clarification=True,
                    clarification_question="Sobre qual mapa você está falando?",
                    suggested_map_ids=tuple(ranked_maps[:6]),
                )

        selection_pool = scored
        if not self._is_comparison_query(query) and len(explicit_maps) <= 1:
            best_by_file: dict[tuple[str, str], float] = {}
            for item in scored:
                file_key = (item.chunk.map_id, item.chunk.path)
                best_by_file[file_key] = max(
                    best_by_file.get(file_key, 0.0),
                    item.score,
                )
            ranked_files = sorted(
                best_by_file,
                key=lambda file_key: best_by_file[file_key],
                reverse=True,
            )
            dominant_file = ranked_files[0]
            has_clear_file_winner = (
                len(ranked_files) == 1
                or best_by_file[dominant_file] >= best_by_file[ranked_files[1]] * 1.2 + 0.5
            )
            if has_clear_file_winner:
                selection_pool = [
                    item for item in scored if (item.chunk.map_id, item.chunk.path) == dominant_file
                ]

        score_floor = selection_pool[0].score * 0.72
        selected = tuple(item for item in selection_pool[:limit] if item.score >= score_floor)
        if not selected:
            selected = (selection_pool[0],)
        selected_maps = {item.chunk.map_id for item in selected}
        inferred_active = next(iter(selected_maps)) if len(selected_maps) == 1 else valid_active_map
        return RetrievalResult(
            chunks=selected,
            active_map_id=inferred_active,
            explicit_map_ids=explicit_maps,
            needs_clarification=False,
            clarification_question="",
            suggested_map_ids=(),
        )

    @staticmethod
    def _is_comparison_query(query: str) -> bool:
        return bool(set(tokenize(query)) & COMPARISON_TERMS)

    @staticmethod
    def _expanded_query_tokens(query: str) -> list[str]:
        normalized = normalize_text(query)
        tokens = tokenize(normalized)
        for token in tuple(tokens):
            tokens.extend(TOKEN_EXPANSIONS.get(token, ()))
        for phrase, expansion in TOPIC_EXPANSIONS.items():
            if normalize_text(phrase) in normalized:
                tokens.extend(expansion)
        return list(dict.fromkeys(tokens))

    def _score_chunk(
        self,
        query_tokens: list[str],
        chunk: KnowledgeChunk,
    ) -> float:
        if not query_tokens:
            return 0.0

        frequencies = self._term_frequencies[chunk.id]
        document_length = len(self._tokens[chunk.id])
        total_documents = max(len(self._chunks), 1)
        k1 = 1.5
        b = 0.75
        score = 0.0

        for token in query_tokens:
            frequency = frequencies.get(token, 0)
            if frequency == 0:
                continue
            document_frequency = self._document_frequency.get(token, 0)
            inverse_document_frequency = math.log(
                1 + (total_documents - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * document_length / self._average_length)
            score += inverse_document_frequency * (frequency * (k1 + 1) / denominator)

        normalized_query = " ".join(query_tokens)
        normalized_title = normalize_text(chunk.section_title)
        if normalized_query and normalized_query in normalized_title:
            score += 3.0
        return round(score, 6)
