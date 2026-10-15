#!/usr/bin/env bash
# ==============================================================================
# reset.sh —— 【危险】清空全部数据并重建环境
# ------------------------------------------------------------------------------
# 本脚本会执行 docker compose down -v，删除以下具名卷中的全部数据：
#   gz_postgres_data（gz_odoo / gz_platform / superset 三个库）
#   gz_redis_data、gz_minio_data、gz_es_data、gz_odoo_data、gz_superset_data
# 删除后不可恢复！执行前必须先做备份：./scripts/backup.sh
# ------------------------------------------------------------------------------
# 用法：
#   ./scripts/reset.sh                 # 交互式二次确认（输入大写 YES）
#   ./scripts/reset.sh --yes           # 跳过确认（仅供 CI / 自动化，慎用）
#   RESET_CONFIRM=YES ./scripts/reset.sh   # 环境变量方式确认
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$DEPLOY_DIR"

SKIP_CONFIRM=0
[[ "${1:-}" == "--yes" ]] && SKIP_CONFIRM=1

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
else
  echo "错误：未找到 docker compose（Compose v2）。" >&2
  exit 1
fi

echo "############################################################"
echo "#  【危险操作】即将删除全部数据卷，数据不可恢复！          #"
echo "############################################################"
echo "将删除的卷："
for v in gz_postgres_data gz_redis_data gz_minio_data gz_es_data gz_odoo_data gz_superset_data; do
  if docker volume inspect "$v" >/dev/null 2>&1; then
    echo "  - $v （存在，将被删除）"
  else
    echo "  - $v （不存在，跳过）"
  fi
done
echo

if [[ "$SKIP_CONFIRM" != "1" && "${RESET_CONFIRM:-}" != "YES" ]]; then
  read -r -p "确认要删除以上全部数据吗？请输入大写 YES 继续，其他任意输入取消： " reply
  if [[ "$reply" != "YES" ]]; then
    echo "已取消，未做任何修改。"
    exit 0
  fi
  read -r -p "再次确认（最后一次机会）：请输入 DELETE 执行删除： " reply2
  if [[ "$reply2" != "DELETE" ]]; then
    echo "已取消，未做任何修改。"
    exit 0
  fi
fi

echo "==> 1/3 停止并移除容器、网络、数据卷（docker compose down -v）"
"${DC[@]}" down -v --remove-orphans

echo "==> 2/3 清理残留的具名卷（compose 之外可能遗留）"
for v in gz_postgres_data gz_redis_data gz_minio_data gz_es_data gz_odoo_data gz_superset_data; do
  if docker volume inspect "$v" >/dev/null 2>&1; then
    docker volume rm -f "$v" >/dev/null 2>&1 || echo "    警告：卷 $v 删除失败（可能仍被其他容器占用）"
    echo "    已删除 $v"
  fi
done

echo "==> 3/3 重新构建并启动"
"${DC[@]}" up -d --build

echo
echo "重置完成。当前状态："
"${DC[@]}" ps
cat <<'EOF'

后续步骤：
  1) 等待全部服务 healthy：./scripts/logs.sh postgres
  2) 初始化业务数据：./scripts/init-data.sh
  3) 首次登录后立即修改 Odoo 与 Superset 管理员密码
EOF
