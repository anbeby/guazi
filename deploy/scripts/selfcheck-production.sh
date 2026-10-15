#!/usr/bin/env bash
set -euo pipefail

echo "docker=$(systemctl is-active docker) boot=$(systemctl is-enabled docker)"
for name in gz-postgres gz-redis gz-minio gz-elasticsearch gz-odoo gz-api gz-worker gz-admin-web gz-superset gz-nginx; do
  state=$(docker inspect -f '{{.State.Status}}/{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$name")
  echo "$name=$state"
  if [ "$state" != 'running/healthy' ]; then exit 1; fi
done
echo "gz-frpc=$(docker inspect -f '{{.State.Status}}' gz-frpc)"
echo "value-ops=$(docker ps --filter name=tunyun-value-ops --format '{{.Names}}:{{.Status}}' | tr '\n' ' ')"
echo "gateway_health=$(curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1:18083/health)"
echo "gateway_ready=$(curl -fsS -o /dev/null -w '%{http_code}' http://127.0.0.1:18083/ready)"
echo "backup_files=$(find /data/guazi/backups -maxdepth 1 -type f -name '*.dump' | wc -l)"
