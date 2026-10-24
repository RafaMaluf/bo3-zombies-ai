from app.language import resolve_response_language
from app.schemas import ConversationMessage


def test_explicit_message_language_overrides_device_language() -> None:
    assert (
        resolve_response_language(
            "How do I upgrade the lightning bow?",
            [],
            "pt-BR",
        )
        == "en"
    )


def test_french_question_preserves_matching_device_locale() -> None:
    assert (
        resolve_response_language(
            "Comment fabriquer le G-Strike ?",
            [],
            "fr-FR",
        )
        == "fr-FR"
    )


def test_ambiguous_game_terms_fall_back_to_device_language() -> None:
    assert resolve_response_language("EE SoE", [], "fr-FR") == "fr-FR"


def test_portuguese_pack_a_punch_question_is_not_misclassified_as_spanish() -> None:
    assert resolve_response_language("Como libero o Pack-a-Punch?", [], "pt-BR") == "pt-BR"


def test_ambiguous_follow_up_uses_recent_conversation_language() -> None:
    history = [
        ConversationMessage(
            role="user",
            content="How do I unlock Pack-a-Punch?",
        )
    ]

    assert resolve_response_language("and the others?", history, "pt-BR") == "en"
