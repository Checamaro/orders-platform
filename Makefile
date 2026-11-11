COMPOSE = docker compose -f deploy/compose/docker-compose.yml

.PHONY: up down logs ps
up:
	$(COMPOSE) up -d --build --wait
down:
	$(COMPOSE) down
logs:
	$(COMPOSE) logs -f --tail=100
ps:
	$(COMPOSE) ps
	
.PHONY: venv e2e load
venv:
	python3 -m venv .venv && .venv/bin/pip install -q pytest httpx
e2e: venv
	.venv/bin/pytest -q tests/e2e
load:
	bash scripts/load.sh