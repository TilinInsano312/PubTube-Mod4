#!/usr/bin/env bash
set -Eeuo pipefail

gateway_port="${GATEWAY_PORT:-8000}"
prometheus_port="${PROMETHEUS_PORT:-9090}"
jaeger_port="${JAEGER_UI_PORT:-16686}"
otel_service_name="${OTEL_SERVICE_NAME:-module4-gateway}"
gateway_base="http://127.0.0.1:${gateway_port}"
prometheus_base="http://127.0.0.1:${prometheus_port}"
jaeger_base="http://127.0.0.1:${jaeger_port}"
deadline_seconds="${SMOKE_TIMEOUT_SECONDS:-120}"
poll_seconds="${SMOKE_POLL_SECONDS:-3}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

printf 'Starting Gateway, Prometheus and tracing backend with docker compose\n'
docker compose up --build -d \
  || fail "Could not start Gateway, Prometheus and tracing backend with docker compose up --build -d"

wait_for_http_200() {
  local name="$1" url="$2" deadline=$((SECONDS + deadline_seconds))
  until curl --silent --show-error --fail --max-time 5 --output /dev/null "$url"; do
    if (( SECONDS >= deadline )); then
      fail "$name did not return HTTP 200 within ${deadline_seconds}s: $url"
    fi
    sleep "$poll_seconds"
  done
  printf 'PASS: %s is healthy (%s)\n' "$name" "$url"
}

wait_for_http_200 "Gateway" "${gateway_base}/api/health"
wait_for_http_200 "Prometheus" "${prometheus_base}/-/healthy"
wait_for_http_200 "Jaeger" "${jaeger_base}/api/services"

docker compose exec -T dashboard-api python -c \
  'import os, urllib.request; port = os.environ["DASHBOARD_PORT"]; urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=5)' \
  || fail "Dashboard internal healthcheck failed"
printf 'PASS: Dashboard is healthy on its private service port\n'

dashboard_result="$(mktemp)"
dashboard_status="$(curl --silent --show-error --max-time 10 \
  -H 'X-Correlation-Id: ci-dashboard-smoke' \
  --output "$dashboard_result" --write-out '%{http_code}' \
  "${gateway_base}/api/dashboard?from=invalid")" \
  || fail "Could not request Dashboard through Gateway"
if [[ "$dashboard_status" != "422" ]]; then
  rm -f "$dashboard_result"
  fail "Public Dashboard must validate dates without JWT; expected 422, got $dashboard_status"
fi
python3 - "$dashboard_result" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as source:
    response = json.load(source)
assert response.get("status") == "error"
assert response.get("code") == "INVALID_DATE_RANGE"
PY
rm -f "$dashboard_result"
printf 'PASS: Public Dashboard validates dates through Gateway without JWT\n'

curl --silent --show-error --fail --max-time 10 \
  -H 'X-Correlation-Id: ci-trace-smoke' \
  "${gateway_base}/api/health" --output /dev/null \
  || fail "Could not create a trace smoke request through ${gateway_base}/api/health"
printf 'PASS: Trace smoke request completed with correlation ID\n'

metrics_file="$(mktemp)"
trap 'rm -f "$metrics_file"' EXIT
curl --silent --show-error --fail --max-time 10 "$gateway_base/metrics" --output "$metrics_file" \
  || fail "Could not fetch Gateway metrics from ${gateway_base}/metrics"
for metric in pubtube_gateway_requests_total pubtube_gateway_request_duration_seconds; do
  if ! grep -Fq "$metric" "$metrics_file"; then
    fail "Gateway /metrics does not contain required metric: $metric"
  fi
done
printf 'PASS: Gateway exposes required HTTP metrics\n'

deadline=$((SECONDS + deadline_seconds))
while :; do
  traces_file="$(mktemp)"
  if ! curl --silent --show-error --fail --max-time 10 --get \
    --data-urlencode "service=${otel_service_name}" \
    --data-urlencode 'lookback=1h' \
    --data-urlencode 'limit=20' \
    "${jaeger_base}/api/traces" --output "$traces_file"; then
    rm -f "$traces_file"
    fail "Could not query Jaeger traces API"
  fi
  if python3 - "$traces_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    data = json.load(source)
traces = data.get("data", [])
if any(
    any(span.get("operationName") == "gateway.request" for span in trace.get("spans", []))
    for trace in traces
):
    raise SystemExit(0)
raise SystemExit(1)
PY
  then
    rm -f "$traces_file"
    printf 'PASS: Jaeger contains a %s gateway.request span\n' "$otel_service_name"
    break
  fi
  rm -f "$traces_file"
  if (( SECONDS >= deadline )); then
    fail "Jaeger did not receive a ${otel_service_name} gateway.request span within ${deadline_seconds}s"
  fi
  sleep "$poll_seconds"
done

deadline=$((SECONDS + deadline_seconds))
while :; do
  targets_file="$(mktemp)"
  if ! curl --silent --show-error --fail --max-time 10 \
    "${prometheus_base}/api/v1/targets" --output "$targets_file"; then
    rm -f "$targets_file"
    fail "Could not query Prometheus targets API"
  fi
  if python3 - "$targets_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    data = json.load(source)
targets = data.get("data", {}).get("activeTargets", [])
healthy_jobs = {
    target.get("labels", {}).get("job") for target in targets
    if target.get("health") == "up"
}
if {"pubtube-gateway", "pubtube-dashboard"} <= healthy_jobs:
    raise SystemExit(0)
raise SystemExit(1)
PY
  then
    rm -f "$targets_file"
    printf 'PASS: Prometheus targets pubtube-gateway and pubtube-dashboard are up\n'
    break
  fi
  rm -f "$targets_file"
  if (( SECONDS >= deadline )); then
    fail "Prometheus Gateway and Dashboard targets did not become up within ${deadline_seconds}s"
  fi
  sleep "$poll_seconds"
done

deadline=$((SECONDS + deadline_seconds))
while :; do
  query_file="$(mktemp)"
  if ! curl --silent --show-error --fail --max-time 10 --get \
    --data-urlencode 'query=up{job="pubtube-gateway"}' \
    "${prometheus_base}/api/v1/query" --output "$query_file"; then
    rm -f "$query_file"
    fail "Could not query Prometheus instant query API"
  fi
  if python3 - "$query_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as source:
    data = json.load(source)
results = data.get("data", {}).get("result", [])
if any(float(result.get("value", [None, "0"])[1]) == 1 for result in results):
    raise SystemExit(0)
raise SystemExit(1)
PY
  then
    rm -f "$query_file"
    printf 'PASS: Prometheus query up{job="pubtube-gateway"} returned 1\n'
    break
  fi
  rm -f "$query_file"
  if (( SECONDS >= deadline )); then
    fail "Prometheus query up{job=\"pubtube-gateway\"} did not return 1 within ${deadline_seconds}s"
  fi
  sleep "$poll_seconds"
done
