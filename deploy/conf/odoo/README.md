# Odoo 17 CE 初始化与模块安装说明

本目录存放 Odoo 的配置文件 `odoo.conf`（挂载到容器 `/etc/odoo/odoo.conf`）。
Odoo 镜像由 `../odoo/Dockerfile` 构建（由 Odoo 业务负责人维护），
本平台编排只做引用，不修改其源码。

> ### ⚠️ 关于 `odoo.conf` 的重要说明（必读）
>
> Odoo 官方镜像的 `/entrypoint.sh` **每次容器启动都会重写**
> `/etc/odoo/odoo.conf`，并把数据库连接、`workers`、`proxy_mode`、
> `limit_*`、`admin_passwd` 等以**命令行参数**形式传给 odoo 进程。
>
> 由此带来三条硬性结论：
>
> 1. **运行期真正生效的配置是 `docker-compose.yml` 中 odoo 服务的 `environment`**，
>    而不是本目录的 `odoo.conf`。要改 Odoo 行为，请改 `deploy/.env`
>    （`ODOO_WORKERS` / `ODOO_MAX_CRON_THREADS` / `ODOO_LIST_DB` / `ODOO_ADMIN_PASSWD` 等）。
> 2. **`odoo.conf` 不能用 `:ro` 挂载**：entrypoint 会执行 `sed -i` 就地修改它，
>    只读挂载会导致启动失败。compose 中该项已刻意不加 `:ro`。
> 3. entrypoint **不支持**通过环境变量注入 `dbfilter`、`smtp_*`、`log_level`、
>    `db_maxconn` 等。这些请改到 Odoo 界面：
>    「设置 → 技术 → 系统参数」（如 `web.base.url`）与
>    「设置 → 技术 → 邮件 → 出站邮件服务器」。
>
> 验证当前实际生效的配置：
>
> ```bash
> docker compose exec odoo cat /etc/odoo/odoo.conf
> docker compose exec odoo ps aux | grep -o -- '--workers=[0-9]*'
> ```

- 容器名：`gz-odoo`
- 访问入口（经网关）：`http://<host>:8080/odoo`
- 直连端口：`http://<host>:8069`（调试用）
- 业务库：`gz_odoo`（与自研库 `gz_platform` 同实例分库，见 `docs/01-总体技术架构.md` ADR-03）

---

## 1. 首次初始化（数据库）

`deploy/conf/postgres/init/01-init.sql` 已在 PostgreSQL 首次启动时创建了空的
`gz_odoo` 库并安装了 `pg_trgm` / `uuid-ossp` / `unaccent` 扩展，
因此 Odoo 只需要**建表并安装模块**，不要再手工 `createdb`。

### 1.1 确认 Odoo 能连上数据库

```bash
cd deploy
docker compose ps odoo postgres
docker compose logs --tail=100 odoo
# 期望日志出现：database connection established / HTTP service (werkzeug) running on 0.0.0.0:8069
```

若报 `FATAL: password authentication failed`，检查 `.env` 的 `POSTGRES_PASSWORD`
与 compose 中 odoo 服务的 `PASSWORD` 是否一致（compose 会用环境变量覆盖 `odoo.conf`）。

### 1.2 创建 Odoo 业务库并安装模块（推荐：一条命令搞定）

自研模块清单见 `docs/02-Odoo承载能力分析与自研模块边界.md`，
阶段一需要安装：`gz_platform_base`、`gz_merchant`、`gz_product`、`gz_inventory`、`gz_trade`。

```bash
# 在 deploy 目录下执行
docker compose exec odoo \
  odoo -d gz_odoo \
       -i gz_platform_base,gz_merchant,gz_product,gz_inventory,gz_trade \
       --stop-after-init \
       --without-demo=all \
       --db_host=postgres --db_port=5432 \
       --db_user=gz --db_password="<.env 中的 POSTGRES_PASSWORD>"
```

说明：

| 参数 | 作用 |
| --- | --- |
| `-d gz_odoo` | 目标数据库；不存在时会自动创建（属主为 `db_user`） |
| `-i a,b,c` | 安装模块列表（逗号分隔，按依赖顺序亦可，Odoo 会自动排序） |
| `--stop-after-init` | 安装完成后退出进程（必加，否则容器会一直挂着） |
| `--without-demo=all` | 不写入演示数据，保持库干净 |
| `--db_*` | 显式指定连接参数，避免读不到环境变量时连错库 |

> 建议直接使用封装脚本，避免手打参数：
> `./scripts/init-data.sh`（Windows：`.\scripts\init-data.ps1`）
> 该脚本会同时执行「API 种子数据」与「Odoo 模块安装」两件事。

### 1.3 初始化完成后重启服务

`--stop-after-init` 会让容器退出，`restart: unless-stopped` 会自动把它拉起来；
若没有自动重启，手工执行：

```bash
docker compose restart odoo
```

### 1.4 设置管理员密码与登录

- 数据库管理主密码：`.env` 的 `ODOO_ADMIN_PASSWD`（用于数据库备份/还原/删除界面）。
- 管理员账号：`.env` 的 `ODOO_ADMIN_USER`（默认 `admin`），
  首次安装 `base` 模块时会以 `admin` / `admin` 创建，**必须在首次登录后立即改密**：

```bash
# 方式一：界面操作 —— 设置 -> 用户 -> 管理员 -> 修改密码
# 方式二：命令行重置（忘记密码时）
docker compose exec odoo odoo shell -d gz_odoo --db_host=postgres --db_user=gz --db_password="<密码>"
# 进入 shell 后：
#   env['res.users'].browse(2).write({'password': '新密码'})
#   env.cr.commit()
```

---

## 2. 常用运维命令

```bash
# 升级/重装某个自研模块（改了 xml/py 后）
docker compose exec odoo odoo -d gz_odoo -u gz_trade --stop-after-init

# 全量升级所有 gz_* 模块
docker compose exec odoo odoo -d gz_odoo -u all --stop-after-init

# 只更新模块列表（新增了模块目录后，让 Odoo 扫描到）
docker compose exec odoo odoo -d gz_odoo --update-list --stop-after-init

# 打开 Odoo shell（调试 ORM）
docker compose exec odoo odoo shell -d gz_odoo --db_host=postgres --db_user=gz --db_password="<密码>"

# 查看模块当前状态
docker compose exec postgres psql -U gz -d gz_odoo \
  -c "SELECT name, state, latest_version FROM ir_module_module WHERE name LIKE 'gz_%' ORDER BY name;"

# 备份数据库（含 filestore 说明见 deploy/README.md 数据备份章节）
docker compose exec postgres pg_dump -U gz -Fc gz_odoo > backups/gz_odoo_$(date +%Y%m%d_%H%M%S).dump

# 还原
docker compose exec -T postgres pg_restore -U gz -d gz_odoo --clean --if-exists < backups/gz_odoo_xxx.dump
```

---

## 3. 自研模块开发挂载

生产：模块随镜像构建进 `/mnt/extra-addons`（compose 挂载具名卷 `gz_odoo_addons`）。

开发：改为源码挂载，改完代码只需重启容器 + 升级模块：

```yaml
# docker-compose.yml 的 odoo 服务 volumes 段
- ../odoo/addons:/mnt/extra-addons
```

```bash
docker compose restart odoo
docker compose exec odoo odoo -d gz_odoo -u gz_product --stop-after-init
```

---

## 4. 常见问题

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 启动日志 `could not connect to server: Connection refused` | postgres 还没就绪 | compose 已配置 `depends_on: service_healthy`；仍报错则看 `docker compose logs postgres` 是否初始化失败 |
| 日志 `relation "ir_module_module" does not exist` | 数据库未初始化 | 按 1.2 执行带 `-i base` 的安装命令 |
| 模块在界面上搜不到 | addons_path 未包含模块目录，或模块缺少 `__manifest__.py` | 检查 `addons_path`（`odoo.conf` 与 compose 的 `ADDONS_PATH`），确认目录结构为 `addons/gz_trade/__manifest__.py` |
| 模块升级报依赖错误 | manifest 的 `depends` 与实际不符 | 按 `docs/02` 的依赖表修正（如 `gz_trade` 依赖 `sale_management`/`purchase`） |
| 界面样式丢失、静态资源 404 | `proxy_mode` 未开或 `web.base.url` 不对 | 确认 `odoo.conf` 有 `proxy_mode = True`；设置 `web.base.url = http://<域名>:8080/odoo` |
| 上传附件失败 | filestore 目录不可写 | `odoo_data` 卷属主应为 uid 101；`docker compose exec -u root odoo chown -R odoo:odoo /var/lib/odoo` |
| 中文乱码 | 数据库编码非 UTF8 | `01-init.sql` 已指定 `ENCODING 'UTF8'`；若库已建好需重建或 `ALTER DATABASE` |
| 定时任务不执行 | `max_cron_threads = 0` | `odoo.conf` 已设 2；注意 `workers = 0`（开发模式）下 cron 由主进程处理 |
