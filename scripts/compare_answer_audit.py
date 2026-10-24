"""Explicit, paid local A/B experiment; never run as part of the automated suite."""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from dataclasses import replace
from pathlib import Path

from app import chat_service
from app.chunking import remove_image_reference_lines
from app.config import settings
from app.knowledge_base import KnowledgeBase
from app.llm import LLMService
from app.retrieval import SearchEngine
from app.schemas import ChatRequest


class TimedLLM(LLMService):
    def __post_init__(self):
        super().__post_init__()
        self.calls = []
        self.attempts = []

    async def _provider_completion(self, client, provider, messages, model, contract):
        started = time.monotonic()
        self.attempts.append({"stage": model.__name__, "provider": provider})
        try:
            return await super()._provider_completion(client, provider, messages, model, contract)
        finally:
            self.attempts[-1]["seconds"] = round(time.monotonic() - started, 3)

    def _record_usage(self, response, provider, model_name, stage):
        super()._record_usage(response, provider, model_name, stage)
        usage = getattr(response, "usage", None)
        self.calls.append({
            "stage": stage,
            "provider": provider,
            "upstream_provider": getattr(response, "provider", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "cost_usd": getattr(usage, "cost", None),
        })
        print(f"  completed {stage}", flush=True)


def markdown_sizes(kb):
    rows = []
    for map_id, record in kb.maps.items():
        texts = [(record.directory / p).read_text(encoding="utf-8") for p in record.document_paths]
        raw = "\n".join(texts)
        text = remove_image_reference_lines(raw)
        rows.append({
            "map": map_id, "documents": len(texts), "markdown_chars": len(raw),
            "text_chars_without_image_references": len(text), "words": len(text.split()),
        })
    return sorted(rows, key=lambda row: -row["markdown_chars"])


async def run_case(case, enabled, kb, search, output_dir):
    config = replace(settings, local_llm_provider="openrouter", answer_audit_enabled=enabled)
    chat_service.settings = config
    llm = TimedLLM(config)
    label = case["id"] + ("-audit-on" if enabled else "-audit-off")
    record = {"case": case["id"], "audit_enabled": enabled, "request": case}
    print("START " + label, flush=True)
    started = time.monotonic()
    try:
        response = await asyncio.wait_for(
            chat_service.answer_chat(
                ChatRequest(
                    message=case["message"], active_map_id=case["map_id"],
                    response_mode="complete",
                ),
                kb, search, llm, lambda id_, variant: f"/media/{id_}?variant={variant}",
            ), timeout=600,
        )
        paths = {s.path for s in response.sources}
        missing = sorted(set(case.get("required_paths", [])) - paths)
        for path, sections in case.get("required_sections", {}).items():
            actual = {s.section for s in response.sources if s.path == path}
            missing.extend(f"{path}:{title}" for title in sections if title not in actual)
        excluded = sorted(set(case.get("excluded_paths", [])) & paths)
        record.update(
            ok=not missing and not excluded and not response.need_clarification,
            missing=missing, excluded=excluded, response=response.model_dump(),
            blocks=len(response.blocks), images=len(response.relevant_images),
            response_words=sum(len(b.body.split()) for b in response.blocks),
        )
    except Exception as error:
        record.update(ok=False, error=str(getattr(error, "detail", error)))
    finally:
        record.update(
            seconds=round(time.monotonic() - started, 3), calls=llm.calls,
            attempts=llm.attempts, stages=dict(Counter(c["stage"] for c in llm.calls)),
            prompt_tokens=sum(c["prompt_tokens"] or 0 for c in llm.calls),
            completion_tokens=sum(c["completion_tokens"] or 0 for c in llm.calls),
            cost_usd=sum(c["cost_usd"] or 0 for c in llm.calls),
        )
        (output_dir / f"{label}.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("RESULT " + json.dumps({
            k: v for k, v in record.items()
            if k not in {"response", "request", "calls", "attempts"}
        }, ensure_ascii=False), flush=True)
        clients = {id(c): c for c in (llm._client, llm._paid_client) if c is not None}
        for client in clients.values():
            await client.close()
    return {k: v for k, v in record.items() if k not in {"response", "request", "attempts"}}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Explicitly spend local API credit.")
    parser.add_argument("--output-dir", type=Path, default=settings.cache_dir / "audit-comparison")
    parser.add_argument(
        "--cases", nargs="+",
        choices=["gorod-base-shield", "origins-full", "zetsubou-summary"],
    )
    parser.add_argument("--reverse-order", action="store_true")
    args = parser.parse_args()
    if not args.live or not settings.paid_local_enabled:
        parser.error("Requires --live and the existing local development paid opt-in.")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    kb = KnowledgeBase(settings.maps_dir)
    search = SearchEngine(kb)  # Same local retrieval for both arms; no Voyage/network variance.
    fixtures = json.loads(
        (settings.base_dir / "tests/fixtures/guide_completeness.json").read_text(encoding="utf-8")
    )["cases"]
    cases = {c["id"]: c for c in fixtures}
    cases["zetsubou-summary"] = {
        "id": "zetsubou-summary", "map_id": "zetsubou_no_shima",
        "message": "Como faço o Easter Egg principal?",
        "required_paths": cases["zetsubou-full"]["required_paths"],
        "excluded_paths": cases["zetsubou-full"]["excluded_paths"],
    }
    sizes = markdown_sizes(kb)
    (args.output_dir / "markdown-sizes.json").write_text(
        json.dumps(sizes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Alternate which arm runs first; requests themselves remain sequential.
    order = [
        ("gorod-base-shield", True), ("gorod-base-shield", False),
        ("origins-full", False), ("origins-full", True),
        ("zetsubou-summary", True), ("zetsubou-summary", False),
    ]
    if args.cases:
        order = [(case, enabled) for case, enabled in order if case in args.cases]
    if args.reverse_order:
        order = [(case, not enabled) for case, enabled in order]
    results = []
    try:
        for case, enabled in order:
            results.append(await run_case(cases[case], enabled, kb, search, args.output_dir))
            (args.output_dir / "summary.json").write_text(
                json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
            )
    finally:
        chat_service.settings = settings


if __name__ == "__main__":
    asyncio.run(main())
