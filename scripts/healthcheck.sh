#!/usr/bin/env bash
set -euo pipefail   # падать на ошибке, на неизвестной переменной, на ошибке в середине конвейера

THRESHOLD="${THRESHOLD:-80}"            # значения по умолчанию, переопределяются переменными
SERVICE="${SERVICE:-hello}"
URL="${URL:-http://localhost:8000}"
LOG="${LOG:-/var/log/healthcheck.log}"
status=0

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

usage=$(df --output=pcent / | tail -1 | tr -dc '0-9')
if (( usage > THRESHOLD )); then log "FAIL disk ${usage}%"; status=1; else log "OK disk ${usage}%"; fi

if systemctl is-active --quiet "$SERVICE"; then log "OK service $SERVICE"; else log "FAIL service $SERVICE"; status=1; fi

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$URL" || true)   # || true: иначе set -e уронит скрипт
if [[ "$code" == "200" ]]; then log "OK http $code"; else log "FAIL http $code"; status=1; fi

exit "$status"      # 0 — всё хорошо, 1 — что-то не так: это читают cron, systemd и CI