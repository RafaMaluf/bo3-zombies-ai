from scripts.check_repository_hygiene import forbidden_gameplay_images


def test_gameplay_images_under_maps_are_rejected() -> None:
    assert forbidden_gameplay_images(
        [
            "maps/origins/images/step.webp",
            "maps/origins/cover.jpg",
            "maps/origins/guide.md",
            "frontend/logo.png",
            "assets/image-manifest.json",
        ]
    ) == [
        "maps/origins/cover.jpg",
        "maps/origins/images/step.webp",
    ]


def test_paths_are_normalized_and_deduplicated() -> None:
    assert forbidden_gameplay_images(
        [
            r"maps\moon\images\panel.PNG",
            "maps/moon/images/panel.PNG",
            "",
        ]
    ) == ["maps/moon/images/panel.PNG"]
