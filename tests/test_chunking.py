from app.chunking import extract_image_paths, split_markdown_by_sections


def test_sections_keep_images_attached_to_their_step() -> None:
    content = """
# Guide

## step 1 - open the door

Do the first thing.

Related image: images/guide/door.jpg

## Related images

- images/guide/door.jpg
""".strip()

    sections = split_markdown_by_sections(content)

    assert len(sections) == 1
    assert sections[0].title == "step 1 - open the door"
    assert sections[0].image_paths == ("images/guide/door.jpg",)
    assert "images/guide/door.jpg" not in sections[0].content


def test_image_extraction_is_deduplicated_and_normalized() -> None:
    content = """
Related image: images\\shield\\part_1.jpg
- images/shield/part_1.jpg
- images/shield/part_2.webp
""".strip()

    assert extract_image_paths(content) == (
        "images/shield/part_1.jpg",
        "images/shield/part_2.webp",
    )
