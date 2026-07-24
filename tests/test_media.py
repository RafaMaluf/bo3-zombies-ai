from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

from app.domain import ImageAsset
from app.media import THUMBNAIL_SIZE, MediaService


def _asset(source_file: Path) -> ImageAsset:
    return ImageAsset(
        id="img_concurrency_test",
        map_id="test_map",
        path="images/source.jpg",
        caption="Test image",
        section="Test section",
        document_path="guide.md",
        source_file=source_file,
    )


def test_thumbnail_generation_is_safe_under_concurrency(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    Image.new("RGB", (1600, 900), color=(40, 80, 120)).save(source, format="JPEG")
    media = MediaService(tmp_path / "cache")
    asset = _asset(source)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(lambda _: media.get_path(asset, "thumb"), range(24)))

    assert len(set(results)) == 1
    thumbnail = results[0]
    assert thumbnail.is_file()
    assert not thumbnail.with_suffix(".tmp.webp").exists()
    with Image.open(thumbnail) as image:
        assert image.format == "WEBP"
        assert image.width <= THUMBNAIL_SIZE[0]
        assert image.height <= THUMBNAIL_SIZE[1]


def test_full_variant_returns_the_original_file(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGB", (10, 10)).save(source)

    assert MediaService(tmp_path / "cache").get_path(_asset(source), "full") == source
