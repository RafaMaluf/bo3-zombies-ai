from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageOps

from app.domain import ImageAsset

THUMBNAIL_SIZE = (960, 640)


class MediaService:
    def __init__(self, cache_dir: Path) -> None:
        self.thumbnail_dir = cache_dir / "thumbnails"

    def get_path(self, asset: ImageAsset, variant: str) -> Path:
        if variant == "full":
            return asset.source_file
        if variant != "thumb":
            raise ValueError("Unsupported image variant.")
        return self._thumbnail(asset)

    def _thumbnail(self, asset: ImageAsset) -> Path:
        self.thumbnail_dir.mkdir(parents=True, exist_ok=True)
        destination = self.thumbnail_dir / f"{asset.id}.webp"
        source_mtime = asset.source_file.stat().st_mtime_ns
        if destination.exists() and destination.stat().st_mtime_ns >= source_mtime:
            return destination

        temporary = destination.with_suffix(".tmp.webp")
        with Image.open(asset.source_file) as source:
            image = ImageOps.exif_transpose(source)
            if getattr(image, "is_animated", False):
                image.seek(0)
            image = image.convert("RGB")
            image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            image.save(
                temporary,
                format="WEBP",
                quality=80,
                method=4,
                optimize=True,
            )
        os.replace(temporary, destination)
        return destination
