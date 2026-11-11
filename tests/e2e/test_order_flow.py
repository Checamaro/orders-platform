import os
import time

import httpx

API = os.getenv("API_URL", "http://localhost:8080")


def test_order_becomes_processed():
    r = httpx.post(f"{API}/orders", json={"item": "book", "qty": 1})
    assert r.status_code == 201
    order_id = r.json()["id"]
    deadline = time.time() + 30
    while time.time() < deadline:
        if httpx.get(f"{API}/orders/{order_id}").json()["status"] == "PROCESSED":
            return
        time.sleep(0.5)
    raise AssertionError(f"order {order_id} not processed in 30s")