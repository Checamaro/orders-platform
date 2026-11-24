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

.PHONY: k8s-images k8s-apply k8s-e2e
k8s-images:
	for s in order-api order-worker notifier; do docker build -t orders-$$s:dev services/$$s && kind load docker-image orders-$$s:dev --name orders; done
	for i in postgres:16 apache/kafka:4.0.0; do docker pull $$i && kind load docker-image $$i --name orders; done
k8s-apply:
	kubectl apply -f deploy/k8s/ -n orders
k8s-e2e: venv
	API_URL=http://localhost:8088 .venv/bin/pytest -q tests/e2e

.PHONY: k8s-metrics
k8s-metrics:
	kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
	kubectl -n kube-system patch deployment metrics-server --type=json \
	  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
	kubectl -n kube-system rollout status deployment metrics-server --timeout=120s

k8s-apply: k8s-metrics
	kubectl apply -f deploy/k8s/ -n orders