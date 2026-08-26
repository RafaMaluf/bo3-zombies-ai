from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _env_origins() -> tuple[str, ...]:
    raw_value = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000",
    )
    return tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    base_dir: Path = BASE_DIR
    maps_dir: Path = BASE_DIR / "maps"
    frontend_dir: Path = BASE_DIR / "frontend"
    cache_dir: Path = BASE_DIR / ".cache"
    asset_manifest_path: Path = BASE_DIR / "assets" / "image-manifest.json"
    asset_base_url: str = field(
        default_factory=lambda: os.getenv("ASSET_BASE_URL", "").strip().rstrip("/")
    )
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"))
    embedding_provider: str = field(
        default_factory=lambda: os.getenv("EMBEDDING_PROVIDER", "").strip().lower()
    )
    voyage_api_key: str = field(default_factory=lambda: os.getenv("VOYAGE_API_KEY", ""))
    voyage_model: str = field(default_factory=lambda: os.getenv("VOYAGE_MODEL", "voyage-4-large"))
    embedding_index_dir: Path = BASE_DIR / "embeddings"
    max_retrieved_chunks: int = field(default_factory=lambda: _env_int("MAX_RETRIEVED_CHUNKS", 10))
    max_multi_documents: int = field(default_factory=lambda: _env_int("MAX_MULTI_DOCUMENTS", 3))
    max_context_chars: int = field(default_factory=lambda: _env_int("MAX_CONTEXT_CHARS", 28_000))
    max_candidate_images: int = field(default_factory=lambda: _env_int("MAX_CANDIDATE_IMAGES", 24))
    max_response_images: int = field(default_factory=lambda: _env_int("MAX_RESPONSE_IMAGES", 8))
    max_history_messages: int = field(default_factory=lambda: _env_int("MAX_HISTORY_MESSAGES", 10))
    allowed_origins: tuple[str, ...] = field(default_factory=_env_origins)

    @property
    def llm_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def embeddings_configured(self) -> bool:
        return self.embedding_provider == "voyage" and bool(self.voyage_api_key)

    @property
    def remote_assets_configured(self) -> bool:
        return bool(self.asset_base_url)


settings = Settings()
