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