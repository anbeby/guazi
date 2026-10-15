#!/usr/bin/env bash
# ==============================================================================
# backup.sh —— 备份 PostgreSQL 业务库（gz_odoo / gz_platform）
# ------------------------------------------------------------------------------
# 输出目录：deploy/backups/
# 文件名：  gz_odoo_20240612_183000.dump / gz_platform_20240612_183000.dump
# 格式：    pg_dump -Fc（自定义格式，压缩、支持并行还原与选择性还原）
# 保留策略：默认每个库保留最近 7 份，更早的自动删除（可用 --keep N 调整）
# ------------------------------------------------------------------------------
# 用法：
#   ./scripts/backup.sh                 # 备份两个库，保留最近 7 份
#   ./scripts/backup.sh --keep 14       # 保留最近 14 份
#   ./scripts/backup.sh --with-minio    # 额外把 MinIO 对象镜像到 backups/minio-<时间戳>/
#   ./scripts/backup.sh --with-odoo-data# 额外打包 odoo filestore 卷
#
# 注意：
#   - 本脚本只备份"数据库"，MinIO 对象与 Odoo filestore 需另外处理（见 README）。
#   - 建议配置 cron 每日执行：0 2 * * * /path/to/deploy/scripts/backup.sh >> /var/log/gz-backup.log 2>&1
# ==============================================================================
set -Eeuo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "$DEPLOY_DIR"

KEEP=7
WITH_MINIO=0
WITH_ODOO_DATA=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --keep) KEEP="${2:-7}"; shift ;;
    --with-minio) WITH_MINIO=1 ;;
    --with-odoo-data) WITH_ODOO_DATA=1 ;;
    -h|--help) grep -E '^#( |$)' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
  echo "错误：未找到 .env。" >&2
  exit 1
fi

env_get() {
  local key="$1" default="$2" line
  line="$(grep -E "^[[:space:]]*${key}=" .env 2>/dev/null | tail -n 1 || true)"
  if [[ -z "$line" ]]; then printf '%s' "$default"; else printf '%s' "${line#*=}" | tr -d '"'"'"'\r'; fi
}
POSTGRES_USER="$(env_get POSTGRES_USER gz)"
ODOO_DB="$(env_get ODOO_DB gz_odoo)"
PLATFORM_DB="$(env_get PLATFORM_DB gz_platform)"
MINIO_BUCKET="$(env_get MINIO_BUCKET gz-product)"

BACKUP_DIR="${DEPLOY_DIR}/backups"
mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d_%H%M%S)"

# 检查 postgres 是否在运行
state="$("${DC[@]}" ps --format '{{.Service}}|{{.State}}' 2>/dev/null | awk -F'|' '$1=="postgres"{print $2}')"
if [[ "$state" != "running" ]]; then
  echo "错误：postgres 服务未运行（当前：${state:-未创建}），无法备份。" >&2
  exit 1
fi

echo "==> 备份目录：$BACKUP_DIR"
echo "==> 时间戳：$STAMP"

dump_one() {
  local db="$1" file="${BACKUP_DIR}/${1}_${STAMP}.dump" tmp="${BACKUP_DIR}/${1}_${STAMP}.dump.part"
  echo "    - 导出 ${db} -> $(basename "$file")"
  # -T 关闭 TTY（脚本环境必需，否则报 "the input device is not a TTY"）
  # 注意：不要用 exec ... > file 直接重定向，-T 下由 stdin/stdout 管道传输更可靠
  if "${DC[@]}" exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc --no-owner --no-privileges "$db" > "$tmp"; then
    mv -f "$tmp" "$file"
    local size
    size="$(du -h "$file" | cut -f1)"
    echo "      完成：$(basename "$file")（$size）"
    # 校验文件可读（pg_restore -l 只读取目录表，不连数据库）
    if ! "${DC[@]}" exec -T postgres pg_restore -l < "$file" >/dev/null 2>&1; then
      echo "      警告：备份文件校验失败，可能不完整，请检查磁盘空间与 postgres 日志。" >&2
    fi
  else
    rm -f "$tmp"
    echo "      错误：${db} 备份失败。" >&2
    return 1
  fi
}

echo "==> 1) 备份数据库"
dump_one "$ODOO_DB"
dump_one "$PLATFORM_DB"

if [[ "$WITH_ODOO_DATA" == "1" ]]; then
  echo "==> 2) 打包 Odoo filestore（附件实体，必须与数据库一起还原）"
  tar_file="${BACKUP_DIR}/gz_odoo_data_${STAMP}.tar.gz"
  # 用临时容器挂载卷打包，避免依赖宿主对 /var/lib/docker 的访问权限
  if docker run --rm -v gz_odoo_data:/data:ro -v "${BACKUP_DIR}":/backup alpine:3.20 \
       tar -czf "/backup/$(basename "$tar_file")" -C /data . ; then
    echo "      完成：$(basename "$tar_file")（$(du -h "$tar_file" | cut -f1)）"
  else
    echo "      警告：filestore 打包失败（可跳过，但恢复时附件会丢失）。" >&2
  fi
fi

if [[ "$WITH_MINIO" == "1" ]]; then
  echo "==> 3) 镜像 MinIO 对象到 backups/minio-${STAMP}/"
  mkdir -p "${BACKUP_DIR}/minio-${STAMP}"
  if "${DC[@]}" exec -T minio-init sh -lc \
       "mc alias set local http://minio:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && mc ls local"; then
    echo "      MinIO 可达。注意：minio-init 容器通常已退出，若报错请改用："
    echo "        docker compose run --rm minio-init mc mirror local/${MINIO_BUCKET} /backup"
  else
    echo "      警告：MinIO 镜像失败。建议改用 mc mirror 或直接备份卷 gz_minio_data。" >&2
  fi
fi

# ------------------------------------------------------------------------------
# 保留策略：按文件名时间戳排序，仅保留最近 $KEEP 份（每个库分别计算）
# ------------------------------------------------------------------------------
echo "==> 4) 清理历史备份（保留最近 ${KEEP} 份/库）"
for db in "$ODOO_DB" "$PLATFORM_DB"; do
  mapfile -t old < <(ls -1t "${BACKUP_DIR}/${db}_"*.dump 2>/dev/null | tail -n "+$((KEEP + 1))" || true)
  if (( ${#old[@]} > 0 )); then
    for f in "${old[@]}"; do
      rm -f "$f"
      echo "    已删除旧备份：$(basename "$f")"
    done
  else
    echo "    ${db}：无需清理"
  fi
done

echo
echo "==> 备份完成，当前 ${BACKUP_DIR} 内容："
ls -lht "$BACKUP_DIR" | head -20
cat <<EOF

还原示例（务必先在测试环境演练）：
  # 1) 停止写入方，避免还原期间有新数据
  docker compose stop api worker odoo

  # 2) 还原 gz_platform（--clean 会先删除同名对象；生产建议先用临时库验证）
  docker compose exec -T postgres pg_restore -U ${POSTGRES_USER} -d ${PLATFORM_DB} --clean --if-exists --no-owner < backups/${PLATFORM_DB}_${STAMP}.dump

  # 3) 还原 gz_odoo
  docker compose exec -T postgres pg_restore -U ${POSTGRES_USER} -d ${ODOO_DB} --clean --if-exists --no-owner < backups/${ODOO_DB}_${STAMP}.dump

  # 4) 恢复 Odoo filestore（若做了 --with-odoo-data）
  docker run --rm -v gz_odoo_data:/data -v "\$PWD/backups":/backup alpine:3.20 \\
    tar -xzf /backup/gz_odoo_data_${STAMP}.tar.gz -C /data

  # 5) 重启并自检
  docker compose up -d && ./scripts/logs.sh api
EOF
