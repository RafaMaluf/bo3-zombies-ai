"""Attach complete image groups to grounded answer blocks, outside the model."""

from __future__ import annotations

from collections.abc import Callable

from app.domain import ImageAsset
from app.llm import GeneratedBlock
from app.prompt_builder import PromptBundle
from app.schemas import AnswerBlock, RelevantImage


def present_blocks(
    blocks: list[GeneratedBlock],
    prompt: PromptBundle,
    image_url: Callable[[str, str], str],
    clean_text: Callable[[str], str],
    max_images: int = 36,
) -> list[AnswerBlock]:
    chunks = {item.chunk.id: item.chunk for item in prompt.chunks}
    assets = {asset.id: asset for asset in prompt.images}
    used_sources: set[str] = set()
    used_images: set[str] = set()
    result: list[AnswerBlock] = []
    for block in blocks:
        source_ids = list(dict.fromkeys(s for s in block.source_ids if s in chunks))
        # Unknown references cannot earn a position in the grounded response.
        if not source_ids or not clean_text(block.body).strip():
            continue
        images: list[RelevantImage] = []
        available_image_count = len(
            {
                i
                for source_id in source_ids
                if source_id not in used_sources
                for i in chunks[source_id].image_ids
                if i not in used_images
            }
        )
        for source_id in source_ids:
            if source_id in used_sources:
                continue
            group: list[ImageAsset] = [
                assets[i]
                for i in chunks[source_id].image_ids
                if i in assets and i not in used_images
            ]
            # Never cut the last photograph off a group of alternative locations.
            expected = set(chunks[source_id].image_ids) - used_images
            if len(group) == len(expected) and len(used_images) + len(group) <= max_images:
                for asset in group:
                    images.append(
                        RelevantImage(
                            id=asset.id,
                            map_id=asset.map_id,
                            path=asset.path,
                            caption=asset.caption,
                            section=asset.section,
                            thumbnail_url=image_url(asset.id, "thumb"),
                            full_url=image_url(asset.id, "full"),
                        )
                    )
                    used_images.add(asset.id)
            used_sources.add(source_id)
        result.append(
            AnswerBlock(
                title=clean_text(block.title),
                body=clean_text(block.body),
                source_ids=source_ids,
                images=images,
                available_image_count=available_image_count,
            )
        )
    return result
