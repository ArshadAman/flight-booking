#!/usr/bin/env bash
# Sync flight-booking to VPS, migrate, run tests, restart services.
set -euo pipefail

VPS_HOST="${VPS_HOST:-root@72.61.21.201}"
REMOTE_DIR="${REMOTE_DIR:-/root/flight-booking}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "→ Syncing backend to ${VPS_HOST}:${REMOTE_DIR}"
rsync -avz --delete \
  --exclude '.git' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude 'staticfiles' \
  --exclude '.env' \
  "$LOCAL_DIR/" "${VPS_HOST}:${REMOTE_DIR}/"

echo "→ Migrate, test, restart on VPS"
ssh "${VPS_HOST}" bash -s <<EOF
set -euo pipefail
cd "${REMOTE_DIR}"
docker compose exec -T web python manage.py migrate --noinput
docker compose exec -T web python manage.py test bookings.tests agents.tests -v 1
docker compose restart web worker
echo "Backend deploy OK"
EOF
