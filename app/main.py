from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from app.db import Storage
from app.inference import Predictor
from app.observability import Metrics
from app.schemas import Prediction, Telemetry

ROOT = Path(__file__).resolve().parents[1]
LOGGER = logging.getLogger("fleet")


def create_app(database_url: str | None = None, model_path: str | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(api: FastAPI):
        url = database_url or os.getenv("DATABASE_URL", "sqlite:///storage/fleet.db")
        if os.getenv("RENDER") and not url.startswith(("postgres://", "postgresql://", "postgresql+psycopg://")):
            raise RuntimeError("Render requiere DATABASE_URL de PostgreSQL gestionado (Neon).")
        storage = Storage(url)
        try:
            await run_in_threadpool(storage.initialize)
            path = Path(model_path or os.getenv("MODEL_PATH", str(ROOT / "models/model.joblib")))
            api.state.predictor = await run_in_threadpool(Predictor, path)
            api.state.storage = storage
            api.state.metrics = Metrics()
            api.state.instance_id = uuid4().hex
            api.state.online_seconds = float(os.getenv("ROBOT_ONLINE_SECONDS", "30"))
            yield
        finally:
            await run_in_threadpool(storage.close)

    api = FastAPI(title="ACI606 Cloud Fleet", version="1.0.0", description="Telemetría persistente, inferencia de condición y operación de flotas.", lifespan=lifespan)

    @api.middleware("http")
    async def observe(request: Request, call_next):
        metrics = request.app.state.metrics
        metrics.request(request.method, request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            LOGGER.exception("Unhandled service error")
            response = JSONResponse(status_code=500, content={"detail": "Error interno del servicio"})
        metrics.response(response.status_code)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @api.exception_handler(RequestValidationError)
    async def invalid_input(_: Request, exc: RequestValidationError):
        # Raw validation input may contain NaN; exclude it so even errors are valid JSON.
        return JSONResponse(status_code=422, content={"detail": [
            {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]})

    @api.exception_handler(SQLAlchemyError)
    async def database_unavailable(_: Request, exc: SQLAlchemyError):
        LOGGER.error("Database operation failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Base de datos temporalmente no disponible"})

    @api.get("/", include_in_schema=False)
    def home():
        return RedirectResponse("/dashboard")

    @api.get("/health")
    def health(request: Request) -> dict:
        request.app.state.storage.ping()
        return {
            "status": "ok", "service": "aci606-cloud-fleet", "version": api.version,
            "database": request.app.state.storage.backend, "model_loaded": True,
            "instance_id": request.app.state.instance_id,
            "model_version": request.app.state.predictor.version,
            "utc": datetime.now(timezone.utc).isoformat(),
        }

    @api.post("/telemetry")
    def ingest(sample: Telemetry, request: Request) -> dict:
        prediction = request.app.state.predictor.predict(sample)
        request.app.state.metrics.inference(prediction.inference_ms, "telemetry")
        request.app.state.storage.save(sample.model_dump(), prediction.model_dump())
        return {"accepted": True, "robot_id": sample.robot_id, "server_time": datetime.now(timezone.utc).isoformat(), **prediction.model_dump(exclude={"robot_id"})}

    @api.get("/robots")
    def robots(request: Request) -> list[dict]:
        return request.app.state.storage.latest(request.app.state.online_seconds)

    @api.get("/robots/{robot_id}/history")
    def history(robot_id: str, request: Request, limit: int | None = Query(default=None, ge=1), offset: int = Query(default=0, ge=0)) -> list[dict]:
        storage = request.app.state.storage
        if not storage.exists(robot_id):
            raise HTTPException(status_code=404, detail="Robot no encontrado")
        return storage.history(robot_id, limit, offset)

    @api.post("/predict", response_model=Prediction)
    def predict(sample: Telemetry, request: Request) -> Prediction:
        result = request.app.state.predictor.predict(sample)
        request.app.state.metrics.inference(result.inference_ms, "predict")
        return result

    @api.get("/metrics")
    def metrics(request: Request) -> dict:
        state = request.app.state
        fleet = state.storage.latest(state.online_seconds)
        return {
            **state.metrics.snapshot(), "stored_samples": state.storage.count(),
            "robots_total": len(fleet), "online_robots": sum(r["connected"] for r in fleet),
            "persistence": state.storage.backend,
            "model": {"version": state.predictor.version, "name": state.predictor.name, **state.predictor.evaluation},
        }

    @api.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> str:
        return (ROOT / "dashboard/index.html").read_text(encoding="utf-8")

    return api


app = create_app()
