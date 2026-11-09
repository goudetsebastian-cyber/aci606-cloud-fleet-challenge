"""Acceptance tests tied to the exercise's persistence and robustness criteria."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from app.main import create_app
from app.schemas import Telemetry

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = {"robot_id": "TEST-01", "timestamp": 1780000000.0, "x": 4.21, "y": 7.82, "speed": .63, "battery": 71., "motor_temp": 48.2, "vibration": .43, "motor_current": 3.7, "obstacle_distance": .42}


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(f"sqlite:///{(tmp_path / 'fleet.db').as_posix()}")) as instance:
        yield instance


def test_complete_contract_and_true_model(client):
    assert client.get("/health").json()["model_loaded"] is True
    prediction = client.post("/predict", json=SAMPLE)
    assert prediction.status_code == 200
    result = prediction.json()
    assert set(result) == {"robot_id", "predicted_status", "confidence", "model_version", "inference_ms"}
    assert result["predicted_status"] in {"NORMAL", "WARNING", "CRITICAL"}
    assert 0 <= result["confidence"] <= 1 and result["inference_ms"] >= 0
    assert result["model_version"].startswith("v1-")
    assert client.post("/telemetry", json=SAMPLE).json()["accepted"] is True
    robot = client.get("/robots").json()[0]
    assert robot["predicted_status"] == result["predicted_status"]
    assert robot["sample_count"] == 1 and robot["connected"] is True
    assert client.get("/robots/TEST-01/history").json()[0]["battery"] == SAMPLE["battery"]
    assert client.get("/dashboard").status_code == 200
    assert client.get("/docs").status_code == 200
    metrics = client.get("/metrics").json()
    assert metrics["prediction_requests"] == 1 and metrics["telemetry_requests"] == 1
    assert metrics["inferences_completed"] == 2 and metrics["stored_samples"] == 1
    scenario = client.get("/demo/scenario").json()
    assert scenario["duration_seconds"] == 120 and scenario["interval_seconds"] == 3
    assert len(scenario["frames"]) == 40
    for frame in scenario["frames"]:
        assert len(frame) == 6
        assert {sample["robot_id"] for sample in frame} == {f"R{i:02d}" for i in range(1, 7)}
        for sample in frame:
            Telemetry.model_validate(sample)
    assert client.get("/metrics").json()["stored_samples"] == 1


def test_more_than_100_samples_survive_a_new_service_instance(tmp_path):
    url = f"sqlite:///{(tmp_path / 'restart.db').as_posix()}"
    with TestClient(create_app(url)) as first:
        for i in range(130):
            assert first.post("/telemetry", json={**SAMPLE, "timestamp": SAMPLE["timestamp"] + i}).status_code == 200
        before = first.get("/robots/TEST-01/history").json()
    with TestClient(create_app(url)) as restarted:
        after = restarted.get("/robots/TEST-01/history").json()
        assert len(after) == 130 and after == before
        assert restarted.get("/metrics").json()["stored_samples"] == 130
        assert len(restarted.get("/robots/TEST-01/history?limit=10&offset=120").json()) == 10


def test_dashboard_data_contains_live_persisted_rows_without_tracking_requests(client):
    assert client.get("/dashboard/data").json()["robots"] == []
    assert client.post("/telemetry", json=SAMPLE).status_code == 200
    response = client.get("/dashboard/data")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["health"]["status"] == "ok"
    assert data["robots"][0]["robot_id"] == SAMPLE["robot_id"]
    assert data["robots"][0]["connected"] is True
    assert data["metrics"]["stored_samples"] == 1
    assert data["metrics"]["online_robots"] == 1


@pytest.mark.parametrize("path", ["/telemetry", "/predict"])
@pytest.mark.parametrize("change", [
    {"battery": -1}, {"battery": 101}, {"speed": -1}, {"vibration": -1},
    {"motor_current": -1}, {"obstacle_distance": -1}, {"timestamp": -1},
    {"battery": float("nan")}, {"x": float("inf")}, {"motor_temp": -float("inf")},
    {"robot_id": ""}, {"speed": "wrong"}, {"unexpected": 1}, {"battery": None},
    {"speed": True}, {"battery": "75.0"},
])
def test_invalid_input_is_4xx_and_service_survives(client, path, change):
    response = client.post(path, content=json.dumps({**SAMPLE, **change}), headers={"Content-Type": "application/json"})
    assert 400 <= response.status_code < 500, response.text
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").json()["server_errors"] == 0


@pytest.mark.parametrize("path", ["/telemetry", "/predict"])
def test_missing_and_malformed_body(client, path):
    assert client.post(path, json={"robot_id": "MISSING"}).status_code == 422
    assert client.post(path, content="{broken", headers={"Content-Type": "application/json"}).status_code == 422
    metrics = client.get("/metrics").json()
    assert metrics["client_errors"] == 2 and metrics["errors"] == 2


def test_latest_is_event_time_and_complete_history_is_ordered(client):
    for stamp in (100., 300., 200.):
        assert client.post("/telemetry", json={**SAMPLE, "timestamp": stamp}).status_code == 200
    assert client.get("/robots").json()[0]["timestamp"] == 300.
    assert [r["timestamp"] for r in client.get("/robots/TEST-01/history").json()] == [100., 200., 300.]
    assert client.get("/robots/unknown/history").status_code == 404
    assert client.get("/robots/TEST-01/history?limit=0").status_code == 422


def test_concurrent_requests_have_no_failures_or_lost_writes(client):
    def work(i):
        sample = {**SAMPLE, "robot_id": f"CONCURRENT-{i % 4}", "timestamp": time.time() + i}
        return client.post("/telemetry", json=sample).status_code, client.post("/predict", json=sample).status_code
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(work, range(48)))
    assert all(pair == (200, 200) for pair in results)
    metrics = client.get("/metrics").json()
    assert metrics["stored_samples"] == 48 and metrics["prediction_requests"] == 48
    assert metrics["telemetry_requests"] == 48 and metrics["server_errors"] == 0
    assert sum(len(client.get(f"/robots/CONCURRENT-{i}/history").json()) for i in range(4)) == 48


def test_database_failure_returns_sanitized_503(client, monkeypatch):
    def fail():
        raise OperationalError("sensitive-database-url", {}, Exception("secret"))
    monkeypatch.setattr(client.app.state.storage, "ping", fail)
    response = client.get("/health")
    assert response.status_code == 503
    assert "secret" not in response.text and "sensitive" not in response.text


def test_group_split_has_no_leakage():
    metadata = json.loads((ROOT / "models/metadata.json").read_text(encoding="utf-8"))
    assert set(metadata["train_fleets"]).isdisjoint(metadata["test_fleets"])
    assert metadata["test_macro_f1"] > metadata["baseline_macro_f1"]


def test_cloud_does_not_silently_use_ephemeral_sqlite(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        with TestClient(create_app("sqlite:///:memory:")):
            pass
