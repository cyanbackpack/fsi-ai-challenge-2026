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
    assert all(f["rebuttal"] for f in body["findings"])


def test_analyze_after_transfer_returns_emergency_steps():
    response = client.post(
        "/api/analyze",
        json={"text": "방금 송금했어요", "stage": "after_transfer"},
    )
    assert response.status_code == 200

    body = response.json()
    assert body["stage"] == "after_transfer"
    assert body["level"] == "critical"
    assert "지급정지" in body["actions"][0]["instruction"]


def test_analyze_rejects_unknown_stage():
    response = client.post("/api/analyze", json={"text": "x", "stage": "whenever"})
    assert response.status_code == 422


def test_analyze_rejects_oversized_text():
    response = client.post("/api/analyze", json={"text": "가" * 20_001})
    assert response.status_code == 422
