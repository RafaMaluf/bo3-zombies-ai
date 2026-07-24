from pathlib import Path

from app.knowledge_base import KnowledgeBase
from app.main import _select_image_assets
from app.prompt_builder import build_answer_prompt
from app.retrieval import SearchEngine

ROOT = Path(__file__).resolve().parent.parent


def test_prompt_only_exposes_images_from_retrieved_chunks() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    result = SearchEngine(knowledge_base).search(
        "How do I get the base bow in Der Eisendrache?",
        active_map_id=None,
        limit=4,
    )

    prompt = build_answer_prompt(
        user_message="How do I get the base bow in Der Eisendrache?",
        history=[],
        scored_chunks=result.chunks,
        knowledge_base=knowledge_base,
        max_context_chars=12_000,
        max_candidate_images=12,
    )

    allowed_ids = {image_id for scored in prompt.chunks for image_id in scored.chunk.image_ids}
    assert prompt.images
    assert {image.id for image in prompt.images} <= allowed_ids
    assert all(image.caption for image in prompt.images)


def test_image_fallback_diversifies_by_section() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    result = SearchEngine(knowledge_base).search(
        "Como monto o Rocket Shield em Der Eisendrache?",
        active_map_id=None,
        limit=8,
    )
    prompt = build_answer_prompt(
        user_message="Como monto o Rocket Shield em Der Eisendrache?",
        history=[],
        scored_chunks=result.chunks,
        knowledge_base=knowledge_base,
        max_context_chars=24_000,
        max_candidate_images=24,
    )

    selected = _select_image_assets([], prompt.images, limit=8)

    assert len(selected) == 3
    assert len({asset.section for asset in selected}) == 3


def test_single_document_context_is_ordered_like_the_guide() -> None:
    knowledge_base = KnowledgeBase(ROOT / "maps")
    result = SearchEngine(knowledge_base).search(
        "Como faço os quatro rituais de Shadows of Evil?",
        active_map_id=None,
        limit=10,
    )
    prompt = build_answer_prompt(
        user_message="Como faço os quatro rituais de Shadows of Evil?",
        history=[],
        scored_chunks=result.chunks,
        knowledge_base=knowledge_base,
        max_context_chars=28_000,
        max_candidate_images=24,
    )

    positions = [item.chunk.position for item in prompt.chunks]
    assert positions == sorted(positions)
    assert {item.chunk.path for item in prompt.chunks} == {"pap.md"}
