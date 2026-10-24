#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CREDIT_TEST_PROJECT="credit-pilot-e2e-$$"
cleanup() {
  docker compose -p "$CREDIT_TEST_PROJECT" -f compose.e2e.yaml unpause postgres >/dev/null 2>&1 || true
  docker compose -p "$CREDIT_TEST_PROJECT" -f compose.e2e.yaml down
}
trap cleanup EXIT
if curl --fail --silent http://localhost:5183/api/health >/dev/null 2>&1; then
  echo 'Port 5183 is occupied. Stop the existing test stack before running E2E.' >&2
  exit 1
fi
docker compose -p "$CREDIT_TEST_PROJECT" -f compose.e2e.yaml up -d --build
for CREDIT_TEST_ATTEMPT in $(seq 1 30); do
  if curl --fail --silent http://localhost:5183/api/health >/dev/null; then break; fi
  sleep 1
done
curl --fail --silent http://localhost:5183/api/health >/dev/null
# Verify health against a real database outage in this disposable project only.
docker compose -p "$CREDIT_TEST_PROJECT" -f compose.e2e.yaml pause postgres
CREDIT_HEALTH_CODE=$(curl --silent --output /dev/null --write-out '%{http_code}' http://localhost:5183/api/health)
test "$CREDIT_HEALTH_CODE" = 503
docker compose -p "$CREDIT_TEST_PROJECT" -f compose.e2e.yaml unpause postgres
for CREDIT_TEST_ATTEMPT in $(seq 1 30); do
  if curl --fail --silent http://localhost:5183/api/health >/dev/null; then break; fi
  sleep 1
done
curl --fail --silent http://localhost:5183/api/health >/dev/null
echo 'Isolated database outage/recovery: health 200 → 503 → 200.'
docker compose -p "$CREDIT_TEST_PROJECT" -f compose.e2e.yaml exec -T backend python seed.py
E2E_BASE_URL=http://localhost:5183 npm --prefix frontend run test:e2e
