-- =============================================================================
-- 02-readonly.sql —— 创建 Superset 报表专用只读账号
-- 执行身份：POSTGRES_USER（超级用户），由官方镜像在 initdb 阶段按文件名顺序执行
-- -----------------------------------------------------------------------------
-- 【为什么这里写死了账号密码】
--   PostgreSQL 官方镜像的 /docker-entrypoint-initdb.d 只把 *.sql 交给 psql 执行，
--   不会注入容器环境变量，因此 .env 里的 POSTGRES_READONLY_USER/PASSWORD 无法在
--   SQL 中直接引用。这里采用"与 .env.example 默认值保持一致 + psql \set 变量"的方式：
--
--   默认账号：gz_ro
--   默认密码：gz_ro_change_me
--
--   **必须与 deploy/.env.example 的 POSTGRES_READONLY_USER / POSTGRES_READONLY_PASSWORD
--   以及 SUPERSET_PLATFORM_URI / SUPERSET_ODOO_URI 保持一致**。
--   如果你已经在 .env 中改了只读账号或密码，请任选一种方式修正：
--
--   方式 A（推荐，无需重建数据卷）：以超级用户连入数据库手工执行
--     docker compose exec postgres psql -U gz -d gz_platform -c \
--       "ALTER ROLE gz_ro WITH PASSWORD '你的新密码';"
--     若还要改账号名，需先 CREATE ROLE 新账号并按本文件重新授权。
--
--   方式 B（全新环境）：把本文件中的 gz_ro / 密码改成与 .env 一致后再启动，
--     注意仅在数据卷为空（首次初始化）时才会执行本脚本。
--
-- 【权限设计原则】
--   Superset 只做查询，因此只授予 CONNECT + USAGE + SELECT，
--   并设置 default privileges，保证"将来新建的表"也自动可读。
--   不授予 CREATE / INSERT / UPDATE / DELETE / TRUNCATE。
-- =============================================================================

\set ro_user 'gz_ro'
\set ro_password 'gz_ro_change_me'

\echo '[02-readonly] 创建只读报表账号 ...'

-- ---------------------------------------------------------------------------
-- 1) 创建只读角色（不授予 LOGIN 之外的管理属性）
--    \gexec 实现"不存在才创建"，重复执行不报错。
-- ---------------------------------------------------------------------------
SELECT format(
         'CREATE ROLE %I WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT CONNECTION LIMIT 20',
         :'ro_user', :'ro_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'ro_user')\gexec

-- 已存在时同步密码，保证与 .env 对齐（幂等）
SELECT format('ALTER ROLE %I WITH PASSWORD %L', :'ro_user', :'ro_password')\gexec

-- 防跑飞：单条查询最长 5 分钟，避免大屏/临时 SQL 拖垮生产库
SELECT format('ALTER ROLE %I SET statement_timeout = ''5min''', :'ro_user')\gexec
SELECT format('ALTER ROLE %I SET idle_in_transaction_session_timeout = ''2min''', :'ro_user')\gexec

-- ---------------------------------------------------------------------------
-- 2) 允许连接三个业务库（Superset 主要用 gz_platform 与 gz_odoo）
--    用 unnest 一次生成多行，再交给 \gexec 逐条执行（\gexec 每条只执行一条语句）
-- ---------------------------------------------------------------------------
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', db, :'ro_user')
FROM unnest(ARRAY['gz_platform', 'gz_odoo', 'superset']) AS db\gexec

-- ---------------------------------------------------------------------------
-- 3) gz_platform：授予 gz schema 的 USAGE + SELECT
--    同时对"当前已存在"与"将来创建"的表/序列生效。
-- ---------------------------------------------------------------------------
\connect gz_platform

GRANT USAGE ON SCHEMA gz TO :"ro_user";
GRANT USAGE ON SCHEMA public TO :"ro_user";

GRANT SELECT ON ALL TABLES    IN SCHEMA gz TO :"ro_user";
GRANT SELECT ON ALL SEQUENCES IN SCHEMA gz TO :"ro_user";
GRANT SELECT ON ALL TABLES    IN SCHEMA public TO :"ro_user";

-- 关键：Alembic 后续迁移新建的表默认也会对只读账号开放 SELECT
ALTER DEFAULT PRIVILEGES IN SCHEMA gz     GRANT SELECT ON TABLES TO :"ro_user";
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO :"ro_user";

-- 只读账号的默认 search_path，避免 Superset 写 SQL 时非要带 gz. 前缀
ALTER ROLE :"ro_user" IN DATABASE gz_platform SET search_path TO gz, public;

\echo '[02-readonly] gz_platform 授权完成'

-- ---------------------------------------------------------------------------
-- 4) gz_odoo：Odoo 表都在 public schema（由 Odoo 建表），授予只读
--    注意：default privileges 只能对"当前角色将来创建的对象"生效，
--          Odoo 建表角色是 gz（同为超级用户），因此这里同样用 gz 身份设置。
-- ---------------------------------------------------------------------------
\connect gz_odoo

GRANT USAGE ON SCHEMA public TO :"ro_user";
GRANT SELECT ON ALL TABLES    IN SCHEMA public TO :"ro_user";
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO :"ro_user";

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO :"ro_user";

-- Odoo 首次安装模块后新表才会出现；若 Odoo 先于本脚本建表也无妨，
-- 上面的 ALTER DEFAULT PRIVILEGES 已覆盖"之后新建"的表。
-- 若在 Odoo 已建完表之后才补授只读权限，可重复执行本文件段或用：
--   docker compose exec postgres psql -U gz -d gz_odoo -c \
--     "GRANT SELECT ON ALL TABLES IN SCHEMA public TO gz_ro;"

\echo '[02-readonly] gz_odoo 授权完成'

-- ---------------------------------------------------------------------------
-- 5) 汇总确认
-- ---------------------------------------------------------------------------
\connect gz_platform

\echo '[02-readonly] 完成。只读账号：gz_ro（请在 .env 中同步密码，并仅用于 Superset 数据源）'
SELECT rolname AS readonly_role, rolcanlogin AS can_login, rolsuper AS is_superuser
FROM pg_roles WHERE rolname = :'ro_user';
