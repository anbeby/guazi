#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

# Run as zhaopeng on 192.168.3.5. Internal-only V1.1 release.
# Never use `docker-compose` without -p guazi.
base=/home/zhaopeng/guazi
deploy="$base/deploy"
package="$base/releases/v1.1-rc1"
data=/data/guazi
active=docker-compose.production-v1.yml
candidate=docker-compose.production-v11.yml
run_dir=
release_active=0

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*"; }
fail() { log "ERROR: $*" >&2; return 1; }
dc() { docker-compose -p guazi -f "$1" "${@:2}"; }
version() { docker exec gz-postgres psql -U gz -d "$1" -Atc 'SELECT version_num FROM gz.alembic_version'; }
health() { docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$1"; }
lock_release() {
  exec 9>"$data/backups/.v11-release.lock"
  flock -n 9 || fail 'Another guazi release or rollback is running'
}
public_check() {
  local label=$1 url=$2 status
  status=$(curl -sS --connect-timeout 8 --max-time 15 -o /dev/null -w '%{http_code}' "$url") || fail "$label connection failed"
  [ "$status" = 200 ] || fail "$label returned HTTP $status"
  log "$label HTTP 200"
}

wait_healthy() {
  local attempt name ready
  for attempt in $(seq 1 60); do
    ready=1
    for name in "$@"; do
      if [ "$(health "$name" 2>/dev/null || true)" != healthy ]; then ready=0; fi
    done
    if [ "$ready" -eq 1 ]; then return 0; fi
    sleep 3
  done
  fail "Health timeout: $*"
}

dump_db() {
  local db=$1 dest=$2
  docker exec gz-postgres pg_dump -U gz -Fc "$db" > "$dest.part"
  docker exec -i gz-postgres pg_restore -l < "$dest.part" > /dev/null
  mv "$dest.part" "$dest"
  sha256sum "$dest" | tee -a "$run_dir/SHA256SUMS.txt"
}

preflight() {
  cd "$deploy"
  [ "$(grep -c '^COMPOSE_PROJECT_NAME=guazi$' .env)" -eq 1 ] || fail 'Compose project name is not fixed to guazi'
  dc "$active" config -q
  [ "$(version gz_platform)" = 0001_initial ] || fail 'Production migration is not 0001_initial'
  for name in gz-api gz-worker gz-admin-web gz-nginx; do
    [ "$(docker inspect -f '{{index .Config.Labels "com.docker.compose.project"}}' "$name")" = guazi ] || fail "$name has the wrong Compose project"
    [ "$(health "$name")" = healthy ] || fail "$name is not healthy"
  done
  [ "$(health gz-v11-test-api)" = healthy ] || fail 'V1.1 staging API is not healthy'
  [ "$(health gz-v11-test-web)" = healthy ] || fail 'V1.1 staging web is not healthy'
  [ "$(version gz_v11_release_check)" = 0003_open_lead_portal ] || fail 'Staging database is not at 0003'
  (cd "$package" && sha256sum -c SHA256SUMS.txt)
  docker image inspect gz-api:v1.1-rc1 gz-admin-web:v1.1-rc1 > /dev/null
  python3 scripts/prepare-v11-compose.py
  dc "$candidate" config -q
  curl -fsS --connect-timeout 8 --max-time 15 -o /dev/null http://127.0.0.1:18083/ready
  log 'Internal preflight passed; public HTTP/HTTPS is outside this release'
}

check_internal() {
  cd "$deploy"
  dc "$active" config -q
  [ "$(version gz_platform)" = 0003_open_lead_portal ] || fail 'Production database is not at 0003'
  for name in gz-postgres gz-redis gz-minio gz-api gz-worker gz-admin-web gz-nginx; do
    [ "$(health "$name")" = healthy ] || fail "$name is not healthy"
  done
  for path in /ready / /login /supply /procurement; do
    public_check "Internal $path" "http://127.0.0.1:18083$path"
  done
  log 'Internal V1.1 check passed'
}

rollback_before_traffic() {
  log 'Rolling back the internal release'
  cd "$deploy" || return 1
  dc "$candidate" stop nginx worker api admin-web || true
  if [ "$(version gz_platform 2>/dev/null || true)" != 0001_initial ]; then
    dc "$candidate" run --rm --no-deps api alembic downgrade 0001_initial || return 1
  fi
  [ "$(version gz_platform)" = 0001_initial ] || return 1
  cp -p "$run_dir/docker-compose.production-v1.yml" "$active"
  cp -p "$run_dir/.env" .env
  docker image tag "$(cat "$run_dir/old-api-image-id")" gz-api:latest
  docker image tag "$(cat "$run_dir/old-web-image-id")" gz-admin-web:latest
  dc "$active" config -q
  dc "$active" up -d --no-build --no-deps --force-recreate api worker admin-web nginx
  wait_healthy gz-api gz-worker gz-admin-web gz-nginx
  curl -fsS --max-time 10 -o /dev/null http://127.0.0.1:18083/ready
  if [ -f "$run_dir/old-frpc-restart" ]; then
    docker update --restart="$(cat "$run_dir/old-frpc-restart")" gz-frpc > /dev/null
  fi
  if [ "$(cat "$run_dir/old-frpc-state")" = running ]; then
    dc "$active" up -d --no-build --no-deps frpc
  fi
  printf 'rolled-back\n' > "$run_dir/state"
  log "Rollback complete: $run_dir"
}

on_exit() {
  local rc=$1
  trap - EXIT
  if [ "$rc" -ne 0 ] && [ "$release_active" -eq 1 ]; then
    if [ -e "$run_dir/internal-released" ]; then
      dc "$candidate" stop nginx || true
      printf 'manual-review-required\n' > "$run_dir/state"
      log "Internal release finished. Gateway stopped; review new data in $run_dir before database rollback." >&2
    else
      rollback_before_traffic || log "AUTOMATIC ROLLBACK FAILED. Do not reopen traffic; inspect $run_dir" >&2
    fi
  fi
  exit "$rc"
}

apply() {
  lock_release
  preflight
  cd "$deploy"
  run_dir="$data/backups/v11-release-$(date +%Y%m%d-%H%M%S)"
  mkdir -m 700 "$run_dir"
  cp -p "$active" "$run_dir/docker-compose.production-v1.yml"
  cp -p .env "$run_dir/.env"
  docker inspect -f '{{.Name}} {{.Id}} {{.Image}} {{index .Config.Labels "com.docker.compose.project"}}' gz-api gz-worker gz-admin-web gz-nginx > "$run_dir/old-containers.txt"
  docker inspect -f '{{.Image}}' gz-api > "$run_dir/old-api-image-id"
  docker inspect -f '{{.Image}}' gz-admin-web > "$run_dir/old-web-image-id"
  docker inspect -f '{{.State.Status}}' gz-frpc > "$run_dir/old-frpc-state"
  docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' gz-frpc > "$run_dir/old-frpc-restart"
  version gz_platform > "$run_dir/old-alembic-version.txt"
  printf 'backing-up\n' > "$run_dir/state"

  # Snapshot-consistent dumps first. After stopping writers, take a final
  # platform dump so the rollback point includes every pre-cutover write.
  for db in gz_platform gz_odoo superset; do dump_db "$db" "$run_dir/$db.dump"; done
  stamp=${run_dir##*/v11-release-}
  docker image tag "$(cat "$run_dir/old-api-image-id")" "gz-api:pre-v11-$stamp"
  docker image tag "$(cat "$run_dir/old-web-image-id")" "gz-admin-web:pre-v11-$stamp"
  printf 'gz-api:pre-v11-%s\ngz-admin-web:pre-v11-%s\n' "$stamp" "$stamp" > "$run_dir/old-image-tags.txt"
  printf 'backup-complete\n' > "$run_dir/state"
  release_active=1
  trap 'on_exit $?' EXIT
  # Pause only guazi FRP so the new local deployment is not exposed through
  # the existing public gateway. Prevent auto-restart after a host reboot.
  dc "$active" stop frpc
  docker update --restart=no gz-frpc > /dev/null
  dc "$active" stop nginx
  dc "$active" stop worker api admin-web
  dump_db gz_platform "$run_dir/gz_platform-final.dump"
  printf 'old-services-stopped\n' > "$run_dir/state"

  # Start the new image only as a one-off migration container. The web API's
  # startup calls create_all, so serving it against schema 0001 is unsafe.
  dc "$candidate" run --rm --no-deps api alembic upgrade head 2>&1 | tee "$run_dir/migration.log"
  [ "$(version gz_platform)" = 0003_open_lead_portal ] || fail 'Migration did not reach 0003'
  printf 'migration-complete\n' > "$run_dir/state"
  dc "$candidate" up -d --no-build --no-deps --force-recreate api worker admin-web
  wait_healthy gz-api gz-worker gz-admin-web
  printf 'new-services-healthy\n' > "$run_dir/state"
  dc "$candidate" up -d --no-build --no-deps --force-recreate nginx
  wait_healthy gz-nginx
  curl -fsS --max-time 15 -o /dev/null http://127.0.0.1:18083/ready
  for path in / /login /supply /procurement; do
    curl -fsS --connect-timeout 8 --max-time 15 -o /dev/null "http://127.0.0.1:18083$path"
  done
  cp -p "$candidate" "$active"
  touch "$run_dir/internal-released"
  printf 'internal-released\n' > "$run_dir/state"
  release_active=0
  log "V1.1 internal release healthy; guazi FRP remains stopped. Rollback checkpoint: $run_dir"
}

rollback_command() {
  lock_release
  run_dir=${1:?Provide the checkpoint path under /data/guazi/backups}
  case "$run_dir" in "$data"/backups/v11-release-*) ;; *) fail 'Invalid checkpoint path';; esac
  [ -f "$run_dir/state" ] && [ -f "$run_dir/gz_platform-final.dump" ] || fail 'Incomplete checkpoint'
  cd "$deploy"
  if [ -e "$run_dir/internal-released" ]; then
    dc "$candidate" stop nginx
    fail 'Internal deployment may have new writes: capture current database and review before any downgrade'
  fi
  rollback_before_traffic
}

case "${1:-}" in
  check) preflight ;;
  check-internal) check_internal ;;
  check-http) public_check 'Public HTTP' http://guazi.btszss.com/ready ;;
  check-https) public_check 'Public HTTPS' https://guazi.btszss.com/ready ;;
  apply) [ "${2:-}" = --execute ] || fail 'Use apply --execute after reviewing preflight'; apply ;;
  rollback) rollback_command "${2:-}" ;;
  *) echo "Usage: $0 check | check-internal | check-http | check-https | apply --execute | rollback /data/guazi/backups/v11-release-TIMESTAMP" >&2; exit 2 ;;
esac
