import re

from fastapi.testclient import TestClient

from app.llm import LLMResponse, LLMUnavailableError
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


def test_health_maps_and_thumbnail_endpoints() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"
        assert health.json()["maps"] == 6

        maps = client.get("/maps")
        assert maps.status_code == 200
        map_payload = maps.json()
        assert len(map_payload) == 6

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
        assert len(payload["suggested_map_ids"]) == 6


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
        assert len(payload["relevant_images"]) == 1
        assert payload["relevant_images"][0]["section"] == "part 3 - underground frame"
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
