#!/usr/bin/env bash
# ==============================================================================
# logs.sh —— 跟随查看容器日志
# ------------------------------------------------------------------------------
# 用法：
#   ./scripts/logs.sh                 # 跟随全部服务日志
#   ./scripts/logs.sh api             # 只看 api
#   ./scripts/logs.sh api worker      # 看多个服务
#   ./scripts/logs.sh --tail 200 es   # 指定初始行数（默认 100）
#   ./scripts/logs.sh --since 30m odoo
#
# 服务名可选值（与 docker-compose.yml 一致）：
#   postgres redis minio minio-init elasticsearch odoo api worker admin-web
#   superset superset-init nginx
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$DEPLOY_DIR"

TAIL=100
SINCE=""
SERVICES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tail)  TAIL="${2:-100}"; shift ;;
    --since) SINCE="${2:-10m}"; shift ;;
    -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*) echo "未知参数：$1" >&2; exit 2 ;;
    *) SERVICES+=("$1") ;;
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
  echo "错误：未找到 .env。" >&2
  exit 1
fi

ARGS=(-f --tail "$TAIL")
[[ -n "$SINCE" ]] && ARGS+=(--since "$SINCE")

if (( ${#SERVICES[@]} == 0 )); then
  echo "==> 跟随全部服务日志（Ctrl+C 退出）"
  exec "${DC[@]}" logs "${ARGS[@]}"
else
  # 校验服务名，避免 compose 报一堆难懂的错
  valid="$( "${DC[@]}" config --services 2>/dev/null | sort | tr '\n' ' ' )"
  for s in "${SERVICES[@]}"; do
    if ! printf '%s\n' "$valid" | tr ' ' '\n' | grep -qx "$s"; then
      echo "错误：未知服务 '$s'。可用服务：$valid" >&2
      exit 2
    fi
  done
  echo "==> 跟随日志：${SERVICES[*]}（Ctrl+C 退出）"
  exec "${DC[@]}" logs "${ARGS[@]}" "${SERVICES[@]}"
fi
