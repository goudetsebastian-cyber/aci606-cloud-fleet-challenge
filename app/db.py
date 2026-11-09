"""Persistent telemetry. PostgreSQL in PaaS; SQLite only for local development."""
from __future__ import annotations
from pathlib import Path
import hashlib
import json
import time
from sqlalchemy import Column, Float, Index, Integer, MetaData, String, Table, create_engine, event, func, insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool
from sqlalchemy.exc import IntegrityError

METADATA = MetaData()
TELEMETRY = Table(
    "telemetry", METADATA,
    Column("id", Integer, primary_key=True),
    Column("robot_id", String(64), nullable=False),
    *[Column(name, Float, nullable=False) for name in (
        "timestamp", "x", "y", "speed", "battery", "motor_temp", "vibration", "motor_current", "obstacle_distance",
    )],
    Column("predicted_status", String(10), nullable=False),
    Column("confidence", Float, nullable=False),
    Column("model_version", String(80), nullable=False),
    Column("inference_ms", Float, nullable=False),
    Column("received_at", Float, nullable=False),
)
Index("ix_telemetry_robot_timestamp", TELEMETRY.c.robot_id, TELEMETRY.c.timestamp, TELEMETRY.c.id)
PROOFS = Table(
    "persistence_proofs", METADATA,
    Column("proof_id", String(32), primary_key=True),
    Column("robot_id", String(64), nullable=False),
    Column("count", Integer, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("before_instance_id", String(32), nullable=False),
    Column("created_at", Float, nullable=False),
)


def history_digest(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def normalize_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


class Storage:
    def __init__(self, url: str):
        parsed = make_url(normalize_url(url))
        self.backend = parsed.get_backend_name()
        options: dict = {"pool_pre_ping": True}
        if self.backend == "sqlite":
            if parsed.database and parsed.database != ":memory:":
                Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
            options["connect_args"] = {"check_same_thread": False, "timeout": 30}
            if parsed.database in (None, "", ":memory:"):
                options["poolclass"] = StaticPool
        else:
            options.update(pool_size=5, max_overflow=5, pool_recycle=240)
            options["connect_args"] = {"connect_timeout": 15}
        self.engine = create_engine(parsed, **options)
        if self.backend == "sqlite":
            @event.listens_for(self.engine, "connect")
            def sqlite_settings(connection, _):
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA busy_timeout=30000")

    def initialize(self) -> None:
        METADATA.create_all(self.engine)

    def ping(self) -> None:
        with self.engine.connect() as conn:
            conn.execute(text("SELECT 1"))

    def save(self, sample: dict, prediction: dict) -> None:
        row = {**sample, **{k: v for k, v in prediction.items() if k != "robot_id"}, "received_at": time.time()}
        with self.engine.begin() as conn:
            conn.execute(insert(TELEMETRY).values(**row))

    def latest(self, online_seconds: float) -> list[dict]:
        ranked = select(
            TELEMETRY,
            func.row_number().over(partition_by=TELEMETRY.c.robot_id, order_by=(TELEMETRY.c.timestamp.desc(), TELEMETRY.c.id.desc())).label("row_number"),
        ).subquery()
        counts = select(
            TELEMETRY.c.robot_id, func.count().label("sample_count"), func.max(TELEMETRY.c.received_at).label("last_seen"),
        ).group_by(TELEMETRY.c.robot_id).subquery()
        query = select(
            *[ranked.c[c.name] for c in TELEMETRY.c], counts.c.sample_count, counts.c.last_seen,
        ).join(counts, ranked.c.robot_id == counts.c.robot_id).where(ranked.c.row_number == 1).order_by(ranked.c.robot_id)
        with self.engine.connect() as conn:
            rows = [dict(row) for row in conn.execute(query).mappings()]
        now = time.time()
        for row in rows:
            row["connected"] = now - row["last_seen"] <= online_seconds
        return rows

    def history(self, robot_id: str, limit: int | None = None, offset: int = 0) -> list[dict]:
        query = select(TELEMETRY).where(TELEMETRY.c.robot_id == robot_id).order_by(TELEMETRY.c.timestamp, TELEMETRY.c.id).offset(offset)
        if limit is not None:
            query = query.limit(limit)
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(query).mappings()]

    def exists(self, robot_id: str) -> bool:
        with self.engine.connect() as conn:
            return conn.execute(select(TELEMETRY.c.id).where(TELEMETRY.c.robot_id == robot_id).limit(1)).first() is not None

    def count(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.scalar(select(func.count()).select_from(TELEMETRY)) or 0)

    def proofs(self) -> list[dict]:
        with self.engine.connect() as conn:
            return [dict(row) for row in conn.execute(select(PROOFS).order_by(PROOFS.c.created_at.desc()).limit(30)).mappings()]

    def proof(self, proof_id: str) -> dict | None:
        with self.engine.connect() as conn:
            row = conn.execute(select(PROOFS).where(PROOFS.c.proof_id == proof_id)).mappings().first()
            return dict(row) if row else None

    def save_proof(self, proof_id: str, rows: list[dict], instance_id: str) -> dict:
        existing = self.proof(proof_id)
        if existing:
            return existing
        try:
            with self.engine.begin() as conn:
                conn.execute(insert(TELEMETRY), [{**row, "received_at": time.time()} for row in rows])
                saved = [dict(row) for row in conn.execute(select(TELEMETRY).where(
                    TELEMETRY.c.robot_id == rows[0]["robot_id"]
                ).order_by(TELEMETRY.c.timestamp, TELEMETRY.c.id)).mappings()]
                reference = {"proof_id": proof_id, "robot_id": rows[0]["robot_id"], "count": len(saved),
                             "sha256": history_digest(saved), "before_instance_id": instance_id, "created_at": time.time()}
                if reference["count"] != 125:
                    raise ValueError("Expected exactly 125 samples")
                conn.execute(insert(PROOFS).values(**reference))
            return reference
        except IntegrityError:
            existing = self.proof(proof_id)
            if existing:
                return existing
            raise

    def close(self) -> None:
        self.engine.dispose()
