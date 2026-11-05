"""Two-phase verification across a real Render restart, without resetting data."""
import argparse
import hashlib
import json
from pathlib import Path
import time
import requests
from smoke_test import SAMPLE


def digest(rows):
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", required=True)
    parser.add_argument("--phase", choices=["before", "after"], required=True)
    parser.add_argument("--snapshot", type=Path, default=Path("reports/persistence_snapshot.json"))
    args = parser.parse_args()
    base = args.api.rstrip("/")
    with requests.Session() as session:
        health_response = session.get(base + "/health", timeout=90)
        health_response.raise_for_status()
        health = health_response.json()
        if args.phase == "before":
            robot_id = f"PERSIST-{int(time.time())}"
            for i in range(125):
                response = session.post(base + "/telemetry", json={**SAMPLE, "robot_id": robot_id, "timestamp": time.time() + i}, timeout=30)
                response.raise_for_status()
            response = session.get(base + f"/robots/{robot_id}/history", timeout=30)
            response.raise_for_status()
            rows = response.json()
            assert len(rows) == 125
            snapshot = {"api_url": base, "robot_id": robot_id, "count": len(rows), "sha256": digest(rows), "before_instance_id": health["instance_id"], "database": health["database"], "restart_verified": False}
            args.snapshot.parent.mkdir(parents=True, exist_ok=True)
            args.snapshot.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            print("125 muestras guardadas. Reiniciar el servicio en Render; después ejecutar --phase after.")
        else:
            snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
            assert snapshot["api_url"] == base, "La URL difiere de la fase before"
            assert health["instance_id"] != snapshot["before_instance_id"], "El servicio no se reinició: instance_id no cambió"
            response = session.get(base + f"/robots/{snapshot['robot_id']}/history", timeout=30)
            response.raise_for_status()
            rows = response.json()
            assert len(rows) == snapshot["count"] and digest(rows) == snapshot["sha256"], "El historial cambió"
            snapshot["restart_verified"] = True
            snapshot["after_instance_id"] = health["instance_id"]
            snapshot["verified_at_unix"] = time.time()
            args.snapshot.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
            print("Persistencia confirmada: 125/125 muestras idénticas al historial previo al reinicio.")
