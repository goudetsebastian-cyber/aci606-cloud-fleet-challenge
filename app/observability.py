from collections import Counter, deque
from threading import Lock
from time import monotonic
import numpy as np


class Metrics:
    """Process counters. Telemetry and its predictions are stored in PostgreSQL."""
    def __init__(self):
        self.lock = Lock()
        self.started = monotonic()
        self.counts: Counter = Counter()
        self.codes: Counter = Counter()
        self.latencies = deque(maxlen=2000)
        self.latency_sum = 0.0

    def request(self, method: str, path: str) -> None:
        with self.lock:
            self.counts["requests_total"] += 1
            if method == "POST" and path in ("/telemetry", "/predict"):
                self.counts["telemetry_requests" if path == "/telemetry" else "prediction_requests"] += 1

    def response(self, status: int) -> None:
        with self.lock:
            self.codes[str(status)] += 1
            if status >= 400:
                self.counts["errors"] += 1
                self.counts["client_errors" if status < 500 else "server_errors"] += 1

    def inference(self, latency: float, source: str) -> None:
        with self.lock:
            self.counts["inferences_completed"] += 1
            self.counts[source + "_inferences"] += 1
            self.latency_sum += latency
            self.latencies.append(latency)

    def snapshot(self) -> dict:
        with self.lock:
            uptime = max(0.001, monotonic() - self.started)
            data = {key: self.counts[key] for key in (
                "requests_total", "telemetry_requests", "prediction_requests", "errors", "client_errors",
                "server_errors", "inferences_completed", "telemetry_inferences", "predict_inferences",
            )}
            data.update(
                uptime_seconds=round(uptime, 3), requests_per_second=round(self.counts["requests_total"] / uptime, 4),
                status_codes=dict(self.codes),
                average_prediction_latency_ms=round(self.latency_sum / max(1, self.counts["inferences_completed"]), 4),
                prediction_latency_p50_ms=round(float(np.percentile(self.latencies, 50)), 4) if self.latencies else 0.0,
                prediction_latency_p95_ms=round(float(np.percentile(self.latencies, 95)), 4) if self.latencies else 0.0,
                latency_window_samples=len(self.latencies),
                counters_scope="current_process; latency percentiles: last 2000 inferences",
            )
            return data
