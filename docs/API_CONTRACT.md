# API contract

The evaluator assumes these routes exist:

- `GET /health`
- `POST /telemetry`
- `GET /robots`
- `GET /robots/{robot_id}/history`
- `POST /predict`
- `GET /metrics`
- `GET /dashboard`

Do not rename the required JSON fields used by `/predict` without instructor approval.


## Dashboard browser controls

The required evaluator routes above remain available. Browser controls use equivalent routes under `/dashboard/` to avoid browser filters on analytics paths.

- `GET /dashboard/data`: live health, fleet and metrics in one uncached response.
- `GET /dashboard/history/{robot_id}`: ordered telemetry history, optional `limit` and `offset`.
- `GET /dashboard/scenario`: six-robot scenario for the two-minute browser demonstration.
- `POST /dashboard/telemetry` and `POST /dashboard/predict`: same validation, persistence and model as the required API routes.
- `POST /dashboard/proofs`: JSON `{"request_id":"<32 lowercase hexadecimal characters>"}`. Saves exactly 125 samples and their reference atomically; replaying a request ID returns the same reference without duplicate writes.
- `GET /dashboard/proofs`: most recent 30 saved references, usable from a different device without local storage.
- `GET /dashboard/proofs/{proof_id}`: reference, current instance ID, `intact`, `restarted`, and `verified`. Confirmation requires all 125 rows to match SHA-256 and a different application instance.

The reference is retained in PostgreSQL; `?proof=<id>` opens it directly in the dashboard. The public exercise uses synthetic data. These routes do not grant permission to restart Render infrastructure.
