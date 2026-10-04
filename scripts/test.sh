#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-18080}"
BASE_URL="http://localhost:$PORT"

TESTS_PASSED=0
TESTS_TOTAL=4

cleanup() {
    if [[ -n "${SERVER_PID:-}" ]]; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT

PORT="$PORT" ./scripts/run.sh > /tmp/city-facts-api-test.log 2>&1 &
SERVER_PID=$!

for i in {1..30}; do
    if curl -sf "$BASE_URL/healthz" > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

if ! curl -sf "$BASE_URL/healthz" > /dev/null 2>&1; then
    echo "Server failed to start"
    cat /tmp/city-facts-api-test.log
    exit 1
fi

if [[ "$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")" == "200" ]]; then
    ((TESTS_PASSED+=1))
fi

if [[ "$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/healthz")" == "200" ]]; then
    ((TESTS_PASSED+=1))
fi

if curl -sf "$BASE_URL/cities/Almaty" | grep -q "Almaty"; then
    ((TESTS_PASSED+=1))
fi

if [[ "$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/cities/Unknown")" == "404" ]]; then
    ((TESTS_PASSED+=1))
fi

echo "TESTS: $TESTS_PASSED/$TESTS_TOTAL"

if [[ "$TESTS_PASSED" -ne "$TESTS_TOTAL" ]]; then
    exit 1
fi