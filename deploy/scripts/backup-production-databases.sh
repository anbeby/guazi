#!/usr/bin/env bash
set -euo pipefail

# Read-only PostgreSQL dumps. Store all backup files on the /data disk.
umask 077
backup_dir=/data/guazi/backups
stamp=$(date +%Y%m%d-%H%M%S)
mkdir -p "$backup_dir"

for db in gz_platform gz_odoo superset; do
  target="$backup_dir/${db}-${stamp}.dump"
  tmp="${target}.part"
  docker exec gz-postgres pg_dump -U gz -Fc "$db" > "$tmp"
  docker exec -i gz-postgres pg_restore -l < "$tmp" > /dev/null
  mv "$tmp" "$target"
  sha256sum "$target"
done
