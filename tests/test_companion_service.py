import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.chat_service import answer_chat
from app.companion_models import CompanionExplanation, CompanionRequest, CompanionStart, MatchState
from app.companion_service import explain_companion, start_companion, update_companion
from app.companion_state import build_catalog
from app.knowledge_base import KnowledgeBase
from app.llm import LLMResponseError, LLMUnavailableError
from app.main import app
from app.retrieval import SearchEngine
from app.schemas import ChatRequest, ChatResponse, SelectedSource
from tests.test_llm_contract import completion, service
from tests.test_planned_chat import PlannedLLM


@pytest.fixture(scope="module")
def services():
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / "maps")
    return kb, build_catalog(kb, "origins"), None


class CompanionLLM(PlannedLLM):
    async def _validated_completion(self, messages, model, validate, *args):
        task = json.loads(messages[-1]["content"])
        result = model(titles=[o["title"] for o in task["objectives"]])
        assert not validate(result)
        return result


@pytest.mark.asyncio
async def test_start_only_builds_overview_then_completion_is_separate_from_generation(services):
    kb, _, _ = services
    llm = CompanionLLM()
    initial = await start_companion(CompanionStart(map_id="origins", player_count=2), kb, llm)
    assert initial.state.stage == "position"
    assert not initial.can_explain
    assert not llm.calls
    positioned = await update_companion(
        CompanionRequest(state=initial.state, message="Do início"), kb, llm
    )
    assert positioned.state.focus
    assert positioned.can_explain
    assert not positioned.question_mode
    assert positioned.state.player_count == 2
    first_id = positioned.state.focus

    async def no_model(*args, **kwargs):
        raise AssertionError("A completion must not call a model.")

    llm._validated_completion = no_model
    kb._companion_labels = {}
    completed = await update_companion(
        CompanionRequest(state=positioned.state, action="complete", objective_id=first_id), kb, llm
    )
    saved = completed.state.model_copy(deep=True)
    assert saved.statuses[first_id] == "complete"
    assert saved.focus != first_id
    llm.fail_batch = 1
    with pytest.raises(LLMResponseError):
        await explain_companion(
            CompanionExplanation(state=saved), kb, llm, lambda i, v: f"/{i}/{v}"
        )
    assert completed.state == saved
    assert saved.statuses[first_id] == "complete"


@pytest.mark.asyncio
async def test_current_objective_explanation_keeps_images_and_only_necessary_sources(services):
    kb, _, _ = services
    llm = CompanionLLM()
    initial = await start_companion(CompanionStart(map_id="origins"), kb, llm)
    current = await update_companion(
        CompanionRequest(state=initial.state, message="Do começo"), kb, llm
    )
    response = await explain_companion(
        CompanionExplanation(state=current.state), kb, llm, lambda i, v: f"/{i}/{v}"
    )
    assert response.blocks and response.relevant_images
    assert len({s.path for s in response.sources}) == 1
    assert response.guide is None
    assert current.state.statuses[current.state.focus] == "pending"


@pytest.mark.asyncio
async def test_outdated_complete_button_does_not_complete_another_objective(services):
    kb, _, _ = services
    llm = CompanionLLM()
    initial = await start_companion(CompanionStart(map_id="origins"), kb, llm)
    current = await update_companion(
        CompanionRequest(state=initial.state, message="Do início"), kb, llm
    )
    with pytest.raises(ValueError, match="mudou"):
        await update_companion(
            CompanionRequest(state=current.state, action="complete", objective_id="stale"), kb, llm
        )


def test_http_start_transition_and_explanation_job_share_existing_transport():
    with TestClient(app) as client:
        app.state.llm = CompanionLLM()
        initial = client.post("/companion/start", json={"map_id": "origins", "player_count": 1})
        assert initial.status_code == 200
        assert initial.headers["cache-control"] == "no-store"
        positioned = client.post(
            "/companion/action", json={"state": initial.json()["state"], "message": "Do início"}
        )
        assert positioned.status_code == 200
        saved = positioned.json()["state"]
        job = client.post("/companion/explain/jobs", json={"state": saved})
        assert job.status_code == 202
        id_ = job.json()["job_id"]
        result = client.get(f"/chat/jobs/{id_}").json()
        assert result["state"] == "completed"
        assert result["response"]["blocks"]
        assert result["response"]["relevant_images"]
        assert saved["statuses"][saved["focus"]] == "pending"
        saved["catalog_version"] = "outdated"
        assert (
            client.post("/companion/action", json={"state": saved, "action": "resume"}).status_code
            == 422
        )
        assert client.post("/companion/explain/jobs", json={"state": saved}).status_code == 422


def test_companion_provider_quota_failure_does_not_rewrite_saved_state():
    class Failing(CompanionLLM):
        async def answer(self, *args, **kwargs):
            raise LLMUnavailableError("Limite gratuito atingido. Tente amanhã.")

    with TestClient(app) as client:
        app.state.llm = Failing()
        initial = client.post("/companion/start", json={"map_id": "origins"}).json()
        saved = client.post(
            "/companion/action", json={"state": initial["state"], "message": "Do início"}
        ).json()["state"]
        job = client.post("/companion/explain/jobs", json={"state": saved}).json()
        result = client.get("/chat/jobs/" + job["job_id"]).json()
        assert result["state"] == "failed"
        assert result["status_code"] == 503
        assert result["response"] is None
        assert "amanhã" in result["error"]
        assert saved["stage"] == "active"


def test_targeted_quest_source_offers_companion_without_literal_ee_in_question(monkeypatch):
    async def answer(*args):
        return ChatResponse(
            answer="Use o G-Strike.",
            active_map_id="origins",
            sources=[
                SelectedSource(
                    chunk_id="source",
                    map_id="origins",
                    map_name="Origins",
                    path="main_ee.md",
                    section="Passagem",
                    score=1,
                ),
            ],
        )

    monkeypatch.setattr("app.main.answer_chat", answer)
    with TestClient(app) as client:
        response = client.post("/chat", json={"message": "Onde abro a passagem?"})
        assert response.status_code == 200
        assert response.json()["companion_offer_map_id"] == "origins"


@pytest.mark.asyncio
@pytest.mark.parametrize("question", ["O que falta?", "What remains?", "Que reste-t-il à faire ?"])
@pytest.mark.parametrize("active_map_id", [None, "origins"])
async def test_normal_chat_uses_saved_match_for_status_without_asking_for_a_guide(
    services, question, active_map_id
):
    kb, catalog, _ = services
    saved = MatchState(map_id="origins", catalog_version=catalog.version)
    before = saved.model_copy(deep=True)
    llm, calls = service(completion({"intent": "status", "reply": "Progress is unconfirmed."}))
    result = await answer_chat(
        ChatRequest(message=question, active_map_id=active_map_id, match_state=saved),
        kb,
        SearchEngine(kb),
        llm,
        lambda i, v: f"/{i}/{v}",
    )
    assert not result.need_clarification
    assert result.answer == "Progress is unconfirmed."
    assert len(calls.calls) == 1
    assert saved == before
