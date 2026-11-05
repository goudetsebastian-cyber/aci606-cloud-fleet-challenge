"""Independent labelled fleets and concurrent client-side latency measurement."""
from concurrent.futures import ThreadPoolExecutor
import argparse
import json
from pathlib import Path
import sys
from threading import local
from time import perf_counter
import numpy as np
import requests
from sklearn.metrics import confusion_matrix, f1_score

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.generate_fleets import generate_rows


def run(api, fleets, samples, workers, seed):
    requests.get(api.rstrip("/") + "/health", timeout=90).raise_for_status()
    rows = generate_rows(fleets, samples, robots=8, seed=seed, scenario_shift=True)
    thread = local()
    def work(row):
        if not hasattr(thread, "session"):
            thread.session = requests.Session()
        sample = {key: value for key, value in row.items() if key not in {"fleet_id", "status"}}
        start = perf_counter()
        try:
            response = thread.session.post(api.rstrip("/") + "/predict", json=sample, timeout=30)
            response.raise_for_status()
            result = response.json()
            assert result["predicted_status"] in {"NORMAL", "WARNING", "CRITICAL"}
            assert 0 <= result["confidence"] <= 1
            return row["status"], result["predicted_status"], (perf_counter() - start) * 1000, None
        except (requests.RequestException, ValueError, KeyError, AssertionError) as exc:
            return row["status"], None, (perf_counter() - start) * 1000, type(exc).__name__
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(work, rows))
    valid = [result for result in results if result[3] is None]
    if not valid:
        raise RuntimeError("Todas las predicciones fallaron")
    truth, predictions, latencies, _ = zip(*valid)
    metadata = json.loads((ROOT / "models/metadata.json").read_text(encoding="utf-8"))
    majority = max(metadata["train_class_distribution"], key=metadata["train_class_distribution"].get)
    f1 = float(f1_score(truth, predictions, average="macro", labels=["NORMAL", "WARNING", "CRITICAL"], zero_division=0))
    baseline = float(f1_score(truth, [majority] * len(truth), average="macro", labels=["NORMAL", "WARNING", "CRITICAL"], zero_division=0))
    return {
        "api_url": api, "seed": seed, "fleets": fleets, "workers": workers,
        "scenario_shift": "new seeds/IDs; extra temperature noise (sd=.75), vibration x1.02, motor current x.98",
        "requests": len(results), "successful": len(valid), "errors": len(results) - len(valid),
        "macro_f1": f1, "baseline_macro_f1": baseline, "baseline_class": majority,
        "client_latency_p50_ms": float(np.percentile(latencies, 50)),
        "client_latency_p95_ms": float(np.percentile(latencies, 95)),
        "labels": ["NORMAL", "WARNING", "CRITICAL"],
        "confusion_matrix": confusion_matrix(truth, predictions, labels=["NORMAL", "WARNING", "CRITICAL"]).tolist(),
        "passed": len(valid) == len(results) and f1 > baseline,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--fleets", type=int, default=4)
    parser.add_argument("--samples-per-fleet", type=int, default=128)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--seed", type=int, default=9001)
    parser.add_argument("--output", type=Path, default=Path("reports/remote_evaluation.json"))
    args = parser.parse_args()
    if min(args.fleets, args.samples_per_fleet, args.workers) < 1:
        parser.error("fleets, samples-per-fleet y workers deben ser positivos")
    result = run(args.api, args.fleets, args.samples_per_fleet, args.workers, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
