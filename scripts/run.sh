#!/usr/bin/env bash
set -euo pipefail

PORT="${PORT:-8080}"

./mvnw spring-boot:run -Dspring-boot.run.arguments="--server.port=$PORT"