-- =============================================================================
-- 01-init.sql —— PostgreSQL 首次初始化脚本（仅在数据卷为空时由官方镜像执行）
-- 执行身份：POSTGRES_USER（默认 gz），默认连接到 POSTGRES_DB
-- 执行顺序：本文件 → 02-readonly.sql（按文件名升序）
-- 幂等性：全部使用 IF NOT EXISTS / 异常捕获，重复执行安全。
--
-- 目标形态（同实例三库）：
--   gz_odoo       Odoo ERP 业务库（由 Odoo 自行建表）
--   gz_platform   自研产业平台库（业务表位于 schema gz）
--   superset      Superset 元数据库
-- 另：本库（POSTGRES_DB，默认 gz_platform）内创建 schema gz，
--     并预装 pg_trgm（模糊检索/相似度）与 uuid-ossp（UUID 主键）扩展。
-- =============================================================================

\echo '[01-init] 开始创建业务数据库 ...'

-- ---------------------------------------------------------------------------
-- 1) 创建三个业务库
--    注意：CREATE DATABASE 不能放在事务块中，因此不能包在 BEGIN/COMMIT 内。
--    这里用 \gexec 实现"不存在才创建"，避免重跑报错。
-- ---------------------------------------------------------------------------
SELECT 'CREATE DATABASE gz_odoo     OWNER ' || quote_ident(current_user) || ' ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'gz_odoo')\gexec

SELECT 'CREATE DATABASE gz_platform OWNER ' || quote_ident(current_user) || ' ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'gz_platform')\gexec

SELECT 'CREATE DATABASE superset    OWNER ' || quote_ident(current_user) || ' ENCODING ''UTF8'''
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'superset')\gexec

\echo '[01-init] 数据库创建完成：gz_odoo / gz_platform / superset'

-- ---------------------------------------------------------------------------
-- 2) 自研平台库 gz_platform：创建 gz schema + 扩展
--    对应 docs/03-数据模型设计.md —— 自研业务表全部位于 schema gz。
-- ---------------------------------------------------------------------------
\connect gz_platform

CREATE SCHEMA IF NOT EXISTS gz;
COMMENT ON SCHEMA gz IS '自研产业平台业务 schema（商户/商品/库存/交易/结算/溯源）';

-- 扩展：
--   pg_trgm    模糊检索（keyword 检索、商品名称相似度，ES 降级时的 SQL LIKE 加速）
--   uuid-ossp  生成 UUID（外部单据号、幂等键、附件 key）
--   citext     大小写不敏感文本（登录名、编码去重），可选但建议保留
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- 说明：不安装 citext / btree_gin，减少对镜像与权限的额外要求；
--       若后续确需大小写不敏感编码列，可在 Alembic 迁移中显式 CREATE EXTENSION。

COMMENT ON EXTENSION pg_trgm IS '三元组模糊匹配，供平台关键词检索使用';
COMMENT ON EXTENSION "uuid-ossp" IS 'UUID 生成，供幂等键与附件 key 使用';

-- 让 gz schema 出现在默认 search_path 中（会话级；应用侧仍会显式声明 schema）
ALTER DATABASE gz_platform SET search_path TO gz, public;

-- 自研平台表结构与索引由 Alembic 迁移管理（services/api/alembic），
-- 本脚本只负责数据库/schema/扩展三件事，不在此建业务表，避免与迁移冲突。

-- ---------------------------------------------------------------------------
-- 3) Odoo 业务库 gz_odoo：安装 Odoo 依赖的扩展
--    Odoo 17 会自行创建 public schema 下的全部表；这里只补扩展。
-- ---------------------------------------------------------------------------
\connect gz_odoo

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Odoo 对 public schema 的权限（属主已是 POSTGRES_USER，此处仅示意，
-- 若后期把 Odoo 库拆分给独立账号，请在此授权并同步 compose 的 HOST/USER/PASSWORD）
GRANT ALL ON SCHEMA public TO CURRENT_USER;

-- ---------------------------------------------------------------------------
-- 4) Superset 元数据库 superset：仅需 UTF8 与 public schema
--    表由 `superset db upgrade` 在 superset-init 一次性容器中创建。
--    连接池、行数限制等由 conf/superset/superset_config.py 控制。
-- ---------------------------------------------------------------------------
\connect superset

CREATE EXTENSION IF NOT EXISTS pg_trgm;
GRANT ALL ON SCHEMA public TO CURRENT_USER;

-- 回到默认库，便于后续脚本（02-readonly.sql）继续在 gz_platform 中操作
\connect gz_platform

\echo '[01-init] 完成：三库就绪，gz schema 与扩展已创建。'
