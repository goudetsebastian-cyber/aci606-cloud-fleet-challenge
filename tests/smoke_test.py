"""Public contract smoke test; --final also enforces prediction and robustness."""
import argparse
import json
from pathlib import Path
import time
import requests

SAMPLE = {"robot_id": "SMOKE-01", "timestamp": 1780000000., "x": 1.2, "y": 3.4, "speed": .72, "battery": 81., "motor_temp": 49., "vibration": .42, "motor_current": 3.8, "obstacle_distance": 1.3}


def run(base: str, final: bool, timeout: float) -> dict:
    checks = []
    with requests.Session() as session:
        def check(method, path, *, expected=200, **kwargs):
            response = session.request(method, base.rstrip("/") + path, timeout=timeout, **kwargs)
            assert response.status_code == expected, f"{method} {path}: {response.status_code} {response.text[:150]}"
            checks.append({"method": method, "path": path, "status": response.status_code})
            print(f"{method:4} {path:36} {response.status_code}", flush=True)
            return response
        health = check("GET", "/health").json()
        sample = {**SAMPLE, "timestamp": time.time()}
        check("POST", "/telemetry", json=sample)
        robots = check("GET", "/robots").json()
        assert any(r["robot_id"] == sample["robot_id"] for r in robots)
        history = check("GET", "/robots/SMOKE-01/history").json()
        assert len(history) >= 1
        check("GET", "/metrics")
        assert "text/html" in check("GET", "/dashboard").headers["Content-Type"]
        if final:
            prediction = check("POST", "/predict", json=sample).json()
            assert set(prediction) == {"robot_id", "predicted_status", "confidence", "model_version", "inference_ms"}
            assert prediction["robot_id"] == sample["robot_id"] and prediction["predicted_status"] in {"NORMAL", "WARNING", "CRITICAL"}
            assert 0 <= prediction["confidence"] <= 1 and prediction["inference_ms"] >= 0 and prediction["model_version"]
            check("POST", "/predict", json={"robot_id": "MISSING"}, expected=422)
            check("POST", "/telemetry", json={**sample, "battery": 101}, expected=422)
            check("POST", "/predict", data=json.dumps({**sample, "vibration": float("nan")}), headers={"Content-Type": "application/json"}, expected=422)
            check("GET", "/health")
    return {"api_url": base, "final": final, "passed": True, "health": health, "checks": checks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--final", action="store_true")
    parser.add_argument("--timeout", type=float, default=90, help="Allows the initial PaaS cold start")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = run(args.api, args.final, args.timeout)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print("Contrato verificado.")
    except (AssertionError, requests.RequestException, ValueError) as exc:
        raise SystemExit(str(exc))
