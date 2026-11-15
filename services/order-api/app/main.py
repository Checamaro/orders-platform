import json
import os
import time
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import psycopg
from confluent_kafka import Producer
from fastapi import FastAPI, HTTPException, Request
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

DSN = os.getenv("DATABASE_URL", "postgresql://orders:orders@localhost:5432/orders")

producer = Producer({
    "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP", "localhost:9092"),
    "acks": "all",                 # подтверждение записи брокером
    "enable.idempotence": True,    # продюсер не создаёт дублей при повторах
})


class OrderIn(BaseModel):
    item: str = Field(min_length=1)
    qty: int = Field(gt=0)


def db():
    return psycopg.connect(DSN, autocommit=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    with db() as conn:  # учебно: таблица создаётся при старте; в проде — миграции (Alembic)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                 id UUID PRIMARY KEY,
                 item TEXT NOT NULL,
                 qty INT NOT NULL,
                 status TEXT NOT NULL DEFAULT 'NEW',
                 created_at TIMESTAMPTZ NOT NULL DEFAULT now())"""
        )
    yield


app = FastAPI(title="order-api", lifespan=lifespan)

REQUESTS = Counter("http_requests_total", "HTTP requests", ["route", "method", "status"])
LATENCY = Histogram(
    "http_request_duration_seconds", "Request latency", ["route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
@app.get("/metrics", include_in_schema=False)   # не показывать в Swagger
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    status = 500                       # если обработчик упал исключением — это 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")   # шаблон пути, не сам путь
        if not request.url.path.startswith("/metrics"):   # было: if path != "/metrics":
            REQUESTS.labels(path, request.method, str(status)).inc()
            LATENCY.labels(path).observe(time.perf_counter() - start)


@app.get("/health")
def health():
    with db() as conn:
        conn.execute("SELECT 1")
    return {"status": "ok"}


@app.post("/orders", status_code=201)
def create_order(order: OrderIn):
    order_id = uuid4()
    with db() as conn:
        conn.execute(
            "INSERT INTO orders (id, item, qty) VALUES (%s, %s, %s)",
            (order_id, order.item, order.qty),
        )
    event = {"order_id": str(order_id), "item": order.item, "qty": order.qty, "ts": time.time(),}
    producer.produce("orders.created", key=str(order_id), value=json.dumps(event))
    producer.flush(5)
    return {"id": str(order_id), "status": "NEW"}


@app.get("/orders/{order_id}")
def get_order(order_id: UUID):
    with db() as conn:
        row = conn.execute(
            "SELECT id, item, qty, status FROM orders WHERE id = %s", (order_id,)
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="order not found")
    return {"id": str(row[0]), "item": row[1], "qty": row[2], "status": row[3]}

