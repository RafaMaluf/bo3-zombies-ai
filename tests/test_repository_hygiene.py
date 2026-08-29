from scripts.check_repository_hygiene import forbidden_gameplay_images, potential_secrets


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


def test_committed_secret_patterns_are_rejected_without_echoing_values() -> None:
    fake_groq_key = "gsk_" + "a" * 32
    findings = potential_secrets(
        [
            ("app/config.py", f'GROQ_API_KEY="{fake_groq_key}"'.encode()),
            ("deploy.env", b"R2_SECRET_ACCESS_KEY=actual-secret-value"),
            (".env", b""),
        ]
    )

    assert findings == [
        ".env: tracked environment file",
        "app/config.py:1: Groq API key",
        "app/config.py:1: non-placeholder GROQ_API_KEY",
        "deploy.env:1: non-placeholder R2_SECRET_ACCESS_KEY",
    ]
    assert fake_groq_key not in "\n".join(findings)


def test_documented_secret_placeholders_are_allowed() -> None:
    assert potential_secrets(
        [
            (".env.example", b"GROQ_API_KEY=\nVOYAGE_API_KEY=your_key_here"),
            ("README.md", b"R2_ACCESS_KEY_ID=<account-key>"),
        ]
    ) == []
