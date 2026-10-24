#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CREDIT_API_PROJECT="credit-pilot-api-$$"
CREDIT_API_ENV=$(mktemp /tmp/credit-pilot-api-env.XXXXXX)
cleanup() {
  rm -f "$CREDIT_API_ENV"
  docker compose -p "$CREDIT_API_PROJECT" -f compose.e2e.yaml down
}
trap cleanup EXIT
if curl --fail --silent http://localhost:5183/api/health >/dev/null 2>&1; then
  echo 'Port 5183 is occupied. Stop the existing test stack before API smoke.' >&2
  exit 1
fi
# These are disposable fixture accounts, never the user's .env credentials.
node - "$CREDIT_API_ENV" <<'JS'
const fs = require('fs');
fs.writeFileSync(process.argv[2], JSON.stringify({name:'Disposable local test',values:[
  {key:'baseUrl',value:'http://localhost:5183',enabled:true},
  {key:'clientPassword',value:'demo-client-a-local',enabled:true},
  {key:'bankPassword',value:'demo-bank-local',enabled:true}
]}));
JS
docker compose -p "$CREDIT_API_PROJECT" -f compose.e2e.yaml up -d --build
for CREDIT_API_ATTEMPT in $(seq 1 30); do
  if curl --fail --silent http://localhost:5183/api/health >/dev/null; then break; fi
  sleep 1
done
curl --fail --silent http://localhost:5183/api/health >/dev/null
docker compose -p "$CREDIT_API_PROJECT" -f compose.e2e.yaml exec -T backend python seed.py
npm exec --yes --package=newman@6.2.1 -- newman run api/CreditPilot.postman_collection.json -e "$CREDIT_API_ENV" --bail --reporters cli --reporter-cli-no-console
# Restart the application process: migrations and results must survive unchanged.
docker compose -p "$CREDIT_API_PROJECT" -f compose.e2e.yaml restart backend
for CREDIT_API_ATTEMPT in $(seq 1 30); do
  if curl --fail --silent http://localhost:5183/api/health >/dev/null; then break; fi
  sleep 1
done
curl --fail --silent http://localhost:5183/api/health >/dev/null
docker compose -p "$CREDIT_API_PROJECT" -f compose.e2e.yaml exec -T backend python - <<'PY'
import psycopg
from database import connection_parameters
with psycopg.connect(**connection_parameters()) as c:
    statuses=dict(c.execute('SELECT status,count(*) FROM applications GROUP BY status').fetchall())
    assert statuses == {'DISBURSED': 3, 'REJECTED': 1}, statuses
    assert c.execute('SELECT count(*) FROM decisions').fetchone()[0] == 4
    assert c.execute('SELECT count(*) FROM simulated_disbursements').fetchone()[0] == 3
print('API collection and restart: 3 DISBURSED, 1 REJECTED, 4 decisions, no duplicate disbursements.')
PY
