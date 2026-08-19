from __future__ import annotations

import logging
import math
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from threading import Lock

from app.domain import (
    KnowledgeChunk,
    RetrievalResult,
    ScoredChunk,
)
from app.embeddings import EmbeddingError, EmbeddingIndex, VoyageEmbeddingClient
from app.knowledge_base import KnowledgeBase

logger = logging.getLogger("krono.retrieval")

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
COMPREHENSIVE_TERMS = {
    "all",
    "build",
    "complete",
    "completo",
    "completa",
    "every",
    "faco",
    "four",
    "full",
    "montar",
    "monto",
    "passos",
    "steps",
    "todos",
    "todas",
    "4",
    "quatro",
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
TITLE_BOOST_STOP_WORDS = {
    "abrir",
    "activate",
    "ativar",
    "build",
    "collect",
    "consigo",
    "easter",
    "egg",
    "faco",
    "find",
    "get",
    "liberar",
    "make",
    "main",
    "obtain",
    "pego",
    "quest",
    "unlock",
    "where",
}
TOPIC_EXPANSIONS = {
    "pack a punch": ("pap", "pack", "punch"),
    "pack-a-punch": ("pap", "pack", "punch"),
    "easter egg": ("easter", "egg", "main", "ee"),
    "main quest": ("main", "quest", "easter", "egg"),
    "base bow": ("wrath", "ancients", "bow"),
    "crafting table": ("build", "table", "workbench"),
    "wonder weapon": ("wonder", "weapon"),
    "arma especial": ("wonder", "weapon"),
    "cajado de fogo": ("fire", "staff"),
    "cajado de gelo": ("ice", "staff"),
    "cajado de raio": ("lightning", "staff"),
    "cajado de vento": ("wind", "staff"),
    "escudo": ("shield",),
    "energia": ("power",),
    "ligar a energia": ("power",),
    "arco eletrico": ("lightning", "bow", "electric"),
    "arco de fogo": ("fire", "bow"),
    "arco do lobo": ("wolf", "bow"),
    "arco do vazio": ("void", "bow"),
    "arco iris": ("rainbow",),
    "agua azul": ("blue", "water", "bucket"),
    "agua verde": ("green", "water", "bucket"),
    "agua roxa": ("purple", "water", "bucket"),
    "piramide de almas": ("pyramid", "souls", "main", "quest"),
    "q e d": ("qed", "quantum", "entanglement", "device"),
    "samantha says": ("computer", "colors", "pyramid", "souls", "main", "quest"),
}
TOKEN_EXPANSIONS = {
    "abrir": ("open", "unlock"),
    "acendo": ("light", "ignite"),
    "agua": ("water",),
    "aguas": ("water",),
    "altar": ("altar",),
    "altares": ("altar", "altars"),
    "aranha": ("spider",),
    "aranhas": ("spider", "spiders"),
    "armadilha": ("trap",),
    "armadilhas": ("trap", "traps"),
    "arco": ("bow",),
    "arcos": ("bow", "bows"),
    "atirar": ("shoot",),
    "ativar": ("activate",),
    "azul": ("blue",),
    "balde": ("bucket",),
    "baldes": ("bucket", "buckets"),
    "bandeira": ("flag",),
    "cajado": ("staff",),
    "cajados": ("staff", "staffs"),
    "caveira": ("skull",),
    "caveiras": ("skull", "skulls"),
    "coracao": ("heart",),
    "coracoes": ("heart", "hearts"),
    "crafting": ("build", "workbench"),
    "dinamite": ("dynamite",),
    "eletrica": ("electric", "lightning"),
    "eletrico": ("electric", "lightning"),
    "esqueleto": ("skeleton",),
    "esqueletos": ("skeleton", "skeletons"),
    "ficam": ("location", "locations"),
    "fogo": ("fire",),
    "fogueira": ("bonfire",),
    "fogueiras": ("bonfire", "bonfires"),
    "frasco": ("flask",),
    "fusivel": ("fuse",),
    "fusiveis": ("fuse", "fuses"),
    "garrafa": ("bottle",),
    "garrafas": ("bottle", "bottles"),
    "incubar": ("incubate",),
    "jogador": ("player",),
    "jogadores": ("player", "players"),
    "lareira": ("fireplace",),
    "liberar": ("unlock",),
    "lobo": ("wolf",),
    "macaco": ("monkey",),
    "macacos": ("monkey", "monkeys"),
    "manopla": ("gauntlet",),
    "mascara": ("mask", "helmet"),
    "mascaras": ("mask", "masks", "helmet"),
    "meteorito": ("meteorite",),
    "meteoritos": ("meteorite", "meteorites"),
    "musica": ("music", "song"),
    "musicas": ("music", "songs"),
    "onde": ("where", "location"),
    "ordem": ("order",),
    "ovo": ("egg",),
    "pego": ("get", "obtain"),
    "pedra": ("rock",),
    "pessoa": ("player",),
    "pessoas": ("player", "players"),
    "peca": ("part", "piece"),
    "pecas": ("parts", "pieces"),
    "planta": ("plant",),
    "plantas": ("plant", "plants"),
    "primeira": ("first", "part", "1"),
    "primeiro": ("first", "part", "1"),
    "quatro": ("four", "4"),
    "ritual": ("ritual",),
    "rituais": ("ritual", "rituals"),
    "robo": ("robot",),
    "robos": ("robot", "robots"),
    "roxa": ("purple",),
    "roxo": ("purple",),
    "segunda": ("second", "part", "2"),
    "segundo": ("second", "part", "2"),
    "sozinha": ("solo", "player"),
    "sozinho": ("solo", "player"),
    "teletransportador": ("teleporter",),
    "teletransportadores": ("teleporter", "teleporters"),
    "terceira": ("third", "part", "3"),
    "terceiro": ("third", "part", "3"),
    "teleporters": ("teleporter",),
    "transformar": ("transform", "transformation"),
    "tumba": ("grave",),
    "tumbas": ("grave", "graves"),
    "ursinho": ("teddy", "bear"),
    "ursinhos": ("teddy", "bear", "bears"),
    "verde": ("green",),
    "vazio": ("void",),
    "vento": ("wind",),
    "valvula": ("valve",),
    "valvulas": ("valve", "valves"),
    "vela": ("candle",),
    "virar": ("transform", "transformation"),
    "viro": ("transform", "transformation"),
    "unlock": ("get", "obtain"),
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


def expanded_query_tokens(query: str) -> list[str]:
    normalized = normalize_text(query)
    tokens = tokenize(normalized)
    for token in tuple(tokens):
        tokens.extend(TOKEN_EXPANSIONS.get(token, ()))
    for phrase, expansion in TOPIC_EXPANSIONS.items():
        if normalize_text(phrase) in normalized:
            tokens.extend(expansion)
    return list(dict.fromkeys(tokens))


class SearchEngine:
    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        embedding_index: EmbeddingIndex | None = None,
        embedding_client: VoyageEmbeddingClient | None = None,
        semantic_retry_seconds: float = 60.0,
    ) -> None:
        self.knowledge_base = knowledge_base
        self.embedding_index = embedding_index
        self.embedding_client = embedding_client
        self._semantic_retry_seconds = semantic_retry_seconds
        self._semantic_retry_after = 0.0
        self._semantic_state_lock = Lock()
        self._chunks = tuple(knowledge_base.chunks.values())
        self._tokens: dict[str, list[str]] = {}
        self._normalized_text: dict[str, str] = {}
        self._term_frequencies: dict[str, Counter[str]] = {}
        self._document_frequency: Counter[str] = Counter()
        self._average_length = 1.0
        self._alias_to_map = self._build_alias_index()
        self._build_index()

    @property
    def semantic_ready(self) -> bool:
        return self.embedding_index is not None and self.embedding_client is not None

    def _bm25_ranked(self, bm25_scores: dict[str, float]) -> list[ScoredChunk]:
        scored = [
            ScoredChunk(chunk=self.knowledge_base.chunks[chunk_id], score=score)
            for chunk_id, score in bm25_scores.items()
            if score > 0
        ]
        scored.sort(key=lambda item: (-item.score, item.chunk.position))
        return scored

    def _rank_chunks(
        self,
        query: str,
        allowed_maps: set[str],
        bm25_scores: dict[str, float],
    ) -> list[ScoredChunk]:
        if not self.semantic_ready:
            return self._bm25_ranked(bm25_scores)

        with self._semantic_state_lock:
            if time.monotonic() < self._semantic_retry_after:
                return self._bm25_ranked(bm25_scores)

        assert self.embedding_index is not None
        assert self.embedding_client is not None
        try:
            query_vector = self.embedding_client.embed_query(query)
            semantic_scores = self.embedding_index.score(query_vector)
        except EmbeddingError:
            with self._semantic_state_lock:
                self._semantic_retry_after = time.monotonic() + self._semantic_retry_seconds
            logger.warning("Semantic retrieval failed; using BM25 only.", exc_info=True)
            return self._bm25_ranked(bm25_scores)

        with self._semantic_state_lock:
            self._semantic_retry_after = 0.0

        bm25_ids = sorted(
            (chunk_id for chunk_id, score in bm25_scores.items() if score > 0),
            key=lambda chunk_id: (
                -bm25_scores[chunk_id],
                self.knowledge_base.chunks[chunk_id].position,
            ),
        )
        semantic_ids = sorted(
            (
                chunk.id
                for chunk in self._chunks
                if chunk.map_id in allowed_maps and semantic_scores.get(chunk.id, -1.0) >= 0.15
            ),
            key=lambda chunk_id: (
                -semantic_scores[chunk_id],
                self.knowledge_base.chunks[chunk_id].position,
            ),
        )[:100]

        # Reciprocal Rank Fusion combines lexical precision with semantic
        # recall without pretending BM25 and cosine scores share a scale. The
        # lexical side intentionally carries more weight: Zombies terminology
        # contains exact names, acronyms and step numbers that embeddings may
        # otherwise smooth over.
        fused: defaultdict[str, float] = defaultdict(float)
        for rank, chunk_id in enumerate(bm25_ids, start=1):
            fused[chunk_id] += 4.0 / (60 + rank)
        for rank, chunk_id in enumerate(semantic_ids, start=1):
            fused[chunk_id] += 1.0 / (60 + rank)

        scored = [
            ScoredChunk(
                chunk=self.knowledge_base.chunks[chunk_id],
                score=round(score * 1000, 6),
            )
            for chunk_id, score in fused.items()
        ]
        scored.sort(key=lambda item: (-item.score, item.chunk.position))
        return scored

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
                    f"{chunk.path.replace('_', ' ').replace('/', ' ')} " * 3,
                    chunk.content,
                ]
            )
            self._normalized_text[chunk.id] = normalize_text(searchable_text)
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

    def explicit_document_paths(
        self,
        query: str,
        map_id: str | None,
    ) -> tuple[str, ...]:
        """Return guides whose filename is explicitly named in the query.

        This is intentionally conservative. It recognizes concrete guide names
        such as "G-Strike" and "Maxis Drone", but does not treat generic words
        such as "main", "setup" or "power" as a multi-document request.
        """
        record = self.knowledge_base.maps.get(map_id or "")
        if record is None:
            return ()

        normalized_query = normalize_text(query)
        query_tokens = set(expanded_query_tokens(query))
        generic_tokens = {
            "ee",
            "general",
            "main",
            "music",
            "overview",
            "pap",
            "power",
            "setup",
            "side",
        }
        matches: list[tuple[int, int, str]] = []
        for order, path in enumerate(record.document_paths):
            label = normalize_text(Path(path).stem.replace("_", " ").replace("-", " "))
            label_tokens = set(tokenize(label))
            phrase_match = re.search(
                rf"(?:^|\s){re.escape(label)}(?:$|\s)",
                normalized_query,
            )
            semantic_match = (
                bool(label_tokens)
                and label_tokens <= query_tokens
                and bool(label_tokens - generic_tokens)
            )
            if phrase_match or semantic_match:
                position = phrase_match.start() if phrase_match else len(normalized_query) + order
                matches.append((position, order, path))

        matches.sort()
        return tuple(path for _, _, path in matches)

    @staticmethod
    def is_multi_document_request(
        query: str,
        document_paths: tuple[str, ...],
    ) -> bool:
        if len(document_paths) < 2:
            return False
        if len(document_paths) >= 3:
            return True
        if any(separator in query for separator in (",", ";", "&", "+", "/")):
            return True
        return bool({"e", "and"} & set(normalize_text(query).split()))

    def search(
        self,
        query: str,
        active_map_id: str | None,
        limit: int,
    ) -> RetrievalResult:
        explicit_maps = self.explicit_map_ids(query)
        valid_active_map = active_map_id if active_map_id in self.knowledge_base.maps else None

        if valid_active_map:
            allowed_maps = {valid_active_map}
        elif explicit_maps:
            allowed_maps = set(explicit_maps)
        else:
            allowed_maps = set(self.knowledge_base.maps)

        query_tokens = expanded_query_tokens(query)
        original_query_tokens = tokenize(query)
        bm25_scores: dict[str, float] = {}
        for chunk in self._chunks:
            if chunk.map_id not in allowed_maps:
                continue
            score = self._score_chunk(query_tokens, original_query_tokens, chunk)
            bm25_scores[chunk.id] = score
        lexical_scored = [
            ScoredChunk(chunk=self.knowledge_base.chunks[chunk_id], score=score)
            for chunk_id, score in bm25_scores.items()
            if score > 0
        ]
        lexical_scored.sort(key=lambda item: (-item.score, item.chunk.position))
        scored = self._rank_chunks(query, allowed_maps, bm25_scores)

        unique_topic_map = self._unique_topic_map(query, original_query_tokens)
        if not explicit_maps and not valid_active_map and unique_topic_map:
            scored = [item for item in scored if item.chunk.map_id == unique_topic_map]
            lexical_scored = [
                item for item in lexical_scored if item.chunk.map_id == unique_topic_map
            ]

        document_map_id = valid_active_map
        if document_map_id is None and len(explicit_maps) == 1:
            document_map_id = explicit_maps[0]
        if document_map_id is None:
            document_map_id = unique_topic_map
        explicit_documents = self.explicit_document_paths(query, document_map_id)
        is_multi_document_query = len(explicit_documents) <= 3 and self.is_multi_document_request(
            query, explicit_documents
        )

        if not scored:
            suggestions = () if valid_active_map else tuple(sorted(allowed_maps))
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
        # Map inference remains lexical when possible. Map names and community
        # aliases are deterministic identifiers; semantic similarity is used
        # to rank content inside that scope, not to override a strong map cue.
        map_evidence = lexical_scored or scored
        for item in map_evidence[: max(limit * 3, 18)]:
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
                unranked_maps = sorted(allowed_maps - set(ranked_maps))
                return RetrievalResult(
                    chunks=(),
                    active_map_id=None,
                    explicit_map_ids=(),
                    needs_clarification=True,
                    clarification_question="Sobre qual mapa você está falando?",
                    suggested_map_ids=tuple([*ranked_maps, *unranked_maps]),
                )

        selection_pool = scored
        if is_multi_document_query:
            requested_paths = set(explicit_documents)
            selection_pool = [
                item
                for item in scored
                if item.chunk.map_id == document_map_id and item.chunk.path in requested_paths
            ]
        elif not self._is_comparison_query(query) and len(explicit_maps) <= 1:
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
            selection_pool = [
                item for item in scored if (item.chunk.map_id, item.chunk.path) == dominant_file
            ]

        if is_multi_document_query:
            by_document = {
                path: [item for item in selection_pool if item.chunk.path == path]
                for path in explicit_documents
            }
            selected_items: list[ScoredChunk] = []
            offset = 0
            while len(selected_items) < limit:
                added = False
                for path in explicit_documents:
                    candidates = by_document[path]
                    if offset >= len(candidates):
                        continue
                    selected_items.append(candidates[offset])
                    added = True
                    if len(selected_items) >= limit:
                        break
                if not added:
                    break
                offset += 1
        else:
            score_ratio = 0.0 if self._is_comprehensive_query(query) else 0.72
            score_floor = selection_pool[0].score * score_ratio
            selected_items = [item for item in selection_pool[:limit] if item.score >= score_floor]
            if not selected_items:
                selected_items = [selection_pool[0]]

        # A guide's overview and progression summary carry prerequisites and
        # connective steps that a highly specific score can otherwise omit.
        # Include them when there is room, while keeping the most relevant
        # section first for source attribution.
        selected_ids = {item.chunk.id for item in selected_items}
        for item in selection_pool:
            if len(selected_items) >= limit:
                break
            normalized_title = normalize_text(item.chunk.section_title)
            is_structural = normalized_title == "overview" or "summary" in normalized_title
            if is_structural and item.chunk.id not in selected_ids:
                selected_items.append(item)
                selected_ids.add(item.chunk.id)

        if self._is_comparison_query(query):
            comparison_maps = explicit_maps or tuple(ranked_maps)
            selected_maps = {item.chunk.map_id for item in selected_items}
            for map_id in comparison_maps:
                if map_id in selected_maps:
                    continue
                best_for_map = next(
                    (item for item in selection_pool if item.chunk.map_id == map_id),
                    None,
                )
                if best_for_map is None:
                    continue
                if len(selected_items) >= limit:
                    selected_items.pop()
                selected_items.append(best_for_map)
                selected_maps.add(map_id)

        selected = tuple(selected_items[:limit])
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
    def _is_comprehensive_query(query: str) -> bool:
        return bool(set(tokenize(query)) & COMPREHENSIVE_TERMS)

    @staticmethod
    def _expanded_query_tokens(query: str) -> list[str]:
        return expanded_query_tokens(query)

    @staticmethod
    def _singular_phrase_token(token: str) -> str:
        if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
            return token[:-1]
        return token

    def _unique_topic_map(
        self,
        query: str,
        original_query_tokens: list[str],
    ) -> str | None:
        phrase_tokens = tokenize(query)
        for width in (4, 3, 2):
            if len(phrase_tokens) < width:
                continue
            for start in range(len(phrase_tokens) - width + 1):
                window = phrase_tokens[start : start + width]
                phrases = {
                    " ".join(window),
                    " ".join(self._singular_phrase_token(token) for token in window),
                }
                for phrase in phrases:
                    matching_maps = {
                        chunk.map_id
                        for chunk in self._chunks
                        if phrase in self._normalized_text[chunk.id]
                    }
                    if len(matching_maps) == 1:
                        return next(iter(matching_maps))

        candidate_scores: Counter[str] = Counter()
        ignored = TITLE_BOOST_STOP_WORDS | COMPREHENSIVE_TERMS | COMPARISON_TERMS
        for token in original_query_tokens:
            if token in ignored or token.isdigit() or len(token) < 3:
                continue
            matching_maps = {
                chunk.map_id
                for chunk in self._chunks
                if self._term_frequencies[chunk.id].get(token, 0) > 0
            }
            if len(matching_maps) == 1:
                candidate_scores.update(matching_maps)
        if not candidate_scores:
            return None
        ranked = candidate_scores.most_common(2)
        if len(ranked) == 1 or ranked[0][1] > ranked[1][1]:
            return ranked[0][0]
        return None

    def _score_chunk(
        self,
        query_tokens: list[str],
        original_query_tokens: list[str],
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
        title_tokens = set(tokenize(normalized_title))
        document_tokens = set(tokenize(Path(chunk.path).stem.replace("_", " ")))
        original_token_set = set(original_query_tokens)
        score += sum(1.25 for token in query_tokens if token in title_tokens)
        score += sum(
            6.0
            for token in original_query_tokens
            if token in title_tokens and token not in TITLE_BOOST_STOP_WORDS and not token.isdigit()
        )
        matched_document_tokens = document_tokens & original_token_set
        if document_tokens and document_tokens <= original_token_set:
            score += 10.0 + 2.0 * len(document_tokens)
        else:
            score += 3.0 * len(matched_document_tokens)
        if normalized_query and normalized_query in normalized_title:
            score += 3.0
        return round(score, 6)
