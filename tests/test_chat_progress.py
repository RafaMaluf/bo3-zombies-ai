import asyncio
import re
import time
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import chat_service
from app.chat_jobs import ChatJobs
from app.chat_progress import report_progress
from app.knowledge_base import KnowledgeBase
from app.llm import LLMResponseError
from app.main import app
from app.retrieval import SearchEngine
from app.schemas import ChatRequest, ChatResponse
from tests.test_planned_chat import PlannedLLM


@pytest.mark.asyncio
@pytest.mark.parametrize('ending', ['complete', 'fail', 'cancel'])
async def test_parallel_results_remain_private_until_the_entire_answer_is_ready(ending):
    kb = KnowledgeBase(Path(__file__).resolve().parent.parent / 'maps')
    gates = [asyncio.Event() for _ in range(4)]
    finished = [asyncio.Event() for _ in range(4)]
    entered = asyncio.Event()

    class ControlledLLM(PlannedLLM):
        active = 0

        async def answer(self, messages, **kwargs):
            index = len(self.calls)
            result = await super().answer(messages, **kwargs)
            self.active += 1
            if len(self.calls) == 4:
                entered.set()
            try:
                await gates[index].wait()
                if ending == 'fail' and index == 2:
                    raise LLMResponseError('Controlled late failure')
                return result
            finally:
                self.active -= 1
                finished[index].set()

    llm = ControlledLLM()
    jobs = ChatJobs()

    async def generate():
        return await chat_service.answer_chat(
            ChatRequest(
                message='EE de Origins completo', active_map_id='origins',
                response_mode="complete",
            ),
            kb, SearchEngine(kb), llm, lambda i, v: f'/{i}/{v}',
        )

    job = jobs.start(generate)
    try:
        await asyncio.wait_for(entered.wait(), 10)
        for index in (1, 0, 3):
            gates[index].set()
            await finished[index].wait()
            snapshot = jobs.get(job.job_id)
            assert snapshot.state == 'pending'
            assert snapshot.phase == 'generating'
            assert snapshot.response is None
            assert 'partial_response' not in snapshot.model_dump()
        if ending == 'cancel':
            await jobs.cancel(job.job_id)
        else:
            gates[2].set()
            await jobs.jobs[job.job_id].task
        final = jobs.get(job.job_id)
        assert llm.active == 0
        if ending == 'complete':
            assert final.phase == 'completed'
            assert len(final.response.blocks) == 23
            ids = [i.id for i in final.response.relevant_images]
            assert len(ids) == len(set(ids)) == 133
            assert [b.source_ids for b in final.response.blocks] == [
                [source] for call in llm.calls
                for source in re.findall(r'\[SOURCE ([^\]]+)\]', call[-1]['content'])
            ]
        else:
            assert final.state == 'failed'
            assert final.phase == ('failed' if ending == 'fail' else 'cancelled')
            assert final.status_code == (502 if ending == 'fail' else 499)
            assert final.response is None
    finally:
        await jobs.close()


@pytest.mark.asyncio
async def test_progress_is_isolated_between_jobs_and_observer_is_restored():
    jobs = ChatJobs()
    gate = asyncio.Event()

    async def generate(label):
        report_progress('planning' if label == 'A' else 'searching')
        await gate.wait()
        return ChatResponse(answer=label + ' complete')

    a = jobs.start(lambda: generate('A'))
    b = jobs.start(lambda: generate('B'))
    await asyncio.sleep(0)
    report_progress('reviewing')
    assert jobs.get(a.job_id).phase == 'planning'
    assert jobs.get(b.job_id).phase == 'searching'
    assert jobs.get(a.job_id).response is None
    gate.set()
    await asyncio.gather(*(job.task for job in jobs.jobs.values()))
    assert jobs.get(a.job_id).response.answer == 'A complete'
    assert jobs.get(a.job_id).phase == 'completed'
    await jobs.close()


def test_http_deadline_never_exposes_a_partial_answer(monkeypatch):
    async def generate(*args):
        report_progress('generating')
        await asyncio.Event().wait()

    monkeypatch.setattr('app.main.answer_chat', generate)
    monkeypatch.setattr('app.main.settings', replace(
        chat_service.settings, chat_timeout_seconds=0.2,
    ))
    with TestClient(app) as client:
        id_ = client.post('/chat/jobs', json={'message': 'EE de Origins'}).json()['job_id']
        snapshot = client.get(f'/chat/jobs/{id_}')
        assert snapshot.headers['cache-control'] == 'no-store'
        assert snapshot.json()['phase'] == 'generating'
        assert snapshot.json()['response'] is None
        time.sleep(0.25)
        final = client.get(f'/chat/jobs/{id_}').json()
        assert final['status_code'] == 504
        assert final['phase'] == 'failed'
        assert final['response'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [False, True])
async def test_provider_failure_or_cancel_has_no_result_and_releases_capacity(failure):
    jobs = ChatJobs(max_active=1)
    gate = asyncio.Event()

    async def generate():
        report_progress('generating')
        await gate.wait()
        raise HTTPException(503, 'Provider unavailable')

    job = jobs.start(generate)
    await asyncio.sleep(0)
    if failure:
        gate.set()
        await jobs.jobs[job.job_id].task
    else:
        await jobs.cancel(job.job_id)
    final = jobs.get(job.job_id)
    assert final.response is None
    assert final.status_code == (503 if failure else 499)
    assert final.phase == ('failed' if failure else 'cancelled')
    next_job = jobs.start(lambda: asyncio.sleep(0, result=ChatResponse(answer='Next answer')))
    await jobs.jobs[next_job.job_id].task
    assert jobs.get(next_job.job_id).response.answer == 'Next answer'
    await jobs.close()
