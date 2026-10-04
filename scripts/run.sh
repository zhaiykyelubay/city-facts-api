#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"

./gradlew bootRun --args="--server.port=$PORT"