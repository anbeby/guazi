#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

action=${1:-}
checkpoint=${2:-}
deploy=/home/zhaopeng/guazi/deploy
compose=$deploy/docker-compose.production-v1.yml
old_image=gz-admin-web:v1.1-rc1
new_image=gz-admin-web:v1.1-guardfix-20261014

case "$checkpoint" in
  /data/guazi/backups/v11-guardfix-*) ;;
  *) echo 'Provide a v11-guardfix checkpoint under /data/guazi/backups' >&2; exit 2 ;;
esac
[ -f "$checkpoint/docker-compose.production-v1.yml" ] || { echo 'Compose backup missing' >&2; exit 2; }
cd "$deploy"

dc() { docker-compose -p guazi -f "$compose" "$@"; }
wait_web() {
  local attempt
  for attempt in $(seq 1 45); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' gz-admin-web 2>/dev/null || true)" = healthy ] && return 0
    sleep 2
  done
  echo 'gz-admin-web did not become healthy' >&2
  return 1
}
check_gateway() {
  local path
  for path in /ready / /login /supply /procurement /403; do
    curl -fsS --connect-timeout 5 --max-time 10 -o /dev/null "http://127.0.0.1:18083$path"
  done
}
restore() {
  cp -p "$checkpoint/docker-compose.production-v1.yml" "$compose"
  dc config -q
  dc up -d --no-build --no-deps --force-recreate admin-web
  wait_web
  docker exec gz-nginx nginx -s reload
  check_gateway
  printf 'rolled-back\n' > "$checkpoint/state"
}

case "$action" in
  apply)
    [ "$(grep -F -c "image: $old_image" "$compose")" -eq 1 ] || { echo 'Expected old image reference not found exactly once' >&2; exit 2; }
    docker image inspect "$old_image" "$new_image" gz-admin-web:pre-guardfix-20261014 > /dev/null
    printf 'deploying\n' > "$checkpoint/state"
    on_error() {
      local rc=$?
      trap - ERR
      echo 'Deployment failed; restoring previous guazi web image and Compose' >&2
      restore || echo 'Automatic restore failed; inspect checkpoint' >&2
      exit "$rc"
    }
    trap on_error ERR
    python3 - "$compose" "$old_image" "$new_image" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
old = f"image: {sys.argv[2]}"
new = f"image: {sys.argv[3]}"
content = path.read_text(encoding="utf-8")
if content.count(old) != 1:
    raise SystemExit("Expected old image reference exactly once")
path.write_text(content.replace(old, new), encoding="utf-8")
PY
    dc config -q
    dc up -d --no-build --no-deps --force-recreate admin-web
    wait_web
    docker exec gz-nginx nginx -s reload
    check_gateway
    [ "$(docker inspect -f '{{.Config.Image}}' gz-admin-web)" = "$new_image" ]
    printf 'released\n' > "$checkpoint/state"
    trap - ERR
    echo "Web guard fix released; checkpoint: $checkpoint"
    ;;
  rollback)
    restore
    echo "Web guard fix rolled back; checkpoint: $checkpoint"
    ;;
  *) echo 'Usage: release-v11-guardfix-web.sh apply|rollback /data/guazi/backups/v11-guardfix-TIMESTAMP' >&2; exit 2 ;;
esac
