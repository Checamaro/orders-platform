import json
import logging
import os
import signal

from confluent_kafka import Consumer
from prometheus_client import Counter, start_http_server          # 7.3

SENT = Counter("notifications_sent_total", "Notifications sent")  # 7.3
start_http_server(8001)                                            # 7.3: /metrics на порту 8001

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("notifier")

BOOT = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

running = True


def stop(*_):
    global running
    running = False


signal.signal(signal.SIGTERM, stop)   # docker stop и Kubernetes шлют SIGTERM — выходим аккуратно
signal.signal(signal.SIGINT, stop)    # Ctrl+C при запуске руками

consumer = Consumer({
    "bootstrap.servers": BOOT,
    "group.id": "notifier",             # своя группа: свои offset, независимо от order-workers
    "enable.auto.commit": False,        # коммитим сами, после «отправки»
    "auto.offset.reset": "earliest",    # первый запуск — читать с начала топика
})
consumer.subscribe(["orders.processed"])
log.info("notifier started, bootstrap=%s", BOOT)

while running:
    msg = consumer.poll(1.0)
    if msg is None:
        continue
    if msg.error():
        log.error("kafka error: %s", msg.error())
        continue
    event = json.loads(msg.value())
    # здесь в настоящем сервисе было бы письмо или push; у нас — запись в лог
    log.info("notification sent for %s", event["order_id"])
    SENT.inc()                                         # 7.3: считаем после отправки, до коммита offset
    consumer.commit(message=msg, asynchronous=False)   # offset сдвигается только после отправки

consumer.close()   # выйти из группы сразу — ребалансировка быстрее