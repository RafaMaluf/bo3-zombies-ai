from pathlib import Path

import pytest

from app.assets import AssetManifest
from app.domain import ScoredChunk
from app.knowledge_base import KnowledgeBase
from app.llm import GeneratedBlock
from app.presentation import present_blocks
from app.prompt_builder import build_answer_prompt

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def shield_prompt():
    kb = KnowledgeBase(
        ROOT / "maps", asset_manifest=AssetManifest.load(ROOT / "assets" / "image-manifest.json")
    )
    parts = tuple(
        ScoredChunk(chunk=c, score=1.0)
        for c in kb.chunks.values()
        if c.map_id == "shadows_of_evil"
        and c.path == "shield.md"
        and c.section_title.startswith("part ")
    )
    return build_answer_prompt("Como monto o escudo?", [], parts, kb, 28_000, 36)


def display(blocks, prompt, limit=36):
    return present_blocks(
        blocks, prompt, lambda i, v: f"/media/{i}?variant={v}", lambda text: text, max_images=limit
    )


def blocks_for(prompt):
    return [
        GeneratedBlock(
            title=c.chunk.section_title,
            body="Três locais possíveis para a peça.",
            source_ids=[c.chunk.id],
        )
        for c in prompt.chunks
    ]


def test_shadows_shield_preserves_all_nine_images_in_three_correct_groups(shield_prompt):
    blocks = display(blocks_for(shield_prompt), shield_prompt)
    assert [len(b.images) for b in blocks] == [3, 3, 3]
    assert len({i.id for b in blocks for i in b.images}) == 9
    for block, source in zip(blocks, shield_prompt.chunks, strict=True):
        assert {i.id for i in block.images} == set(source.chunk.image_ids)


def test_legacy_eight_image_cap_never_truncates_a_three_photo_group(shield_prompt):
    blocks = display(blocks_for(shield_prompt), shield_prompt, limit=8)
    assert [len(b.images) for b in blocks] == [3, 3, 0]
    assert blocks[-1].available_image_count == 3


def test_unknown_source_cannot_attach_or_display_a_block(shield_prompt):
    invalid = GeneratedBlock(body="Invented instruction", source_ids=["not-retrieved"])
    assert display([invalid], shield_prompt) == []


def test_repeated_source_does_not_repeat_photos(shield_prompt):
    block = blocks_for(shield_prompt)[0]
    shown = display([block, block], shield_prompt)
    assert [len(b.images) for b in shown] == [3, 0]
    assert shown[1].available_image_count == 0
