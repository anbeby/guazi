# 第十师瓜子油料数字化交易平台 —— 部署手册

> **当前状态（2026-10-15）**：V1.1 已在 `192.168.3.5` 的 `127.0.0.1:18083` 运行，瓜子专用 FRP 已恢复；公网域名仍受云入口备案拦截。后续正式升级统一按 [瓜子平台后续升级标准流程](../docs/瓜子平台后续升级标准流程.md) 执行，使用 `scripts/release-guazi.py`。现有服务的 Compose 项目名必须为 `guazi`，不要省略 `-p guazi`，不要占用增值运营平台的 18080。

> 历史 V1.1 演练见 [V1.1 发布准备与回滚手册](../docs/V1.1发布准备与回滚手册.md)。现有业务服务器使用 `docker-compose 1.29.2` 与 `docker-compose.production-v1.yml`，本文件以下内容是原阶段一通用说明；新版本发布以上述标准流程为准。

> 适用范围：阶段一（单机 Docker Compose 部署）
> 对应架构：[docs/01-总体技术架构.md](../docs/01-总体技术架构.md) 第 5 节部署拓扑

本目录（`deploy/`）包含全栈编排、中间件配置与运维脚本。
**业务源码（`../odoo`、`../services/api`、`../apps/admin-web`）由各自负责人维护**，
本目录只负责"如何把它们编排起来跑"，并提供配置与运维脚本。

---

## 一、目录结构

```
deploy/
├── docker-compose.yml          全栈编排（12 个服务 + 3 个一次性任务）
├── .env.example                环境变量模板（含中文注释与安全默认值）
├── .env                        实际环境变量（由 start 脚本生成，已被 .gitignore 忽略）
├── .gitignore                  忽略 .env 与 backups/
├── README.md                   本文件
├── conf/
│   ├── postgres/init/
│   │   ├── 01-init.sql         建 gz_odoo / gz_platform / superset 三库 + gz schema + 扩展
│   │   └── 02-readonly.sql     建 Superset 报表只读账号 gz_ro
│   ├── redis/redis.conf        AOF/RDB 持久化、内存策略、慢查询、命令禁用
│   ├── minio/README.md         Bucket 规划（gz-product / gz-report / gz-contract / gz-trace）
│   ├── odoo/
│   │   ├── odoo.conf           Odoo 17 服务端配置
│   │   └── README.md           Odoo 初始化与模块安装（gz_* 模块）
│   ├── nginx/nginx.conf        统一入口网关（/、/api、/odoo、/superset、/websocket）
│   └── superset/superset_config.py  Superset 4.0.2 配置（元数据库、中文、连接池）
├── scripts/
│   ├── start.{sh,ps1}          一键启动（含 .env 检查、健康等待、访问入口打印）
│   ├── stop.{sh,ps1}           停止（保留数据卷）
│   ├── reset.{sh,ps1}          【危险】清空数据卷并重建（二次确认）
│   ├── init-data.{sh,ps1}      平台种子数据 + Odoo 模块安装
│   ├── backup.{sh,ps1}         pg_dump 备份 gz_odoo / gz_platform，保留最近 7 份
│   └── logs.{sh,ps1}           跟随查看指定服务日志
├── backups/                    备份输出目录（自动创建，已忽略）
└── data/                       运行期数据（nginx 日志、API 本地降级文件存储）
```

---

## 二、前置条件

| 项目 | 最低要求 | 建议 |
| --- | --- | --- |
| Docker Engine | 24.0+ | 26.x |
| Docker Compose | v2.20+（`docker compose` 子命令） | v2.27+ |
| CPU | 4 核 | **8 核** |
| 内存 | 16 GB（需下调 ES 堆与 Redis 上限） | **32 GB** |
| 磁盘 | 100 GB | **500 GB SSD/NVMe** |
| 操作系统 | Linux（生产）/ Windows 10+、macOS（开发） | Ubuntu 22.04 LTS |
| 其他 | 端口 8080 / 8069 / 9000 / 9001 / 8088 可用 | 生产仅暴露 8080（或 443） |

**端口占用检查**：

```bash
# Linux/macOS
ss -lntp | grep -E ':(8080|8069|8088|9000|9001)\b'
# Windows PowerShell
Get-NetTCPConnection -State Listen | Where-Object LocalPort -in 8080,8069,8088,9000,9001
```

**Docker 安装（Ubuntu 22.04）**：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 重新登录后生效
docker compose version
```

> Docker Desktop（Windows/macOS）需在设置中给足内存（建议 ≥ 12 GB），
> 并把 `deploy/` 加入文件共享白名单（若使用 WSL2 后端则无需）。

---

## 三、首次部署（5 步）

```bash
# 1) 生成环境变量
cd deploy
cp .env.example .env            # Windows: copy .env.example .env

# 2) 【必做】修改 .env 中所有标注"请务必修改"的密码与密钥
#    - POSTGRES_PASSWORD / POSTGRES_READONLY_PASSWORD
#    - REDIS_PASSWORD / MINIO_ROOT_PASSWORD
#    - ODOO_ADMIN_PASSWD
#    - API_SECRET_KEY / JWT_SECRET / INTEGRATION_SECRET
#    - SUPERSET_SECRET_KEY / SUPERSET_ADMIN_PASSWORD
#    生成随机串：python -c "import secrets;print(secrets.token_urlsafe(48))"
#    改完密码后请同步改下面三行"字面值"连接串：
#      DATABASE_URL、REDIS_URL、SUPERSET_*_URI
vi .env

# 3) 一键启动（等价于 docker compose up -d --build，并会等待健康）
./scripts/start.sh              # Windows: .\scripts\start.ps1
#  脚本会：检查 .env → docker compose config -q 校验 → 构建启动 → 等待 healthy → 打印入口

# 4) 初始化业务数据（角色、权限、管理员、园区、商品、库存、示例交易 + Odoo 模块）
./scripts/init-data.sh          # Windows: .\scripts\init-data.ps1

# 5) 验证
curl -s http://localhost:8080/health
docker compose ps
```

### 服务与启动顺序

| 顺序 | 服务 | 说明 | 首次启动耗时 |
| --- | --- | --- | --- |
| 1 | `postgres` | 三库初始化（执行 `conf/postgres/init/*.sql`） | 20~60s |
| 1 | `redis` | 加载配置、开启 AOF | 5~15s |
| 1 | `minio` | 对象存储 | 10~30s |
| 1 | `elasticsearch` | 需等 JVM 堆分配完毕 | **60~120s** |
| 2 | `minio-init` | 一次性：建 4 个 bucket 与策略 | 5~20s |
| 3 | `odoo` | 依赖 postgres（healthy） | **60~180s**（首次建表更久） |
| 3 | `api` | 依赖 postgres + redis（healthy） | 20~60s |
| 3 | `admin-web` | 静态资源托管 | 10~30s |
| 3 | `superset-init` | 一次性：`db upgrade` + 建管理员 + `init` | 60~180s |
| 4 | `worker` | 后台任务（索引/同步/结算跑批） | 10~30s |
| 5 | `superset` | 依赖 `superset-init` 成功完成 | 30~90s |
| 6 | `nginx` | 网关（依赖均为 `service_started`，不阻塞） | 5s |

> **注意**：`nginx` 的依赖刻意使用 `condition: service_started`（而非 `service_healthy`），
> 这样后端启动慢时不会让 `docker compose up` 整体卡住或失败。
> 代价是网关可能先于后端就绪几秒，此时访问会短暂 502，属正常现象。

---

## 四、访问地址表

| 入口 | 地址 | 说明 |
| --- | --- | --- |
| 统一网关 | http://localhost:8080 | 唯一对外入口（`GATEWAY_PORT` 可改） |
| PC 管理后台 | http://localhost:8080/ | Vue3 前端（构建产物由容器内 nginx 托管） |
| 平台 API 文档 | http://localhost:8080/api/docs | OpenAPI 交互式文档 |
| API 健康检查 | http://localhost:8080/health | 网关透传至 api |
| Odoo ERP | http://localhost:8080/odoo | 首次登录 admin / admin，须立即改密 |
| Superset BI | http://localhost:8080/superset （直连 :8088） | 账号见 `SUPERSET_ADMIN_*` |
| MinIO 控制台 | http://localhost:9001 | 账号见 `MINIO_ROOT_USER` |
| MinIO S3 API | http://localhost:9000 | API 预签名 URL 使用 |
| ElasticSearch | http://localhost:9200（默认不映射） | 需在 compose 中放开 `ports` |
| Odoo 直连 | http://localhost:8069 | 调试用 |
| Superset 直连 | http://localhost:8088 | 调试用 |

**生产环境务必**：只暴露 8080（或前置 SLB 做 TLS 卸载后暴露 443），
把 8069 / 8000 / 8088 / 9000 / 9001 / 5432 / 6379 / 9200 全部收回内网。

### 默认账号速查

| 系统 | 账号 | 密码来源 |
| --- | --- | --- |
| 平台 API / 管理后台 | 由 `app.initial_data` 种子决定（见 `../services/api` 与接口文档） | — |
| Odoo | `admin`（`ODOO_ADMIN_USER`） | 首次以 `admin/admin` 登录后修改；数据库管理密码为 `ODOO_ADMIN_PASSWD` |
| Superset | `SUPERSET_ADMIN_USERNAME`（默认 `admin`） | `SUPERSET_ADMIN_PASSWORD` |
| MinIO | `MINIO_ROOT_USER` | `MINIO_ROOT_PASSWORD` |
| PostgreSQL | `POSTGRES_USER`（超级用户） | `POSTGRES_PASSWORD` |
| PostgreSQL（只读报表） | `POSTGRES_READONLY_USER`（默认 `gz_ro`） | `POSTGRES_READONLY_PASSWORD` |
| Redis | — | `REDIS_PASSWORD` |

---

## 五、数据库与 Superset 使用说明

### 5.1 三库一实例

| 库 | 属主 | 内容 |
| --- | --- | --- |
| `gz_odoo` | `gz` | Odoo 全部表（public schema），需安装 `gz_*` 模块后才完整 |
| `gz_platform` | `gz` | 自研平台业务表，全部位于 **schema `gz`** |
| `superset` | `gz` | Superset 元数据（`ab_user` 等） |

```bash
# 进入 psql
docker compose exec postgres psql -U gz -d gz_platform
# 常用检查
\dn                        -- schema 列表（应有 gz 与 public）
\dt gz.*                   -- 自研业务表
SELECT extname FROM pg_extension;   -- 应有 pg_trgm / uuid-ossp
```

### 5.2 Superset 接入数据源

1. 浏览器打开 `http://<host>:8080/superset`，用 `SUPERSET_ADMIN_*` 登录。
2. 设置 → 数据库连接 → 添加数据库：
   - 显示名：`瓜子平台库(只读)`
   - SQLAlchemy URI：`postgresql://gz_ro:gz_ro_change_me@postgres:5432/gz_platform`
     （把密码换成 `.env` 的 `POSTGRES_READONLY_PASSWORD`）
   - 勾选 **Allow this database to be queried in SQL Lab**（建议仅管理员）
3. 再添加：`瓜子Odoo库(只读)` → `...@postgres:5432/gz_odoo`。
4. 只读账号默认 `search_path = gz,public`，查询 `gz_platform` 可直接写表名；
   查询 `gz_odoo` 时请写 `public.` 前缀。

> 只读账号的创建与授权见 `conf/postgres/init/02-readonly.sql`。
> 该文件中的账号密码是**硬编码**的（initdb 阶段读不到容器环境变量），
> 默认与 `.env.example` 一致（`gz_ro` / `gz_ro_change_me`）。若你改了 `.env`，
> 请按该文件顶部注释同步（方式 A：`ALTER ROLE`；方式 B：全新环境改 SQL 后重建）。
>
> 单机部署未启用 Superset 的 Celery（`superset-worker` / `superset-beat`），
> 因此**定时报表与告警邮件不会自动发送**；如需要，另加两个服务（同镜像，command 不同）。

---

## 六、常见故障排查

### 6.1 端口被占用

```
Error response from daemon: Ports are not available: exposing port TCP 0.0.0.0:8080 -> bind: address already in use
```

```bash
# 找出占用者
ss -lntp | grep :8080                     # Linux
netstat -ano | findstr :8080              # Windows（再用任务管理器按 PID 定位）
# 两种解决：停掉占用进程，或改 .env 中的 GATEWAY_PORT 后重启 nginx
docker compose up -d nginx
```

### 6.2 ElasticSearch 内存不足 / 起不来

现象：容器反复重启，日志出现 `max virtual memory areas vm.max_map_count [65530] is too low`
或 `OutOfMemoryError`。

```bash
# 1) 宿主机内核参数（Linux）
sudo sysctl -w vm.max_map_count=262144
echo 'vm.max_map_count=262144' | sudo tee -a /etc/sysctl.conf

# 2) 减少堆内存（.env）—— 开发机建议 512m
ES_JAVA_OPTS=-Xms512m -Xmx512m
docker compose up -d elasticsearch

# 3) WSL2 用户还需在 %UserProfile%\.wslconfig 加：
#    [wsl2]
#    memory=12GB
```

> ES 不可用时平台会自动降级为 SQL LIKE 检索（见架构 ADR-06），
> 因此**交易主链路不会中断**，可先继续其他部署步骤再回头修 ES。

### 6.3 Odoo 无法连接数据库

```bash
docker compose logs --tail=200 odoo | grep -i -E 'database|connection|fatal'
docker compose logs --tail=100 postgres
```

| 日志 | 原因 | 处理 |
| --- | --- | --- |
| `FATAL: password authentication failed for user "gz"` | `.env` 改了 `POSTGRES_PASSWORD`，但卷里还是旧密码 | 数据卷是用旧密码初始化的：要么把密码改回去，要么 `reset.sh` 重建（数据会丢，先备份） |
| `could not connect to server: Connection refused` | postgres 未就绪或初始化失败 | `docker compose logs postgres` 看 `initdb` 是否报错；确认卷权限 |
| `database "gz_odoo" does not exist` | 初始化脚本未执行（卷非空时不会重跑） | `docker compose exec postgres createdb -U gz gz_odoo`，再执行 `init-data` |
| `relation "ir_module_module" does not exist` | Odoo 库未初始化 | 按 `conf/odoo/README.md` 执行 `-i base` 安装 |
| 改了 `conf/odoo/odoo.conf` 但重启后不生效 | 官方 entrypoint 每次启动都会重写 `odoo.conf`，并以命令行参数传入配置 | 改 `deploy/.env` 与 compose 的 odoo `environment`（唯一生效入口），详见 `conf/odoo/README.md` 顶部说明 |
| Odoo 启动即报错 `sed: can't read /etc/odoo/odoo.conf` / `Read-only file system` | 把 `odoo.conf` 挂载成了 `:ro`，entrypoint 的 `sed -i` 无法写入 | 去掉该挂载的 `:ro`（compose 默认已去掉） |

### 6.4 MinIO bucket 未创建

```bash
docker compose logs minio-init
docker compose run --rm minio-init          # 手动重跑（幂等）
# 确认桶存在
docker compose run --rm minio-init mc ls local
```

若报 `mc: Unable to connect`，检查 `minio` 是否 healthy（`docker compose ps minio`）。

### 6.5 权限报错（Permission denied）

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `initdb: could not change permissions of directory` | 宿主目录属主不是 postgres（uid 999） | 使用具名卷时不会出现；若改为 bind mount，需 `chown 999:999` |
| Odoo 启动报 `Permission denied: '/var/lib/odoo'` | filestore 卷属主不对 | `docker compose exec -u root odoo chown -R odoo:odoo /var/lib/odoo` |
| nginx 报 `Permission denied /var/log/nginx/access.log` | `./data/nginx-logs` 在 Linux 下权限不足 | `sudo chown -R 101:101 data/nginx-logs`（nginx 镜像 uid=101） |
| Superset 报 `PermissionError: '/app/superset_home'` | 卷属主不对（镜像内用户 uid=1000） | `docker compose exec -u root superset chown -R 1000:1000 /app/superset_home` |
| API 报 `permission denied for schema gz` | 迁移未建 schema 或连接串 search_path 不对 | 确认 `DATABASE_URL` 带 `options=-csearch_path%3Dgz,public`，或 `01-init.sql` 已执行 |

### 6.6 网关 502 / 504

| 现象 | 排查 |
| --- | --- |
| `/` 502 | `docker compose logs admin-web`；确认镜像构建成功且容器在 80 端口监听 |
| `/api` 502 | `docker compose ps api` 是否 healthy；`docker compose logs api` |
| `/odoo` 502 | Odoo 启动慢，等 1~2 分钟；仍不行看 `logs odoo` |
| `/superset` 502 | `superset-init` 是否成功完成（`docker compose ps superset-init` 应为 `Exited(0)`） |
| 504 超时 | 大屏/报表查询慢：已设 `proxy_read_timeout 300s`（Odoo/Superset 为 600s）；必要时优化 SQL |

### 6.7 磁盘写满

```bash
docker system df                       # 查看镜像/容器/卷占用
docker compose logs --tail=50 nginx    # 日志已限制 10MB×3，一般不是日志问题
# 常见元凶：ES 索引、MinIO 检测报告/溯源影像、PostgreSQL WAL
du -sh /var/lib/docker/volumes/gz_*
```

处理：按 `conf/minio/README.md` 的生命周期归档对象；清理无用镜像 `docker image prune -a`；
必要时扩容数据盘（不要把 `/var/lib/docker` 放在系统盘）。

---

## 七、数据备份与恢复

### 7.1 备份

```bash
./scripts/backup.sh                      # 备份 gz_odoo + gz_platform，保留最近 7 份
./scripts/backup.sh --keep 14            # 保留 14 份
./scripts/backup.sh --with-odoo-data     # 额外打包 Odoo filestore（附件实体）
./scripts/backup.sh --with-minio         # 额外镜像 MinIO 对象
```

产物：`deploy/backups/{gz_odoo,gz_platform}_YYYYmmdd_HHMMSS.dump`（`pg_dump -Fc` 自定义格式）。

**必须一起备份的三样东西**（缺一不可）：

| 内容 | 命令 |
| --- | --- |
| 数据库 | `./scripts/backup.sh`（或直接 `docker compose exec -T postgres pg_dump`） |
| Odoo filestore（附件实体） | 卷 `gz_odoo_data` —— `--with-odoo-data` |
| MinIO 对象（图片/报告/合同/溯源） | 卷 `gz_minio_data` 或 `mc mirror` —— `--with-minio` |

定时备份（Linux cron，每日 02:00）：

```cron
0 2 * * * cd /opt/瓜子/deploy && ./scripts/backup.sh --with-odoo-data >> /var/log/gz-backup.log 2>&1
```

并**定期把 `deploy/backups/` 同步到异地**（rsync / 对象存储 / NAS）——
本机备份不能防磁盘损坏。

### 7.2 恢复

```bash
# 1) 停止写入方
docker compose stop api worker odoo superset

# 2) 还原数据库（--clean 会先删除同名对象）
docker compose exec -T postgres pg_restore -U gz -d gz_platform --clean --if-exists --no-owner \
  < backups/gz_platform_20240612_183000.dump
docker compose exec -T postgres pg_restore -U gz -d gz_odoo --clean --if-exists --no-owner \
  < backups/gz_odoo_20240612_183000.dump

# 3) 恢复 filestore
docker run --rm -v gz_odoo_data:/data -v "$PWD/backups:/backup" alpine:3.20 \
  tar -xzf /backup/gz_odoo_data_20240612_183000.tar.gz -C /data

# 4) 重新授权（pg_restore --no-owner 后需补只读账号权限）
docker compose exec -T postgres psql -U gz -d gz_platform -c "GRANT SELECT ON ALL TABLES IN SCHEMA gz TO gz_ro;"
docker compose exec -T postgres psql -U gz -d gz_odoo     -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO gz_ro;"

# 5) 重启并验证
docker compose up -d
curl -s http://localhost:8080/health
```

> **演练要求**：至少每季度在测试环境完整演练一次恢复流程。
> 未演练过的备份等于没有备份。

---

## 八、升级流程

### 8.1 升级业务代码（API / 前端 / Odoo 模块）

```bash
# 1) 先备份（务必）
./scripts/backup.sh --with-odoo-data

# 2) 拉取新代码（git pull 等），然后重建镜像
docker compose build api admin-web odoo
docker compose up -d api worker admin-web odoo

# 3) 数据库迁移（若 services/api 使用 Alembic；init-data 脚本已含此步）
docker compose exec -T api alembic upgrade head

# 4) Odoo 模块升级
docker compose exec odoo odoo -d gz_odoo -u gz_platform_base,gz_merchant,gz_product,gz_inventory,gz_trade --stop-after-init
docker compose restart odoo

# 5) 自检
curl -s http://localhost:8080/health
./scripts/logs.sh api
```

### 8.2 升级中间件版本

1. 修改 `docker-compose.yml` 中的镜像 tag（例如 `postgres:16-alpine` → 明确小版本）。
2. **PostgreSQL 大版本升级不能只换 tag**：需 `pg_dumpall` → 新卷 → 还原（或用 `pg_upgrade`）。
3. ElasticSearch 升级前确认索引兼容性；索引可重建（数据源在 PostgreSQL），
   必要时删除 `es_data` 卷后由 worker 重新索引。
4. Redis 升级通常向后兼容 AOF；跨大版本先备份 `redis_data`。

### 8.3 回滚

```bash
# 代码回滚
git checkout <上一个可用 tag>
docker compose build api admin-web odoo
docker compose up -d api worker admin-web odoo

# 数据库回滚（只能靠备份）
# 注意：Alembic 的 downgrade 仅在迁移脚本支持时可用
docker compose exec -T api alembic downgrade -1
# 或按第七章用备份还原
```

> 建议：每次升级前打 tag（`git tag -a v1.1.0`），并记录当时的
> `docker compose images` 输出（镜像 digest），便于精确回滚。

---

## 九、资源占用说明

| 服务 | 空闲内存 | 峰值内存 | CPU | 磁盘（增长点） |
| --- | --- | --- | --- | --- |
| `postgres` | ~120 MB | ~1.5 GB | 中 | 数据 + WAL，随交易量线性增长 |
| `redis` | ~10 MB | ≤ 2 GB（`maxmemory`） | 低 | AOF/RDB，≤ 数 GB |
| `minio` | ~100 MB | ~500 MB | 低 | **增长最快**：图片/报告/影像 |
| `elasticsearch` | ~1.5 GB | ~3 GB（1 GB 堆） | 中高 | 索引，可重建 |
| `odoo` | ~400 MB | ~1.5 GB | 中 | filestore（附件实体）在 `odoo_data` |
| `api` | ~200 MB | ~1.2 GB（4 workers） | 中高 | 日志 + 本地降级文件 |
| `worker` | ~150 MB | ~600 MB | 低 | 日志 |
| `admin-web` | ~10 MB | ~30 MB | 极低 | 无 |
| `superset` | ~400 MB | ~1.5 GB | 中 | 上传文件与缓存 |
| `nginx` | ~10 MB | ~50 MB | 低 | `data/nginx-logs`（按天轮转需自行配置 logrotate） |
| **合计** | **约 3 GB** | **约 13 GB** | — | 建议 8C32G 起步 |

**调优开关（写进 `.env` 即可）**：

| 变量 | 生产建议 | 开发机建议 |
| --- | --- | --- |
| `ES_JAVA_OPTS` | `-Xms1g -Xmx1g`（架构建议 ES 独立 4GB 堆，单机可到 2g） | `-Xms512m -Xmx512m` |
| `ODOO_WORKERS` | `4`（8 核） | `1` 或 `0`（单进程便于调试） |
| `api` 的 `--workers` | `4`（改 `docker-compose.yml` 的 command） | `1` |
| Redis `maxmemory` | `2gb`（改 `conf/redis/redis.conf`） | `512mb` |
| Superset `--workers` | `2` | `1` |

> 扩容路径（架构 ADR-09 已按"可拆 K8s"设计）：
> 1. 把 ES / MinIO 拆到独立主机；
> 2. PostgreSQL 加流复制从库 + 备份机；
> 3. API 多副本 + 前置 Nginx；
> 4. 迁移到 K8s（compose 中无宿主路径绑定、配置全部外置，迁移成本低）。

---

## 十、无 Docker 的本地开发启动说明

适合只想改后端代码、快速迭代的场景。**不推荐**用于联调前端与 Odoo。

### 10.1 本机安装 PostgreSQL 16 与 Redis 7

```bash
# --- Windows（推荐用官方安装包或 winget） ---
winget install PostgreSQL.PostgreSQL.16
winget install Memurai.MemuraiDeveloper      # 或 Redis-x64 便携版
# 或用 Chocolatey：
choco install postgresql16 redis-64 -y

# --- macOS ---
brew install postgresql@16 redis
brew services start postgresql@16
brew services start redis

# --- Ubuntu ---
sudo apt install -y postgresql-16 redis-server
sudo systemctl enable --now postgresql redis-server
```

创建数据库与账号（与 `deploy/.env.example` 保持一致，便于连接串直接复用）：

```sql
-- psql -U postgres
CREATE ROLE gz WITH LOGIN PASSWORD 'gz_pg_change_me_2024' SUPERUSER;
CREATE DATABASE gz_platform OWNER gz ENCODING 'UTF8';
CREATE DATABASE gz_odoo     OWNER gz ENCODING 'UTF8';
\connect gz_platform
CREATE SCHEMA IF NOT EXISTS gz;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- 直接复用仓库脚本亦可：
--   psql -U gz -d gz_platform -f deploy/conf/postgres/init/01-init.sql
```

Redis 设置密码（可选）：编辑 `redis.conf` 加 `requirepass gz_redis_change_me_2024` 后重启。

### 10.2 启动自研 API（uvicorn）

```bash
cd services/api

# 1) 虚拟环境
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 2) 依赖（开发依赖含 pytest / ruff）
pip install -U pip
pip install -r requirements-dev.txt

# 3) 配置环境变量（本地指向本机服务，不要用容器服务名）
# Windows PowerShell
$env:DATABASE_URL="postgresql://gz:gz_pg_change_me_2024@127.0.0.1:5432/gz_platform?options=-csearch_path%3Dgz,public"
$env:REDIS_URL="redis://:gz_redis_change_me_2024@127.0.0.1:6379/0"
$env:JWT_SECRET="dev_jwt_secret"
$env:API_SECRET_KEY="dev_api_secret"
$env:INTEGRATION_SECRET="dev_integration_secret"
# Linux/macOS
export DATABASE_URL="postgresql://gz:gz_pg_change_me_2024@127.0.0.1:5432/gz_platform?options=-csearch_path%3Dgz,public"
export REDIS_URL="redis://:gz_redis_change_me_2024@127.0.0.1:6379/0"

# 4) 建表与种子数据
alembic upgrade head                 # 若项目使用 Alembic
python -m app.initial_data

# 5) 启动服务（热重载）
uvicorn app.main:app --reload --port 8000
#   API 文档：http://127.0.0.1:8000/docs
#   健康检查：http://127.0.0.1:8000/health

# 6) 后台任务（另开一个终端）
python -m app.worker

# 7) 测试
pytest -q
```

### 10.3 启动前端（Vite 开发服务器）

```bash
cd apps/admin-web
npm install          # 或 pnpm install
npm run dev
# Vite 默认 http://localhost:5173；在 .env.development 中把接口地址指向
#   VITE_API_BASE_URL=http://127.0.0.1:8000
# 这样可绕过网关直连本机 API（注意本地 API 没有 /api 前缀时需相应调整）
```

### 10.4 本地开发注意事项

| 事项 | 说明 |
| --- | --- |
| schema 必须存在 | 本地库若没执行 `01-init.sql`，迁移会在 `gz` schema 上失败；先 `CREATE SCHEMA gz` |
| search_path | 连接串必须带 `options=-csearch_path%3Dgz,public`，否则表建到 `public` |
| Redis 不可用 | 按架构 ADR-06，缓存/黑名单会降级；但登录黑名单功能会失效，仅用于本地调试 |
| ES / MinIO 不可用 | 同样自动降级（SQL LIKE / 本地磁盘），无需在本地启动它们 |
| Odoo 联调 | 本地开发若要联调 Odoo JSON-RPC，仍需 `docker compose up -d postgres odoo`，并把 `ODOO_URL` 指向 `http://127.0.0.1:8069` |
| 端口冲突 | 本机 8000 若被占用，改用 `--port 8001` 并同步前端配置 |
| 环境隔离 | 本地 `.env`（`services/api/.env`）不要提交；生产配置一律放 `deploy/.env` |

---

## 十一、运维速查

```bash
# 状态与健康
docker compose ps
docker compose ps --format 'table {{.Service}}\t{{.Status}}'

# 日志
./scripts/logs.sh                # 全部
./scripts/logs.sh api worker     # 指定服务
docker compose logs --tail=200 --since=30m odoo

# 重启单个服务（不重建镜像）
docker compose restart api

# 重新构建并滚动更新（api 可先扩容再缩容以零停机）
docker compose up -d --build --no-deps api
docker compose up -d --scale api=2 && docker compose up -d --scale api=1

# 进入容器
docker compose exec api bash
docker compose exec postgres psql -U gz -d gz_platform
docker compose exec redis redis-cli -a "$REDIS_PASSWORD"
docker compose exec odoo odoo shell -d gz_odoo

# 停止 / 清空
./scripts/stop.sh                # 停止，保留数据
./scripts/reset.sh               # 【危险】清空数据卷并重建
```
