import json
import logging
import os
import signal
import time

import psycopg
from confluent_kafka import Consumer, Producer
from prometheus_client import Counter, Histogram, start_http_server

PROCESSED = Counter("orders_processed_total", "Orders processed")
DUPLICATES = Counter("orders_duplicates_total", "Duplicate events skipped")
E2E = Histogram("order_e2e_seconds", "Time from order creation to processing",
                buckets=(0.5, 1, 2, 5, 10, 30))
start_http_server(8001)   # /metrics на порту 8001

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("order-worker")

BOOT = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
DSN = os.getenv("DATABASE_URL", "postgresql://orders:orders@localhost:5432/orders")

running = True


def stop(*_):
    global running
    running = False


signal.signal(signal.SIGTERM, stop)   # docker stop шлёт SIGTERM — выходим аккуратно

consumer = Consumer({
    "bootstrap.servers": BOOT,
    "group.id": "order-workers",
    "enable.auto.commit": False,      # коммитим сами, после обработки
    "auto.offset.reset": "earliest",
})
producer = Producer({"bootstrap.servers": BOOT, "acks": "all", "enable.idempotence": True})
consumer.subscribe(["orders.created"])
conn = psycopg.connect(DSN, autocommit=True)

while running:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        log.error("kafka error: %s", msg.error())
        continue
    event = json.loads(msg.value())
    time.sleep(0.2)  # имитация работы
    cur = conn.execute(
        "UPDATE orders SET status = 'PROCESSED' WHERE id = %s AND status = 'NEW'",
        (event["order_id"],),
    )
    if cur.rowcount == 1:
        producer.produce("orders.processed", key=msg.key(), value=msg.value())
        producer.flush(5)
        PROCESSED.inc()                                   # 7.3: +1 обработанный заказ
        if "ts" in event:                                 # 7.3: старые события без ts пропускаем
            E2E.observe(time.time() - event["ts"])        # секунд от создания до обработки
        log.info("processed %s (partition %s)", event["order_id"], msg.partition())
    else:
        DUPLICATES.inc()                                  # 7.3: повтор — заказ уже PROCESSED
        log.info("skip duplicate %s", event["order_id"])   # идемпотентность
    consumer.commit(message=msg, asynchronous=False)

consumer.close()   # выйти из группы сразу — ребалансировка быстрее
conn.close()