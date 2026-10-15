#!/usr/bin/env bash
# ==============================================================================
# 第十师瓜子油料数字化交易平台 · 访问地址自动探测（Linux / macOS / WSL / Git Bash）
#
# 用途：启动容器后自动探测本机局域网 IP，打印 PC / 手机 / 后台 的完整访问地址。
# 用法：bash deploy/scripts/access-info.sh
# ==============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

GATEWAY_PORT=8080
ADMIN_PORT=8081
if [ -f "${ENV_FILE}" ]; then
  gp="$(grep -E '^[[:space:]]*GATEWAY_PORT[[:space:]]*=' "${ENV_FILE}" | tail -1 | cut -d= -f2 | tr -d ' \r')"
  ap="$(grep -E '^[[:space:]]*ADMIN_PORT[[:space:]]*=' "${ENV_FILE}" | tail -1 | cut -d= -f2 | tr -d ' \r')"
  [ -n "${gp:-}" ] && GATEWAY_PORT="${gp}"
  [ -n "${ap:-}" ] && ADMIN_PORT="${ap}"
fi

detect_ip() {
  # 1) 默认路由出口网卡的地址（最可能是局域网可达 IP）
  if command -v ip >/dev/null 2>&1; then
    local dev ip
    dev="$(ip route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
    if [ -n "${dev}" ]; then
      ip="$(ip -4 addr show dev "${dev}" 2>/dev/null | awk '/inet / {print $2; exit}' | cut -d/ -f1)"
      [ -n "${ip}" ] && { echo "${ip}"; return; }
    fi
  fi
  if command -v ipconfig >/dev/null 2>&1; then
    local ip
    ip="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null)"
    [ -n "${ip}" ] && { echo "${ip}"; return; }
  fi
  if command -v hostname >/dev/null 2>&1; then
    local ip
    ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    [ -n "${ip}" ] && { echo "${ip}"; return; }
  fi
  echo "127.0.0.1"
}

IP="$(detect_ip)"

echo ""
echo "================================"
echo " 系统启动成功"
echo "================================"
echo ""
echo " PC 访问（管理后台）：   http://${IP}:${GATEWAY_PORT}/"
echo " 手机访问（H5 移动端）： http://${IP}:${GATEWAY_PORT}/m/"
echo " 后台专用入口：         http://${IP}:${ADMIN_PORT}/"
echo ""
echo " 运维控制台（免构建）：  http://${IP}:${GATEWAY_PORT}/console/"
echo " 接口文档（OpenAPI）：   http://${IP}:${GATEWAY_PORT}/api/docs"
echo " Odoo ERP：             http://${IP}:${GATEWAY_PORT}/odoo"
echo " 数据分析（Superset）：  http://${IP}:${GATEWAY_PORT}/superset"
echo " MinIO 控制台：         http://${IP}:9001"
echo ""
echo " 本机访问可用 http://localhost 替换上述 IP"
echo " 手机请连接与电脑相同的 WiFi"
echo ""
echo " 演示账号：admin / Admin@123（平台管理员）"
echo "           jinsui、testmerchant、gongxiao、testbuyer 密码均为 Gz@123456"
echo ""

if command -v curl >/dev/null 2>&1; then
  if curl -fsS "http://127.0.0.1:${GATEWAY_PORT}/nginx-health" >/dev/null 2>&1; then
    echo " [自检] 网关健康检查通过"
  else
    echo " [自检] 网关暂不可达，可能仍在启动中，请稍等 30 秒后重试"
  fi
fi
echo ""
