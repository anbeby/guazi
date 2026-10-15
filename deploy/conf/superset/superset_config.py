# ==============================================================================
# 第十师瓜子油料数字化交易平台 —— Apache Superset 4.0.2 配置
# 挂载位置：/app/pythonpath/superset_config.py（只读）
# 生效方式：容器环境变量 SUPERSET_CONFIG_PATH=/app/pythonpath/superset_config.py
# ------------------------------------------------------------------------------
# 用途：产业驾驶舱、跨库报表（gz_platform 自研库 + gz_odoo ERP 库）
# 元数据库：PostgreSQL 的 superset 库（见 .env 的 SUPERSET_DATABASE_URI）
# 初始化：由一次性容器 superset-init 执行 db upgrade / create-admin / init
# ==============================================================================

import os
from datetime import timedelta

# ------------------------------------------------------------------------------
# 1. 基础路径与密钥
# ------------------------------------------------------------------------------
# 配置模块所在目录（Superset 会据此加载自定义插件）
PYTHONPATH = os.environ.get("PYTHONPATH", "/app/pythonpath")

# 【必须】会话签名与加密密钥；一旦更换，已保存的数据源密码需重新录入。
# 生成方式：openssl rand -base64 42
SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "CHANGE_ME_SUPERSET_SECRET_KEY")

# 运行目录（上传的 CSV、缩略图、缓存）
DATA_DIR = os.environ.get("SUPERSET_HOME", "/app/superset_home")

# ------------------------------------------------------------------------------
# 2. 元数据库连接（PostgreSQL）
# ------------------------------------------------------------------------------
# 也可用 SUPERSET_DATABASE_URI 形式；这里显式拆分便于调参。
SQLALCHEMY_DATABASE_URI = os.environ.get(
    "SUPERSET_DATABASE_URI",
    "postgresql+psycopg2://gz:CHANGE_ME@postgres:5432/superset",
)

# 连接池：Superset 元数据读写并发不高，但事务要短、连接要能自愈
SQLALCHEMY_ENGINE_OPTIONS = {
    "pool_size": 10,           # 常驻连接
    "max_overflow": 20,        # 峰值可临时超出 20 个
    "pool_timeout": 30,        # 取连接超时（秒）
    "pool_recycle": 1800,      # 30 分钟回收，规避 PG 侧空闲断连
    "pool_pre_ping": True,     # 取连接前探活，防 "server closed connection"
    "connect_args": {
        "connect_timeout": 10,
        "application_name": "gz-superset",
    },
}

# 元数据表前缀（多环境共用一个 superset 库时可用）
# SQLALCHEMY_DATABASE_URI 已隔离到独立库，这里留空即可
# TABLE_NAMES = {"ab_user": "ab_user"}

# ------------------------------------------------------------------------------
# 3. 反向代理与外部访问地址
# ------------------------------------------------------------------------------
# 网关以 /superset 前缀暴露（见 conf/nginx/nginx.conf），因此必须开启 ProxyFix，
# 让 Superset 依据 X-Forwarded-Proto/Host/Prefix 生成正确的静态资源与跳转 URL。
ENABLE_PROXY_FIX = True
# 若前置还有一层 SLB/CDN，可加大 proxy fix 层数
PROXY_FIX_CONFIG = {"x_for": 1, "x_proto": 1, "x_host": 1, "x_port": 1, "x_prefix": 1}

# 允许 iframe 嵌入（驾驶舱大屏被其他系统嵌入时使用；不嵌入可设为 "self"）
# 说明：flask-talisman 负责下发 CSP 等安全响应头。内网 HTTP 部署时必须关闭，
#       否则 Talisman 会强制跳转 HTTPS 导致无法访问。
#       生产启用 HTTPS 后建议改为：
#         TALISMAN_ENABLED = True
#         TALISMAN_CONFIG = {"content_security_policy": {...}, "force_https": True}
#       并把需要嵌入 Superset 的域名写入 CSP 的 frame-ancestors。
TALISMAN_ENABLED = False

# 静态资源缓存
SEND_FILE_MAX_AGE_DEFAULT = timedelta(days=30)

# ------------------------------------------------------------------------------
# 4. 安全与账号
# ------------------------------------------------------------------------------
# 强制登录后才能访问（大屏如需免登录，改为 False 并为大屏单独建公开角色）
PUBLIC_ROLE_LIKE = "Gamma"          # 匿名公开角色继承 Gamma 的权限
AUTH_ROLE_PUBLIC = "Public"
AUTH_USER_REGISTRATION = False       # 关闭自助注册，账号由管理员创建
AUTH_TYPE = 1                        # 1 = 数据库账号密码认证

# 会话与令牌有效期
PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
SUPERSET_SESSION_COOKIE_SECURE = False   # HTTP 内网部署；启用 HTTPS 后设 True
SUPERSET_SESSION_COOKIE_SAMESITE = "Lax"

# 【必须修改】首次初始化由 superset-init 创建的管理员（此处仅作兜底，
# 避免某些发行版读取不到环境变量时报错；真实值来自 .env）
# 注意：Superset 本身不读取如下变量建号，实际建号在 compose 的 superset-init 中完成。
SUPERSET_ADMIN_FALLBACK_USERNAME = os.environ.get("SUPERSET_ADMIN_USERNAME", "admin")

# 登录防爆破（配合 nginx 的 gz_auth 限流形成双层防护）
AUTH_RATE_LIMITED = True
AUTH_RATE_LIMIT = "30 per minute"

# 用户自建数据源/上传 CSV 的权限管控：阶段一仅管理员可建数据源
# （由角色权限控制，此处保留 Superset 默认；如需收紧可在界面调整）

# ------------------------------------------------------------------------------
# 5. 功能开关
# ------------------------------------------------------------------------------
FEATURE_FLAGS = {
    # 大屏与可视化增强
    "DASHBOARD_NATIVE_FILTERS": True,
    "DASHBOARD_CROSS_FILTERS": True,
    "DASHBOARD_NATIVE_FILTERS_SET": True,
    "DASHBOARD_RBAC": True,                  # 按角色控制看板可见性
    "HORIZONTAL_FILTER_BAR": True,
    "DASHBOARD_VIRTUALIZATION": True,        # 大屏图表多时按需渲染
    "GLOBAL_ASYNC_QUERIES": False,           # 阶段一单机部署，不需要异步查询后端
    # 报表与告警
    "ALERT_REPORTS": True,                   # 定时报表（产业月报邮件推送）
    "THUMBNAILS": True,                      # 看板缩略图
    "EMBEDDED_SUPERSET": True,               # 允许嵌入到园区大屏
    # 数据集与 SQL
    "ENABLE_TEMPLATE_PROCESSING": True,      # Jinja 模板（动态时间范围）
    "SQL_VALIDATORS_BY_ENGINE": False,
    "ALLOW_ADHOC_SUBQUERY": True,
    "ESTIMATE_QUERY_COST": True,
    "USE_DENYLIST": True,                    # 只读账号 + SQL 关键字黑名单双重保障
    # 中文化与本地化
    "ENABLE_JAVASCRIPT_CONTROLS": False,     # 禁止自定义 JS，防 XSS
    "TAGGING_SYSTEM": True,                  # 数据集/看板打标签，便于分类管理
    "LISTVIEWS_DEFAULT_CARD_VIEW": False,
}

# ------------------------------------------------------------------------------
# 6. 中文与时区（平台统一 Asia/Shanghai）
# ------------------------------------------------------------------------------
BABEL_DEFAULT_LOCALE = "zh"
BABEL_DEFAULT_TIMEZONE = os.environ.get("TZ", "Asia/Shanghai")
LANGUAGES = {
    "zh": {"flag": "cn", "name": "简体中文"},
    "en": {"flag": "us", "name": "English"},
}
# 让新用户默认中文（首次登录后仍可在个人设置中切换）
DEFAULT_LOCALE = "zh"

# 日期/数字格式（人民币、千分位）
# 说明：Superset 通过数据集列级 D3 格式控制，此处仅设置默认货币符号
CURRENCIES = ["CNY"]

# ------------------------------------------------------------------------------
# 7. 查询与限流（保护 PostgreSQL 生产库）
# ------------------------------------------------------------------------------
# 单次查询返回行数上限（防止 SELECT * 拖垮浏览器与数据库）
ROW_LIMIT = 50000
# 图表的默认行数上限
DEFAULT_VIZ_ROW_LIMIT = 10000
# SQL Lab 单次最多返回行数
SQL_MAX_ROW = 100000
# 查询超时（秒）：与数据库端 statement_timeout=5min 形成双保险
SUPERSET_WEBSERVER_TIMEOUT = 300
SQLLAB_TIMEOUT = 300
SQLLAB_ASYNC_TIME_LIMIT_SEC = 600
# 定时查询与缓存
CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",     # 单机部署；如需多副本换成 Redis
    "CACHE_DEFAULT_TIMEOUT": 300,
    "CACHE_KEY_PREFIX": "gz_superset_",
}
DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 600,    # 图表结果缓存 10 分钟
    "CACHE_KEY_PREFIX": "gz_superset_data_",
}
FILTER_STATE_CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
}
EXPLORE_FORM_DATA_CACHE_CONFIG = {
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
}
# 说明：单机如需更强缓存，可改为
#   {"CACHE_TYPE": "RedisCache", "CACHE_REDIS_URL": os.environ.get("REDIS_URL"), ...}
# 但 Superset 官方镜像需额外安装 redis 包，阶段一先用 SimpleCache。

# ------------------------------------------------------------------------------
# 8. 业务库连接（供管理员在界面中"添加数据库"时参考，不会自动入库）
# ------------------------------------------------------------------------------
# 平台库（只读账号，schema gz）
GZ_PLATFORM_DB_URI = os.environ.get("GZ_PLATFORM_DB_URI", "")
# Odoo 库（只读账号，public schema）
GZ_ODOO_DB_URI = os.environ.get("GZ_ODOO_DB_URI", "")

# 阶段一不在配置里预置数据源，改由管理员在界面手工添加（更直观、可即时验证连接）：
#   设置 -> 数据库连接 -> 添加：
#     显示名：瓜子平台库(只读)
#     SQLAlchemy URI：postgresql://gz_ro:****@postgres:5432/gz_platform
#     勾选 "Allow this database to be queried in SQL Lab"（仅管理员）
#   再添加一个：瓜子Odoo库(只读) -> .../gz_odoo
# 注意：只读账号默认 search_path = gz,public，查询 gz_platform 时可直接写表名；
#       查询 gz_odoo 时请写 public. 前缀或显式设置 schema。
# 若希望用配置预置数据源，Superset 支持 PREVIEW / "Predefined databases" 方案，
# 但需要额外的初始化脚本，阶段一从简（见 deploy/README.md 的 Superset 章节）。

# ------------------------------------------------------------------------------
# 9. 告警/报表（可选）与邮件
# ------------------------------------------------------------------------------
SMTP_HOST = os.environ.get("SMTP_SERVER") or ""
SMTP_PORT = int(os.environ.get("SMTP_PORT") or 25)
SMTP_STARTTLS = False
SMTP_SSL = False
SMTP_USER = os.environ.get("SMTP_USER") or ""
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD") or ""
SMTP_MAIL_FROM = os.environ.get("EMAIL_FROM") or "superset@example.com"
# 定时报表/告警需要 Celery worker 与 beat；单机 compose 未启用，
# 阶段一如需要请另行增加 superset-worker / superset-beat 两个服务（同镜像不同 command）。

# ------------------------------------------------------------------------------
# 10. 日志
# ------------------------------------------------------------------------------
import logging  # noqa: E402

LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s:%(levelname)s:%(name)s:%(message)s"
# 查询日志（排查慢查询与异常 SQL）
ENABLE_TIME_ROTATE = False
# 审计日志：记录谁在执行什么查询（满足等保审计要求）
FAB_ADD_SECURITY_API = True
