from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import PurePosixPath

GAMEPLAY_IMAGE_SUFFIXES = {
    ".avif",
    ".bmp",
    ".gif",
    ".jpeg",
    ".jpg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}


def forbidden_gameplay_images(paths: Iterable[str]) -> list[str]:
    forbidden: list[str] = []
    for raw_path in paths:
        normalized = raw_path.strip().replace("\\", "/")
        if not normalized:
            continue
        path = PurePosixPath(normalized)
        parts = path.parts
        if len(parts) < 2 or parts[0] != "maps":
            continue
        inside_images_directory = len(parts) >= 3 and parts[2] == "images"
        has_image_extension = path.suffix.lower() in GAMEPLAY_IMAGE_SUFFIXES
        if inside_images_directory or has_image_extension:
            forbidden.append(normalized)
    return sorted(set(forbidden))


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return [path.decode("utf-8") for path in result.stdout.split(b"\0") if path]


def main() -> int:
    forbidden = forbidden_gameplay_images(tracked_files())
    if forbidden:
        print("Tracked gameplay image binaries are forbidden:")
        for path in forbidden:
            print(f"- {path}")
        return 1
    print("Repository hygiene passed: no gameplay image binaries are tracked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
