#!/usr/bin/env bash
# ==============================================================================
# stop.sh —— 停止全部服务（保留数据卷，数据不丢）
# 用法：./scripts/stop.sh
# 说明：等价于 docker compose stop；若要彻底移除容器但保留卷用
#       docker compose down（不加 -v）。清空数据请用 scripts/reset.sh。
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$DEPLOY_DIR"

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
else
  echo "错误：未找到 docker compose（Compose v2）。" >&2
  exit 1
fi

echo "==> 停止全部服务（数据卷 postgres_data / minio_data / odoo_data 等均保留）"
"${DC[@]}" stop

echo
echo "已停止。当前状态："
"${DC[@]}" ps

cat <<'EOF'

提示：
  - 重新启动：./scripts/start.sh --no-build
  - 彻底移除容器与网络（仍保留数据卷）：docker compose down
  - 清空全部数据（危险）：./scripts/reset.sh
EOF
