from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_rejects_zero_qty():
    assert client.post("/orders", json={"item": "book", "qty": 0}).status_code == 422


def test_rejects_bad_id():
    assert client.get("/orders/not-a-uuid").status_code == 422