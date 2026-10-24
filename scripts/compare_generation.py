"""Explicit paid experiment: fixed sources, three generation strategies, no server changes."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import time
from dataclasses import replace
from pathlib import Path

from app import chat_service
from app.config import settings
from app.knowledge_base import KnowledgeBase
from app.llm import LLMService
from app.retrieval import SearchEngine
from app.schemas import ChatRequest
from scripts.compare_answer_audit import TimedLLM


class ExperimentLLM(TimedLLM):
    async def _provider_completion(self, client, provider, messages, model, contract):
        # Keep a local reference: concurrent requests finish in arbitrary order.
        attempt = {"stage": model.__name__, "provider": provider}
        self.attempts.append(attempt)
        started = time.monotonic()
        try:
            return await LLMService._provider_completion(
                self, client, provider, messages, model, contract
            )
        finally:
            attempt["seconds"] = round(time.monotonic() - started, 3)


async def experiment(args):
    if not args.live or not settings.paid_local_enabled:
        raise SystemExit("Requires --live and the existing paid local development opt-in.")
    if (args.output_dir / "summary.json").exists():
        raise SystemExit("Use a new output directory to preserve previous measurements.")
    config = replace(settings, local_llm_provider="openrouter", answer_audit_enabled=False)
    kb = KnowledgeBase(settings.maps_dir)
    search = SearchEngine(kb)
    cases = {c["id"]: c for c in json.loads(
        (settings.base_dir / "tests/fixtures/guide_completeness.json").read_text(encoding="utf-8")
    )["cases"]}
    cases["zetsubou-summary"] = {
        **cases["zetsubou-full"], "id": "zetsubou-summary",
        "message": "Como faço o Easter Egg principal?",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "model": "openai/gpt-oss-120b", "reasoning": "low", "temperature": 0.1,
        "provider": "openrouter", "max_tokens": 12000, "request_timeout_seconds": 90,
        "parallel_limit": 4, "audit_enabled": False,
        "single_prompt_scope_version": 2,
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=settings.base_dir, text=True,
        ).strip(),
        "note": "Includes working-tree experiment changes; see committed experiment report.",
    }
    (args.output_dir / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    original = chat_service._generate_plan
    original_settings = chat_service.settings
    chat_service.settings = config
    results = []
    try:
        for case_index, case_id in enumerate(args.cases):
            case = cases[case_id]
            frozen = None
            # Rotate first mode across cases to reduce ordering bias.
            offset = case_index % len(args.modes)
            modes = args.modes[offset:] + args.modes[:offset]
            for mode in modes:
                llm = ExperimentLLM(config)
                record = {"case": case_id, "mode": mode, "request": case,
                          "audit_enabled": False, "retrieval": "BM25", "generation_runs": []}

                async def generate(
                    *call_args, record=record, case_id=case_id, llm=llm, mode=mode, **kwargs,
                ):
                    nonlocal frozen
                    if len(call_args) > 9:  # Internal parallel/subdivision recursion.
                        return await original(*call_args, **kwargs)
                    # The first run prepares the plan once. All strategies receive the
                    # identical arguments, including full source content and source notes.
                    if frozen is None:
                        frozen = call_args[1:]
                    ids = [c.chunk.id for c in call_args[2].chunks]
                    expected = [c.chunk.id for c in frozen[1].chunks]
                    if ids != expected or call_args[1] != frozen[0]:
                        raise RuntimeError("Planning changed between arms; comparison invalid")
                    payload = {"plan": frozen[0].model_dump(), "sources": [
                        {"id": c.chunk.id, "content": c.chunk.content,
                         "images": list(c.chunk.image_ids)} for c in frozen[1].chunks
                    ]}
                    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
                    record["source_fingerprint"] = hashlib.sha256(serialized.encode()).hexdigest()
                    record["source_characters"] = sum(
                        len(c.chunk.content) for c in frozen[1].chunks
                    )
                    record["planned_sections"] = len(expected)
                    (args.output_dir / f"{case_id}-sources.json").write_text(
                        serialized, encoding="utf-8"
                    )
                    started = time.monotonic()
                    try:
                        return await original(llm, *frozen, _batch_mode=mode)
                    finally:
                        record["generation_runs"].append(round(time.monotonic() - started, 3))

                chat_service._generate_plan = generate
                print(f"START {case_id} {mode}", flush=True)
                started = time.monotonic()
                try:
                    response = await asyncio.wait_for(chat_service.answer_chat(
                        ChatRequest(
                            message=case["message"], active_map_id=case["map_id"],
                            response_mode="complete",
                        ),
                        kb, search, llm, lambda id_, variant: f"/media/{id_}?variant={variant}",
                    ), timeout=600)
                    paths = {s.path for s in response.sources}
                    missing = sorted(set(case.get("required_paths", [])) - paths)
                    for path, titles in case.get("required_sections", {}).items():
                        actual = {s.section for s in response.sources if s.path == path}
                        missing.extend(f"{path}:{t}" for t in titles if t not in actual)
                    excluded = sorted(set(case.get("excluded_paths", [])) & paths)
                    record.update(
                        structural_ok=(
                            not missing and not excluded and not response.need_clarification
                        ),
                        missing=missing, excluded=excluded, response=response.model_dump(),
                        blocks=len(response.blocks), images=len(response.relevant_images),
                        words=sum(len(b.body.split()) for b in response.blocks),
                    )
                except Exception as error:
                    record.update(structural_ok=False, error=str(getattr(error, "detail", error)))
                finally:
                    record.update(seconds=round(time.monotonic() - started, 3),
                                  calls=llm.calls, attempts=llm.attempts,
                                  cost_usd=sum(c["cost_usd"] or 0 for c in llm.calls))
                    (args.output_dir / f"{case_id}-{mode}.json").write_text(
                        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    summary = {k: v for k, v in record.items() if k not in {"response", "request"}}
                    results.append(summary)
                    (args.output_dir / "summary.json").write_text(
                        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    print("RESULT " + json.dumps({k: v for k, v in summary.items()
                                                   if k not in {"calls", "attempts"}}), flush=True)
                    clients = {id(c): c for c in (llm._client, llm._paid_client) if c is not None}
                    for client in clients.values():
                        await client.close()
    finally:
        chat_service._generate_plan = original
        chat_service.settings = original_settings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", default=[
        "gorod-base-shield", "shadows-pap", "zetsubou-pap", "origins-full", "zetsubou-summary",
    ])
    parser.add_argument("--modes", nargs="+", choices=["sequential", "single", "parallel"],
                        default=["sequential", "single", "parallel"])
    asyncio.run(experiment(parser.parse_args()))
