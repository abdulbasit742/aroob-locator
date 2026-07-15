from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

import app as app_module
from locator import ShareStore


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setattr(app_module, "store", ShareStore())
    monkeypatch.setattr(app_module, "limiter", app_module.FixedWindowLimiter())
    with TestClient(app_module.app) as test_client:
        yield test_client


def fragment(url: str) -> dict[str, list[str]]:
    return parse_qs(urlparse(url).fragment)


def test_full_consent_flow_requires_separate_capabilities(client: TestClient):
    created = client.post("/api/shares", json={"label": "Check-in", "duration_minutes": 15})
    assert created.status_code == 200
    body = created.json()
    share = fragment(body["share_url"])
    viewer = fragment(body["viewer_url"])
    assert "accept=" not in urlparse(body["share_url"]).query
    assert "view=" not in urlparse(body["viewer_url"]).query

    share_id = body["share_id"]
    assert client.get(f"/api/shares/{share_id}/location").status_code == 401
    waiting = client.get(
        f"/api/shares/{share_id}/location",
        headers={"Authorization": f"Bearer {viewer['view'][0]}"},
    )
    assert waiting.json()["status"] == "awaiting_acceptance"

    accepted = client.post(
        f"/api/shares/{share_id}/accept",
        json={"accept_token": share["accept"][0], "precision": "approximate"},
    )
    assert accepted.status_code == 200
    upload_token = accepted.json()["upload_token"]

    uploaded = client.post(
        f"/api/shares/{share_id}/locations",
        headers={"Authorization": f"Bearer {upload_token}"},
        json={"latitude": 33.684456, "longitude": 73.047812, "accuracy_m": 9, "observed_at": datetime.now(timezone.utc).isoformat()},
    )
    assert uploaded.status_code == 200
    assert uploaded.json()["latitude"] == 33.684

    viewed = client.get(
        f"/api/shares/{share_id}/location",
        headers={"Authorization": f"Bearer {viewer['view'][0]}"},
    )
    assert viewed.status_code == 200
    assert viewed.json()["location"]["precision"] == "approximate"


def test_wrong_capability_cannot_read_or_stop(client: TestClient):
    body = client.post("/api/shares", json={"label": "Private", "duration_minutes": 15}).json()
    share_id = body["share_id"]
    bad = "x" * 43
    assert client.get(f"/api/shares/{share_id}/location", headers={"Authorization": f"Bearer {bad}"}).status_code == 403
    assert client.post(f"/api/shares/{share_id}/stop", headers={"Authorization": f"Bearer {bad}"}).status_code == 403


def test_stop_erases_latest_point(client: TestClient):
    body = client.post("/api/shares", json={"label": "Private", "duration_minutes": 15}).json()
    share = fragment(body["share_url"]); viewer = fragment(body["viewer_url"]); share_id = body["share_id"]
    upload = client.post(f"/api/shares/{share_id}/accept", json={"accept_token": share["accept"][0], "precision": "exact"}).json()["upload_token"]
    client.post(
        f"/api/shares/{share_id}/locations",
        headers={"Authorization": f"Bearer {upload}"},
        json={"latitude": 1, "longitude": 2, "accuracy_m": 5, "observed_at": datetime.now(timezone.utc).isoformat()},
    )
    stopped = client.post(f"/api/shares/{share_id}/stop", headers={"Authorization": f"Bearer {viewer['view'][0]}"})
    assert stopped.status_code == 200
    after = client.get(f"/api/shares/{share_id}/location", headers={"Authorization": f"Bearer {viewer['view'][0]}"}).json()
    assert after["status"] == "stopped"
    assert after["location"] is None


def test_security_headers_and_same_origin_assets(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["permissions-policy"].startswith("geolocation=(self)")
    html = response.text
    assert "https://" not in html
    assert "<script type=\"module\" src=\"/assets/index.js\"" in html
