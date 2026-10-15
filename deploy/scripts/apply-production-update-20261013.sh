#!/usr/bin/env bash
set -euo pipefail

# Run on 192.168.3.5 as zhaopeng after transferring the two verified archives.
base=/home/zhaopeng/guazi
data=/data/guazi
config_archive="$base/production-config-update-20261013.tar.gz"
image_archive="$data/backups/gz-api-20261013-update.tar.gz"

if [ "$#" -ne 1 ]; then
  echo 'Usage: apply-production-update-20261013.sh NEW_ADMIN_PASSWORD' >&2
  exit 2
fi
export GUAZI_ADMIN_PASSWORD="$1"

printf '%s  %s\n' \
  5d5c2f8b4e5ed0b822e24da2a8b22135eae94b7694d3b895265d691c19ed9bd8 "$config_archive" \
  5e6bcc28902f4302b35db98bb7e4ff38064290e5ecd06f3a18fc0a50fbf7068c "$image_archive" \
  | sha256sum -c -

cd "$base"
tar -xzf "$config_archive"
cd "$base/deploy"
python3 scripts/generate-production-compose-v1.py
docker-compose -p guazi -f docker-compose.production-v1.yml config -q

# Keep the previously working API image available for a fast rollback.
docker image tag gz-api:latest gz-api:before-20261013-update
gzip -dc "$image_archive" | docker load

# The seed password is for fresh database initialization only. Keep it aligned
# with the password changed through the authenticated API, without printing it.
python3 - <<'PY'
import os
from pathlib import Path

path = Path('/home/zhaopeng/guazi/deploy/.env')
lines = path.read_text(encoding='utf-8').splitlines()
matches = [i for i, line in enumerate(lines) if line.startswith('INITIAL_ADMIN_PASSWORD=')]
if len(matches) != 1:
    raise SystemExit('Expected exactly one INITIAL_ADMIN_PASSWORD entry')
lines[matches[0]] = 'INITIAL_ADMIN_PASSWORD=' + os.environ['GUAZI_ADMIN_PASSWORD']
tmp = path.with_name('.env.next')
tmp.write_text('\n'.join(lines) + '\n', encoding='utf-8')
tmp.chmod(0o600)
tmp.replace(path)
PY
unset GUAZI_ADMIN_PASSWORD

docker-compose -p guazi -f docker-compose.production-v1.yml up -d --no-build --no-deps --force-recreate api worker
docker-compose -p guazi -f docker-compose.production-v1.yml ps
