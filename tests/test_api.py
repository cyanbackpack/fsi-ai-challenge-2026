from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "llm_enabled" in body


def test_analyze_returns_scored_result():
    response = client.post("/api/analyze", json={"text": "지금 당장 OTP 알려주세요"})
    assert response.status_code == 200

    body = response.json()
    assert 0 <= body["score"] <= 100
    assert body["level"] in {"low", "medium", "high", "critical"}
    assert body["engine"] in {"hybrid", "rules-only", "llm-only"}


def test_analyze_rejects_oversized_text():
    response = client.post("/api/analyze", json={"text": "가" * 20_001})
    assert response.status_code == 422
