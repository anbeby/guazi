#!/usr/bin/env bash
# ==============================================================================
# start.sh —— 一键启动全栈（首次运行会自动从模板生成 .env）
# 用法：./scripts/start.sh [--no-build] [--wait-seconds 600]
# ------------------------------------------------------------------------------
# 重要提醒：本脚本不会执行任何危险操作；数据卷不会被删除。
#           清空数据请使用 scripts/reset.sh（有二次确认）。
# ==============================================================================
set -Eeuo pipefail

# 切换到 deploy 目录（本脚本的上一级），保证 compose 能找到 .env 与 conf/
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$DEPLOY_DIR"

BUILD_FLAG="--build"
WAIT_SECONDS=600
ALLOW_DEFAULTS="${ALLOW_DEFAULT_SECRETS:-0}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-build) BUILD_FLAG="" ;;
    --allow-default-secrets) ALLOW_DEFAULTS=1 ;;
    --wait-seconds) WAIT_SECONDS="${2:-600}"; shift ;;
    -h|--help)
      grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数：$1（可用：--no-build --wait-seconds N --allow-default-secrets）" >&2; exit 2 ;;
  esac
  shift
done

echo "==> [1/5] 检查 Docker 环境"
if ! command -v docker >/dev/null 2>&1; then
  echo "错误：未找到 docker 命令。请先安装 Docker 24+ 并启动 Docker Desktop / dockerd。" >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "错误：无法连接 Docker 守护进程（docker info 失败）。请确认 Docker 已启动。" >&2
  exit 1
fi
if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  echo "提示：检测到旧版 docker-compose，建议升级到 Compose v2（docker compose）。"
  DC=(docker-compose)
else
  echo "错误：未找到 docker compose（Compose v2）。请安装 Docker Compose v2 插件。" >&2
  exit 1
fi
echo "    docker: $(docker --version)"

echo "==> [2/5] 检查环境变量文件 .env"
if [[ ! -f .env ]]; then
  if [[ ! -f .env.example ]]; then
    echo "错误：$DEPLOY_DIR 下既没有 .env 也没有 .env.example，无法继续。" >&2
    exit 1
  fi
  cp .env.example .env
  echo "    已从 .env.example 生成 .env（使用默认演示密码）。"
  echo "    ！！请立即编辑 $DEPLOY_DIR/.env，修改所有标注【请务必修改】的密码与密钥。！！"
  echo "    修改完成后重新执行：./scripts/start.sh"
  if [[ "$ALLOW_DEFAULTS" != "1" ]]; then
    echo "    已停止启动，避免把默认密码带到共享环境。"
    echo "    若确认仅在本机演示、可接受默认密码，请加参数：--allow-default-secrets"
    exit 0
  fi
  echo "    已指定 --allow-default-secrets，继续使用默认密码启动（仅限本机演示）。"
fi

# 读取端口等非敏感配置用于打印访问入口。
# 注意：不使用 `. ./.env`（source 会执行文件内容并有注入风险），
#       这里只按 KEY=VALUE 精确提取需要的几个变量。
env_get() {
  local key="$1" default="$2" line
  line="$(grep -E "^[[:space:]]*${key}=" .env 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$line" ]]; then printf '%s' "$default"; else printf '%s' "${line#*=}" | tr -d '"'"'"'\r'; fi
}
GATEWAY_PORT="$(env_get GATEWAY_PORT 8080)"
SUPERSET_PORT="$(env_get SUPERSET_PORT 8088)"
ODOO_PORT="$(env_get ODOO_PORT 8069)"
MINIO_CONSOLE_PORT="$(env_get MINIO_CONSOLE_PORT 9001)"
MINIO_API_PORT="$(env_get MINIO_API_PORT 9000)"

echo "==> [3/5] 校验并构建镜像（首次构建约 3~10 分钟）"
"${DC[@]}" config -q
"${DC[@]}" up -d ${BUILD_FLAG}

echo "==> [4/5] 等待服务健康（最多 ${WAIT_SECONDS}s）"
echo "    说明：minio-init / superset-init 是一次性任务，运行结束显示 Exited(0) 属正常；"
echo "          PostgreSQL / Redis / MinIO / ES / Odoo / API / Superset / Nginx 会显示 healthy。"
deadline=$((SECONDS + WAIT_SECONDS))
while (( SECONDS < deadline )); do
  statuses="$("${DC[@]}" ps --format '{{.Service}}|{{.State}}|{{.Health}}' 2>/dev/null || true)"
  # 汇总两类问题：①声明了 healthcheck 但尚未 healthy ②非 running/exited 状态
  summary="$(printf '%s\n' "$statuses" | awk -F'|' '
    NF>=3 {
      svc=$1; st=$2; hl=$3
      if (st=="running" && hl!="" && hl!="healthy") bad = bad (bad?",":"") svc ":" hl
      else if (st!="running" && st!="exited") bad = bad (bad?",":"") svc ":" st
    }
    END { print bad }')"
  if [[ -z "$summary" ]]; then
    echo "    所有服务已就绪。"
    break
  fi
  printf '\r    等待中... 未就绪: %-60s' "$summary"
  sleep 5
done
echo

echo "==> [5/5] 当前服务状态"
"${DC[@]}" ps

cat <<EOF

================================================================================
  启动完成，访问入口如下（服务器部署请把 localhost 换成实际 IP / 域名）
--------------------------------------------------------------------------------
  统一网关（推荐入口）    http://localhost:${GATEWAY_PORT}
  平台 API 文档           http://localhost:${GATEWAY_PORT}/api/docs
  API 健康检查            http://localhost:${GATEWAY_PORT}/health
  Odoo ERP                http://localhost:${GATEWAY_PORT}/odoo
  Superset BI             http://localhost:${GATEWAY_PORT}/superset   （直连 :${SUPERSET_PORT}）
  MinIO 控制台            http://localhost:${MINIO_CONSOLE_PORT}     （S3 API :${MINIO_API_PORT}）
  Odoo 直连（调试）       http://localhost:${ODOO_PORT}

  首次使用请初始化数据：
      ./scripts/init-data.sh          # 平台种子数据 + Odoo 模块安装
  账号密码见 deploy/.env（ODOO_ADMIN_USER / ODOO_ADMIN_PASSWD / SUPERSET_ADMIN_*）
--------------------------------------------------------------------------------
  查看日志：./scripts/logs.sh [服务名]
  停止服务：./scripts/stop.sh          停止并清空数据：./scripts/reset.sh
  数据备份：./scripts/backup.sh
================================================================================
EOF
