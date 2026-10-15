#!/usr/bin/env bash
# ==============================================================================
# init-data.sh —— 初始化业务数据（可重复执行，幂等）
# ------------------------------------------------------------------------------
# 做两件事：
#   1) 自研平台种子数据：docker compose exec api python -m app.initial_data
#      （角色、权限、平台管理员、园区、商品分类、示例商品与库存、示例交易）
#   2) Odoo 模块安装：
#      docker compose exec odoo odoo -d gz_odoo \
#        -i gz_platform_base,gz_merchant,gz_product,gz_inventory,gz_trade --stop-after-init
# ------------------------------------------------------------------------------
# 用法：
#   ./scripts/init-data.sh              # 两件事都做
#   ./scripts/init-data.sh --api-only   # 只初始化平台种子数据
#   ./scripts/init-data.sh --odoo-only  # 只安装 Odoo 模块
#   ./scripts/init-data.sh --upgrade    # Odoo 改为 -u（升级已有模块）而不是 -i
#
# 安全说明：数据库密码不通过命令行传递（避免出现在宿主 ps 与 shell history 中），
#           而是用 compose 已注入容器的 POSTGRES_* 环境变量，由 Odoo 自行读取。
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$DEPLOY_DIR"

DO_API=1
DO_ODOO=1
ODOO_ACTION="-i"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-only)  DO_ODOO=0 ;;
    --odoo-only) DO_API=0 ;;
    --upgrade)   ODOO_ACTION="-u" ;;
    -h|--help)   grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数：$1" >&2; exit 2 ;;
  esac
  shift
done

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  DC=(docker-compose)
else
  echo "错误：未找到 docker compose（Compose v2）。" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "错误：未找到 .env，请先执行 ./scripts/start.sh 生成。" >&2
  exit 1
fi

env_get() {
  local key="$1" default="$2" line
  line="$(grep -E "^[[:space:]]*${key}=" .env 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$line" ]]; then printf '%s' "$default"; else printf '%s' "${line#*=}" | tr -d '"'"'"'\r'; fi
}
ODOO_DB="$(env_get ODOO_DB gz_odoo)"
PLATFORM_DB="$(env_get PLATFORM_DB gz_platform)"
POSTGRES_USER="$(env_get POSTGRES_USER gz)"

ensure_running() {
  local svc="$1" state
  state="$("${DC[@]}" ps --format '{{.Service}}|{{.State}}' 2>/dev/null | awk -F'|' -v s="$svc" '$1==s{print $2}')"
  if [[ "$state" != "running" ]]; then
    echo "错误：服务 $svc 未在运行（当前状态：${state:-未创建}）。" >&2
    echo "      请先执行 ./scripts/start.sh，并用 ./scripts/logs.sh $svc 排查。" >&2
    exit 1
  fi
}

# ------------------------------------------------------------------------------
# 1) 平台种子数据
# ------------------------------------------------------------------------------
if [[ "$DO_API" == "1" ]]; then
  echo "==> [1/2] 初始化自研平台种子数据（库 ${PLATFORM_DB}，schema gz）"
  ensure_running api
  # 若迁移由 Alembic 管理，先升级到最新版本（命令不存在时不阻断，仅提示）
  if "${DC[@]}" exec -T api sh -lc 'command -v alembic >/dev/null 2>&1'; then
    echo "    - 执行数据库迁移：alembic upgrade head"
    "${DC[@]}" exec -T api alembic upgrade head || {
      echo "    警告：alembic upgrade head 失败，请检查 services/api 的迁移脚本与 DATABASE_URL。" >&2
      exit 1
    }
  else
    echo "    - 未检测到 alembic 命令，跳过迁移（由 app.initial_data 自行建表时属正常）"
  fi
  echo "    - 执行种子数据：python -m app.initial_data"
  "${DC[@]}" exec -T api python -m app.initial_data
  echo "    平台种子数据完成。"
  echo "    提示：默认管理员账号见 deploy/README.md；首次登录后请立即改密。"
fi

# ------------------------------------------------------------------------------
# 2) Odoo 模块安装
# ------------------------------------------------------------------------------
if [[ "$DO_ODOO" == "1" ]]; then
  echo "==> [2/2] 安装 / 升级 Odoo 自研模块（库 ${ODOO_DB}）"
  ensure_running odoo
  MODULES="gz_platform_base,gz_merchant,gz_product,gz_inventory,gz_trade"
  echo "    动作：${ODOO_ACTION} ${MODULES}"
  echo "    参数：--stop-after-init --without-demo=all --db_host=postgres --db_port=5432"
  # 通过容器已有的环境变量（compose 注入的 USER/PASSWORD/DB_NAME）提供连接信息，
  # 避免在命令行出现密码。
  "${DC[@]}" exec -T odoo \
    odoo -d "${ODOO_DB}" \
         ${ODOO_ACTION} "${MODULES}" \
         --stop-after-init \
         --without-demo=all \
         --db_host=postgres \
         --db_port=5432 \
         --db_user="${POSTGRES_USER}"
  echo "    Odoo 模块处理完成。"
  echo "    注意：--stop-after-init 会让 odoo 容器进程退出，"
  echo "          restart: unless-stopped 会自动拉起；若未恢复请执行："
  echo "          docker compose restart odoo"
  # 主动确保容器恢复运行，避免后续命令找不到容器
  "${DC[@]}" up -d odoo >/dev/null 2>&1 || true
fi

echo
echo "初始化流程结束。自检命令："
cat <<EOF
  # 平台侧
  docker compose exec postgres psql -U ${POSTGRES_USER} -d ${PLATFORM_DB} -c "\\dt gz.*" | head -20
  # Odoo 侧
  docker compose exec postgres psql -U ${POSTGRES_USER} -d ${ODOO_DB} \\
    -c "SELECT name, state FROM ir_module_module WHERE name LIKE 'gz_%' ORDER BY name;"
  # 登录验证
  curl -s -X POST http://localhost:8080/api/v1/auth/login \\
    -H 'Content-Type: application/json' -d '{"username":"admin","password":"<见文档>"}'
EOF
