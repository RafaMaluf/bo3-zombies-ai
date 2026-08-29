from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class LiveCase:
    message: str
    active_map_id: str | None
    expected_path: str
    minimum_images: int


LIVE_CASES = (
    LiveCase(
        message="Onde fica a terceira peça do escudo?",
        active_map_id="der_eisendrache",
        expected_path="shield.md",
        minimum_images=1,
    ),
    LiveCase(
        message="Como faço os quatro rituais de Shadows of Evil?",
        active_map_id=None,
        expected_path="pap.md",
        minimum_images=1,
    ),
    LiveCase(
        message="Como viro uma aranha?",
        active_map_id="zetsubou_no_shima",
        expected_path="side_ee/spider_transformation.md",
        minimum_images=1,
    ),
)

EXPECTED_COUNTS = {
    "maps": 14,
    "documents": 166,
    "chunks": 602,
    "images": 1084,
}


class SmokeFailure(RuntimeError):
    pass


def _request(
    base_url: str,
    path: str,
    payload: dict[str, Any] | None = None,
    expected_status: int = 200,
) -> tuple[bytes, dict[str, str]]:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        f"{base_url.rstrip('/')}{path}",
        data=body,
        headers={
            "Accept": "application/json, image/webp, text/html, */*",
            "User-Agent": "Mozilla/5.0 Kronochat-Smoke/1.0",
            **({"Content-Type": "application/json"} if body is not None else {}),
        },
        method="POST" if body is not None else "GET",
    )
    try:
        with urlopen(request, timeout=45) as response:
            status = response.status
            content = response.read()
            headers = {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as error:
        status = error.code
        content = error.read()
        headers = {key.lower(): value for key, value in error.headers.items()}

    if status != expected_status:
        preview = content.decode("utf-8", errors="replace")[:500]
        raise SmokeFailure(
            f"{path} returned HTTP {status}; expected {expected_status}. Body: {preview}"
        )
    return content, headers


def _json(
    base_url: str,
    path: str,
    payload: dict[str, Any] | None = None,
    expected_status: int = 200,
) -> Any:
    body, _ = _request(base_url, path, payload, expected_status)
    return json.loads(body)


def run(base_url: str, *, live_chat: bool) -> None:
    health = _json(base_url, "/health")
    if health["status"] != "ok":
        raise SmokeFailure(f"Health is not ok: {health}")
    for field, expected in EXPECTED_COUNTS.items():
        if health[field] != expected:
            raise SmokeFailure(f"Health field {field} is {health[field]}; expected {expected}.")

    maps = _json(base_url, "/maps")
    expected_maps = EXPECTED_COUNTS["maps"]
    if len(maps) != expected_maps or len({item["map_id"] for item in maps}) != expected_maps:
        raise SmokeFailure(f"Map catalog must contain {expected_maps} unique maps.")
    for item in maps:
        cover_id = item["cover_image_id"]
        if not cover_id:
            raise SmokeFailure(f"{item['map_id']} has no cover image.")
        thumbnail, headers = _request(base_url, f"/media/{cover_id}?variant=thumb")
        if headers.get("content-type") != "image/webp":
            raise SmokeFailure(f"{item['map_id']} cover is not WebP.")
        if not (thumbnail.startswith(b"RIFF") and thumbnail[8:12] == b"WEBP"):
            raise SmokeFailure(f"{item['map_id']} cover has invalid WebP bytes.")

    home, _ = _request(base_url, "/app/")
    css, _ = _request(base_url, "/app/style.css")
    javascript, _ = _request(base_url, "/app/app.js")
    if b"Krono" not in home or len(css) < 10_000 or len(javascript) < 10_000:
        raise SmokeFailure("Frontend assets look incomplete.")

    _request(base_url, "/media/img_unknown?variant=full", expected_status=404)
    _json(base_url, "/chat", {"message": ""}, expected_status=422)
    clarification = _json(
        base_url,
        "/chat",
        {"message": "How do I unlock Pack-a-Punch?"},
    )
    if (
        not clarification["need_clarification"]
        or len(clarification["suggested_map_ids"]) != expected_maps
    ):
        raise SmokeFailure("Generic Pack-a-Punch question did not request a map.")

    if live_chat:
        if not health["llm_configured"]:
            raise SmokeFailure("--live-chat requires GROQ_API_KEY in the running service.")
        for case in LIVE_CASES:
            payload: dict[str, Any] = {"message": case.message}
            if case.active_map_id:
                payload["active_map_id"] = case.active_map_id
            response = _json(base_url, "/chat", payload)
            paths = {source["path"] for source in response["sources"]}
            if not response["answer"].strip():
                raise SmokeFailure(f"Live case returned an empty answer: {case.message}")
            if paths != {case.expected_path}:
                raise SmokeFailure(
                    f"Live case used {sorted(paths)} instead of {case.expected_path}: "
                    f"{case.message}"
                )
            if len(response["relevant_images"]) < case.minimum_images:
                raise SmokeFailure(f"Live case returned too few images: {case.message}")

    print(
        "Smoke test passed: "
        f"{health['maps']} maps, {health['documents']} documents, "
        f"{health['images']} images, live_chat={live_chat}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test a running Krono API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--live-chat", action="store_true")
    args = parser.parse_args()
    try:
        run(args.base_url, live_chat=args.live_chat)
    except (SmokeFailure, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Smoke test failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
