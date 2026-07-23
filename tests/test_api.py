from fastapi.testclient import TestClient

from app.main import app


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


def test_unknown_image_is_not_exposed_as_a_path() -> None:
    with TestClient(app) as client:
        response = client.get("/media/../../.env?variant=full")
        assert response.status_code == 404
