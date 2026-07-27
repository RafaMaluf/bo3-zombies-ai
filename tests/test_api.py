import re

from fastapi.testclient import TestClient

from app.llm import (
    LLMResponse,
    LLMResponseError,
    LLMUnavailableError,
    QueryResolution,
)
from app.main import app


class ImageSelectingLLM:
    async def answer(self, messages: list[dict[str, str]]) -> LLMResponse:
        image_ids = re.findall(r"img_[a-f0-9]{16}", messages[-1]["content"])
        selected = [image_ids[0], image_ids[0], "img_not_allowed"] if image_ids else []
        return LLMResponse(answer="Resposta de teste.", image_ids=selected)


class NoImageLLM:
    async def answer(self, _: list[dict[str, str]]) -> LLMResponse:
        return LLMResponse(answer="Resposta de teste sem seleção do modelo.")


class UnavailableLLM:
    async def answer(self, _: list[dict[str, str]]) -> LLMResponse:
        raise LLMUnavailableError("GROQ_API_KEY is not configured.")


class AmbiguousFollowUpLLM:
    async def resolve_query(
        self,
        _: list[dict[str, str]],
    ) -> QueryResolution:
        return QueryResolution(
            need_clarification=True,
            clarification_question=("Há quatro melhorias de arco. Qual delas você quer fazer?"),
            candidate_document_paths=[
                "fire_bow.md",
                "lightning_bow.md",
                "void_bow.md",
                "wolf_bow.md",
                "invented_bow.md",
            ],
        )

    async def answer(self, _: list[dict[str, str]]) -> LLMResponse:
        raise AssertionError("A clarification must not generate an answer.")


class RewritingFollowUpLLM:
    async def resolve_query(
        self,
        _: list[dict[str, str]],
    ) -> QueryResolution:
        return QueryResolution(
            resolved_query="Como consigo o Wolf Bow em Der Eisendrache?",
        )

    async def answer(self, _: list[dict[str, str]]) -> LLMResponse:
        return LLMResponse(answer="Guia contextual do arco do lobo.")


class FailingResolverLLM:
    async def resolve_query(
        self,
        _: list[dict[str, str]],
    ) -> QueryResolution:
        raise LLMResponseError("No usable resolution.")

    async def answer(self, _: list[dict[str, str]]) -> LLMResponse:
        return LLMResponse(answer="O escudo é montado na bancada.")


class PlayerCountFollowUpLLM:
    async def resolve_query(
        self,
        _: list[dict[str, str]],
    ) -> QueryResolution:
        raise LLMResponseError("No usable resolution.")

    async def answer(self, _: list[dict[str, str]]) -> LLMResponse:
        return LLMResponse(
            answer=(
                "No jogo sem mod, o Easter Egg principal exige 4 jogadores. "
                "Solo requer um mod compatível; com 2 ou 3 não funciona."
            )
        )


def test_health_maps_and_thumbnail_endpoints() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["maps"] == 14

        maps = client.get("/maps")
        assert maps.status_code == 200
        map_payload = maps.json()
        assert len(map_payload) == 14
        assert [item["map_id"] for item in map_payload] == [
            "shadows_of_evil",
            "the_giant",
            "der_eisendrache",
            "zetsubou_no_shima",
            "gorod_krovi",
            "revelations",
            "nacht_der_untoten",
            "verruckt",
            "shi_no_numa",
            "kino_der_toten",
            "ascension",
            "shangri_la",
            "moon",
            "origins",
        ]
        assert [item["release_order"] for item in map_payload] == list(range(1, 15))

        cover_id = next(item["cover_image_id"] for item in map_payload if item["cover_image_id"])
        thumbnail = client.get(f"/media/{cover_id}?variant=thumb")
        assert thumbnail.status_code == 200
        assert thumbnail.headers["content-type"] == "image/webp"
        assert thumbnail.headers["cache-control"] == "public, max-age=86400"

        full = client.get(f"/media/{cover_id}?variant=full")
        assert full.status_code == 200
        assert full.headers["content-type"].startswith("image/")


def test_frontend_redirect_and_assets() -> None:
    with TestClient(app) as client:
        redirect = client.get("/", follow_redirects=False)
        assert redirect.status_code in {302, 307}
        assert redirect.headers["location"] == "/app/"

        assert client.get("/app/").status_code == 200
        assert client.get("/app/style.css").headers["content-type"].startswith("text/css")
        assert client.get("/app/app.js").headers["content-type"].startswith("text/javascript")
        assert client.get("/static/der_eisendrache/general.md").status_code == 404


def test_unknown_image_is_not_exposed_as_a_path() -> None:
    with TestClient(app) as client:
        response = client.get("/media/../../.env?variant=full")
        assert response.status_code == 404
        assert client.get("/media/img_unknown?variant=full").status_code == 404
        assert client.get("/media/img_unknown?variant=raw").status_code == 422


def test_chat_request_validation() -> None:
    with TestClient(app) as client:
        assert client.post("/chat", json={"message": ""}).status_code == 422
        assert client.post("/chat", json={"message": "x" * 2001}).status_code == 422
        assert (
            client.post(
                "/chat",
                json={
                    "message": "test",
                    "conversation_history": [{"role": "system", "content": "bad"}],
                },
            ).status_code
            == 422
        )


def test_generic_question_returns_map_clarification_without_calling_llm() -> None:
    with TestClient(app) as client:
        client.app.state.llm = UnavailableLLM()
        response = client.post("/chat", json={"message": "How do I unlock Pack-a-Punch?"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["need_clarification"]
        assert len(payload["suggested_map_ids"]) == 14


def test_ambiguous_follow_up_offers_valid_document_choices() -> None:
    with TestClient(app) as client:
        client.app.state.llm = AmbiguousFollowUpLLM()
        response = client.post(
            "/chat",
            json={
                "message": "e os arcos?",
                "active_map_id": "der_eisendrache",
                "conversation_history": [
                    {
                        "role": "user",
                        "content": "Como libero o Pack-a-Punch?",
                    },
                    {
                        "role": "assistant",
                        "content": "O Pack-a-Punch foi explicado.",
                        "source_paths": ["power_pap_teleporter.md"],
                    },
                    {
                        "role": "user",
                        "content": "e os arcos?",
                    },
                ],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["need_clarification"]
        assert payload["clarification_question"] == (
            "Encontrei 4 guias relacionados em Der Eisendrache. Qual deles você quer consultar?"
        )
        assert payload["suggested_queries"] == [
            "Fire Bow",
            "Lightning Bow",
            "Void Bow",
            "Wolf Bow",
        ]
        assert payload["suggested_map_ids"] == []


def test_referential_follow_up_is_rewritten_before_retrieval() -> None:
    with TestClient(app) as client:
        client.app.state.llm = RewritingFollowUpLLM()
        response = client.post(
            "/chat",
            json={
                "message": "e o do lobo?",
                "active_map_id": "der_eisendrache",
                "conversation_history": [
                    {
                        "role": "assistant",
                        "content": "Esse é o passo a passo do arco de fogo.",
                        "source_paths": ["fire_bow.md"],
                    }
                ],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"] == "Guia contextual do arco do lobo."
        assert {source["path"] for source in payload["sources"]} == {"wolf_bow.md"}


def test_referential_follow_up_uses_previous_source_when_resolution_fails() -> None:
    with TestClient(app) as client:
        client.app.state.llm = FailingResolverLLM()
        response = client.post(
            "/chat",
            json={
                "message": "e onde monta?",
                "active_map_id": "der_eisendrache",
                "conversation_history": [
                    {
                        "role": "assistant",
                        "content": "As peças do escudo ficam em três áreas.",
                        "source_paths": ["shield.md"],
                    }
                ],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"] == "O escudo é montado na bancada."
        assert {source["path"] for source in payload["sources"]} == {"shield.md"}


def test_elliptical_player_count_follow_up_keeps_previous_main_quest_source() -> None:
    with TestClient(app) as client:
        client.app.state.llm = PlayerCountFollowUpLLM()
        response = client.post(
            "/chat",
            json={
                "message": "pode com 2?",
                "active_map_id": "shangri_la",
                "conversation_history": [
                    {
                        "role": "user",
                        "content": "Em quantas pessoas consigo fazer o EE principal?",
                    },
                    {
                        "role": "assistant",
                        "content": "O Easter Egg principal exige quatro jogadores.",
                        "source_paths": ["main_ee.md"],
                    },
                ],
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert not payload["need_clarification"]
        assert {source["path"] for source in payload["sources"]} == {"main_ee.md"}
        assert "4 jogadores" in payload["answer"]


def test_chat_rejects_model_image_ids_outside_retrieved_context() -> None:
    with TestClient(app) as client:
        client.app.state.llm = ImageSelectingLLM()
        response = client.post(
            "/chat",
            json={
                "message": "Onde fica a terceira peça do escudo?",
                "active_map_id": "der_eisendrache",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["answer"] == "Resposta de teste."
        assert len(payload["relevant_images"]) == 3
        assert {image["section"] for image in payload["relevant_images"]} == {
            "part 3 - underground frame"
        }
        assert {source["path"] for source in payload["sources"]} == {"shield.md"}


def test_chat_falls_back_to_one_image_per_procedure_section() -> None:
    with TestClient(app) as client:
        client.app.state.llm = NoImageLLM()
        response = client.post(
            "/chat",
            json={"message": "Como monto o Rocket Shield em Der Eisendrache?"},
        )

        assert response.status_code == 200
        payload = response.json()
        sections = {image["section"] for image in payload["relevant_images"]}
        assert sections == {
            "part 1 - double pipe item",
            "part 2 - griffin plate",
            "part 3 - underground frame",
        }


def test_chat_fills_visual_location_guide_from_one_section() -> None:
    with TestClient(app) as client:
        client.app.state.llm = NoImageLLM()
        response = client.post(
            "/chat",
            json={
                "message": "Onde ficam as bonecas da Samantha?",
                "active_map_id": "nacht_der_untoten",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert len(payload["relevant_images"]) == 6
        assert {image["section"] for image in payload["relevant_images"]} == {
            "Side easter egg - Samantha's dolls"
        }


def test_specific_chat_fails_cleanly_when_llm_is_unavailable() -> None:
    with TestClient(app) as client:
        client.app.state.llm = UnavailableLLM()
        response = client.post(
            "/chat",
            json={
                "message": "Onde fica a terceira peça do escudo?",
                "active_map_id": "der_eisendrache",
            },
        )

        assert response.status_code == 503
        assert "GROQ_API_KEY" in response.json()["detail"]
