import os
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import psycopg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

DSN = os.getenv("DATABASE_URL", "postgresql://orders:orders@localhost:5432/orders")


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