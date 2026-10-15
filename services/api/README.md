# 第十师瓜子油料数字化交易平台 —— 自研 B2B 交易与产业运营平台（后端）

FastAPI + SQLAlchemy 2.0 + PostgreSQL 16。

## 目录

```
services/api/
├── app/
│   ├── main.py              应用入口（中间件、异常处理、路由挂载、静态控制台）
│   ├── worker.py            后台任务进程（outbox 推送 Odoo / 索引同步 / 定时跑批）
│   ├── initial_data.py      数据库初始化与种子数据（幂等）
│   ├── core/                配置、数据库、安全、缓存、错误、依赖、数据权限
│   ├── models/              ORM 模型（8 个领域文件）
│   ├── schemas/             Pydantic 请求/响应模型
│   ├── services/            领域服务（库存、交易、结算、编码、集成）
│   ├── api/v1/              REST 路由（12 个模块路由）
│   ├── integrations/        Odoo JSON-RPC、MinIO/本地存储、ElasticSearch（均可降级）
│   └── static/console/      免构建运营控制台（直连真实 API）
├── alembic/                 数据库迁移
├── tests/                   单元与集成测试
├── requirements.txt
└── Dockerfile
```

## 本地开发

```bash
python -m venv .venv
.venv/Scripts/activate           # Windows
pip install -r requirements-dev.txt
copy .env.example .env
python -m pytest -q              # 默认 SQLite 内存库，无需外部依赖
uvicorn app.main:app --reload --port 8000
```

生产运行使用 PostgreSQL；`DATABASE_URL` 形如
`postgresql+psycopg://gz:pass@postgres:5432/gz_platform`，
引擎会自动设置 `search_path=gz,public`，业务表全部落在 `gz` schema。

## 初始化数据

```bash
python -m app.initial_data           # 幂等，可重复执行
python -m app.initial_data --demo    # 追加演示交易数据
```

默认管理员：`admin / Admin@123`（首次登录后请立即修改）。

## 关键设计

- **统一响应信封** `{code, message, data, request_id}`，见 `docs/04-接口规范.md`。
- **鉴权**：JWT(HS256，标准库实现) + Redis 黑名单，PBKDF2-SHA256 密码散列。
- **数据隔离**：`app/core/scope.py` 统一注入企业/园区维度过滤，路由内禁止手写隔离条件。
- **中间件降级**：Redis / MinIO / ElasticSearch 不可用时自动降级为进程内缓存 / 本地磁盘 / SQL LIKE，交易主链路不中断。
- **库存并发**：PostgreSQL 下行级 `SELECT ... FOR UPDATE`，SQLite（测试）自动跳过。
- **集成出站**：`sync_outbox` 表 + worker 推送 Odoo JSON-RPC，幂等键 + 重试 + 对账兜底。
