from __future__ import annotations

import re

from langdetect import DetectorFactory, LangDetectException, detect_langs

from app.schemas import ConversationMessage

DetectorFactory.seed = 0

WORD_PATTERN = re.compile(r"[^\W\d_]+(?:['’-][^\W\d_]+)*", flags=re.UNICODE)
MIN_WORDS = 3
MIN_LETTERS = 10
MIN_CONFIDENCE = 0.75


def resolve_response_language(
    message: str,
    history: list[ConversationMessage],
    preferred_language: str,
) -> str:
    """Resolve a stable response locale without asking the answer model to guess."""
    detected = _detect_language(message)
    if detected is None:
        for item in reversed(history):
            if item.role != "user":
                continue
            detected = _detect_language(item.content)
            if detected is not None:
                break

    if detected is None:
        return preferred_language

    preferred_base = preferred_language.split("-", maxsplit=1)[0].casefold()
    detected_base = detected.split("-", maxsplit=1)[0].casefold()
    return preferred_language if preferred_base == detected_base else detected


def _detect_language(message: str) -> str | None:
    words = WORD_PATTERN.findall(message)
    letter_count = sum(len(word) for word in words)
    if len(words) < MIN_WORDS or letter_count < MIN_LETTERS:
        return None

    try:
        candidates = detect_langs(" ".join(words))
    except LangDetectException:
        return None
    if not candidates or candidates[0].prob < MIN_CONFIDENCE:
        return None
    return candidates[0].lang
