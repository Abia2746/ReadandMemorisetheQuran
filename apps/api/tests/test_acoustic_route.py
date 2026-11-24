from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import acoustic


@pytest.fixture
def acoustic_api(monkeypatch):
    app = FastAPI()
    app.include_router(acoustic.router)
    app.dependency_overrides[acoustic.current_user] = lambda: SimpleNamespace(id="test")
    app.state.redis = SimpleNamespace(eval=AsyncMock(return_value=1))
    model = {"model_id": "fixture", "verse_phone_references": {"1:1": ["a", "b", "c"]}}
    monkeypatch.setattr(acoustic, "load_approved_model", lambda: (None, model))
    inference = Mock(return_value={"phones": [{"phone": "b"}], "tajweed_verified": False})
    monkeypatch.setattr(acoustic, "analyse", inference)
    return TestClient(app), app.state.redis.eval, inference


def send(client, verse):
    return client.post("/api/acoustic/analyse", content=b"\x00\x10" * 5000,
                       headers={"Content-Type": "application/octet-stream", "X-Quran-Verse": verse})


def test_reference_checked_before_inference(acoustic_api):
    client, _, inference = acoustic_api
    assert client.get("/api/acoustic/capabilities?verse=1:2").json()["available"] is False
    assert send(client, "1:2").status_code == 503
    assert send(client, "1:8").status_code == 422
    inference.assert_not_called()


def test_quota_stops_inference(acoustic_api):
    client, counter, inference = acoustic_api
    counter.return_value = 31
    assert send(client, "1:1").status_code == 429
    inference.assert_not_called()


def test_short_window_candidate_only(acoustic_api):
    client, _, _ = acoustic_api
    report = send(client, "1:1").json()
    assert report["tajweed_verified"] is False
    assert [event["reference_index"] for event in report["alignment"]["events"]] == [1]
