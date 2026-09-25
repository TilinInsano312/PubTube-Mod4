#!/usr/bin/env bash
set -Eeuo pipefail

gateway_port="${GATEWAY_PORT:-8000}"
prometheus_port="${PROMETHEUS_PORT:-9090}"
gateway_base="http://127.0.0.1:${gateway_port}"
prometheus_base="http://127.0.0.1:${prometheus_port}"
deadline_seconds="${SMOKE_TIMEOUT_SECONDS:-120}"
poll_seconds="${SMOKE_POLL_SECONDS:-3}"

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

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
if any(
    target.get("labels", {}).get("job") == "pubtube-gateway"
    and target.get("health") == "up"
    for target in targets
):
    raise SystemExit(0)
raise SystemExit(1)
PY
  then
    rm -f "$targets_file"
    printf 'PASS: Prometheus target pubtube-gateway is up\n'
    break
  fi
  rm -f "$targets_file"
  if (( SECONDS >= deadline )); then
    fail "Prometheus target pubtube-gateway did not become up within ${deadline_seconds}s"
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
