#!/usr/bin/env bash
set -euo pipefail
N="${N:-200}"; API="${API_URL:-http://localhost:8080}"
for i in $(seq 1 "$N"); do
  curl -s -o /dev/null -X POST "$API/orders" -H 'Content-Type: application/json' -d "{\"item\":\"item-$i\",\"qty\":1}" &
done
wait
echo "sent $N orders"