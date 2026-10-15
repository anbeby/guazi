# 部署准备与回滚

此仓库保留前后端、Odoo 扩展、数据库迁移与部署模板。运行卷、生产凭据、镜像包和备份不在仓库中。

## 兼容性

- API 使用 Python 3.11 与 `services/api/requirements.txt`，Odoo 镜像为 17.0；管理后台要求 Node.js >=20，锁文件为 `apps/admin-web/package-lock.json`。
- `deploy/docker-compose.production.yml` 使用 `!override`，部署前确认目标机 Docker Compose >=2.24.4；旧版 Compose 不兼容该覆盖语法。
- 生产配置将持久化目录绑定至 `/data/guazi`。先确认该路径确属预期数据盘、容量充足且旧数据挂载正确。

## 发布前

1. 在 192.168.3.5 和公网网关核验当前版本、入口、端口、容器、卷、依赖服务与健康状态。
2. 备份 PostgreSQL、Odoo filestore、MinIO、Redis 等业务数据，复制一份到独立磁盘，并在隔离环境恢复验证。
3. 由服务器上的生产变量文件提供密码和密钥，绝不以仓库模板覆盖现有值。
4. 在隔离环境执行 Alembic 与 Odoo 模块升级，完成前后端联调；记录当前镜像、配置和网关规则。

## 发布与回滚

按 `deploy/scripts` 中的现有流程分阶段更新 API、Odoo、前端与网关。每阶段验证登录、商家、商品、交易与只读入口。若失败，停止写入并恢复旧镜像与配置；若数据库结构或数据已变化，使用验证过的备份恢复并核对一致性。对外切流需在健康检查通过后进行。
