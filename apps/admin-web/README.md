# admin-web · 第十师瓜子油料数字化交易平台 PC 管理后台

面向**平台管理员 / 园区运营人员 / 商户 / 供应商 / 采购商 / 财务**的 PC 端管理后台。
后端为自研平台 REST API（`services/api`，默认 `http://localhost:8000`），
企业侧账务与 ERP 能力由 Odoo 承载（见 `odoo/addons/README.md`）。

---

## 1. 技术栈

| 分类 | 选型 | 版本 |
| --- | --- | --- |
| 框架 | Vue 3（`<script setup>` + Composition API） | ^3.4.38 |
| 语言 | TypeScript | ~5.5.4 |
| 构建 | Vite | ^5.4.8 |
| 路由 | Vue Router 4（`createWebHistory`，history 模式） | ^4.4.5 |
| 状态 | Pinia | ^2.2.4 |
| UI | Element Plus（中文语言包 `zh-cn`） | ^2.8.4 |
| 图标 | @element-plus/icons-vue（`main.ts` 全量注册） | ^2.3.1 |
| 图表 | ECharts | ^5.5.1 |
| 请求 | Axios（统一信封解包 / 401 刷新 / 错误提示） | ^1.7.7 |
| 时间 | dayjs（`zh-cn`） | ^1.11.13 |
| 进度条 | NProgress | ^0.2.0 |
| 开发增强 | unplugin-auto-import、unplugin-vue-components（Element Plus 按需 + 组件自动注册） | — |
| 类型检查 | vue-tsc | ^2.1.6 |

运行时要求：**Node.js >= 20**（见 `package.json` 的 `engines`）。

---

## 2. 目录说明

```
apps/admin-web/
├── index.html                # SPA 入口
├── vite.config.ts            # 别名 @ -> src、dev server（0.0.0.0:5173）、/api 代理、build.outDir=dist
├── tsconfig.json             # 应用 TS 配置（含 @/* 路径映射）
├── tsconfig.node.json        # vite.config.ts 的 Node 侧 TS 配置
├── .env.development          # 开发环境变量（VITE_API_BASE_URL=/api/v1）
├── .env.production           # 生产环境变量（构建期注入，nginx 反代 /api）
├── Dockerfile                # 两阶段构建：node:20-alpine 构建 → nginx:alpine 托管
├── nginx.conf                # 容器内站点配置：SPA 回退 + /api 反代 api:8000
└── src/
    ├── main.ts               # 应用装配：Element Plus、图标、Pinia、Router、v-permission
    ├── App.vue               # 根组件（router-view）
    ├── env.d.ts              # import.meta.env 类型声明
    ├── api/                  # 接口层：按业务域拆分，统一走 request.ts 的 http 封装
    │   ├── request.ts        # axios 实例、响应信封解包、401 静默刷新、错误码提示
    │   ├── types.ts          # 全量请求/响应 TS 类型（与 docs/04-接口规范.md 对齐）
    │   └── auth/user/role/org/enterprise/category/product/warehouse/inventory/
    │       trade/settlement/park/trace/dashboard/file/system .ts
    ├── components/           # 通用组件（unplugin-vue-components 自动注册）
    │   ├── PageTable.vue     # 分页表格 + 加载态 + 空数据
    │   ├── SearchForm.vue    # 查询表单容器（@search / @reset）
    │   ├── StatusTag.vue     # 状态标签（按字典着色）
    │   ├── DictSelect.vue    # 字典下拉（数据源 stores/dict.ts）
    │   ├── FileUpload.vue    # 文件上传（POST /files/upload）
    │   └── ChartCard.vue     # ECharts 卡片（按需注册图表类型）
    ├── directives/
    │   └── permission.ts     # v-permission 按钮级权限指令
    ├── layout/               # 主框架：Sidebar 菜单 / Navbar / TagsView / Breadcrumb
    ├── router/
    │   ├── routes.ts         # 静态路由表（meta: title/icon/permission/hidden/public）
    │   └── index.ts          # 守卫：登录态、/auth/me 恢复、权限校验、NProgress
    ├── stores/               # Pinia：user（会话/权限）、app（侧栏、面包屑、标签页、主题）、dict（字典）
    ├── styles/index.css      # 设计变量（--gz-*）、布局辅助类、Element Plus 主色覆盖
    ├── utils/                # auth（令牌持久化）、format（金额/数量/时间）、download（CSV/打印）
    └── views/                # 页面（与路由一一对应，见 §6 页面清单）
```

---

## 3. 本地开发

```bash
cd apps/admin-web

# 1) 安装依赖
npm install

# 2) 启动开发服务器（vite.config.ts: host=0.0.0.0, port=5173）
npm run dev
```

访问地址：

- 本机：`http://localhost:5173`
- 局域网其他设备：`http://<开发机内网IP>:5173`（因 `server.host: '0.0.0.0'`，非默认 localhost）

### 接口代理

开发环境下前端所有请求都以 `/api` 开头，由 **Vite dev server 代理**到自研后端：

| 前端请求 | 代理目标 | 配置位置 |
| --- | --- | --- |
| `/api/**` | `http://localhost:8000` | `vite.config.ts` → `server.proxy['/api']`（`changeOrigin: true`） |

因此前端代码里不需要写死后端地址：`.env.development` 中 `VITE_API_BASE_URL=/api/v1` 即可。
请先确保自研后端已在 `8000` 端口启动（`services/api`，健康检查 `GET /health`）。
`vite.config.ts` 的 `preview.proxy` 采用相同规则，`npm run preview` 时同样可直接联调。

### 常用脚本

| 命令 | 说明 |
| --- | --- |
| `npm run dev` | 启动 Vite 开发服务器（0.0.0.0:5173） |
| `npm run build` | 类型检查 + 生产构建（`vue-tsc --noEmit` → `vite build`，产物 `dist/`） |
| `npm run build:only` | 仅构建，跳过类型检查（应急用） |
| `npm run preview` | 本地预览构建产物（0.0.0.0:4173） |
| `npm run type-check` | 仅执行 `vue-tsc --noEmit -p tsconfig.json` |

### 环境变量

| 变量 | 开发（`.env.development`） | 生产（`.env.production`） | 说明 |
| --- | --- | --- | --- |
| `VITE_APP_TITLE` | 第十师瓜子油料数字化交易平台 | 同左 | 浏览器标题（`document.title`） |
| `VITE_API_BASE_URL` | `/api/v1` | `/api/v1` | REST 前缀（生产由网关 / nginx 反代） |
| `VITE_UPLOAD_URL` | `/api/v1/files/upload` | 同左 | 上传地址 |

---

## 4. 生产构建

```bash
cd apps/admin-web
npm ci            # 或 npm install
npm run build     # 类型检查通过后输出 dist/
```

- 构建产物目录：`dist/`（`vite.config.ts` → `build.outDir: 'dist'`，`sourcemap: false`）。
- 已按 `vue` / `element` / `charts` 手动分包（`build.rollupOptions.output.manualChunks`）。
- 路由为 **history 模式**，托管方必须配置 SPA 回退（`try_files $uri $uri/ /index.html`），
  仓库内 `nginx.conf` 已包含该配置。
- 端口约定：dev `5173`、preview `4173`，**均不使用 80**，避免与网关 / nginx 的 80 端口冲突。

---

## 5. Docker 构建与部署

`Dockerfile` 为两阶段构建：`node:20-alpine` 安装依赖并 `npm run build`，
再把 `dist/` 复制进 `nginx:alpine`，站点配置使用仓库内 `nginx.conf`（监听 80）。

### 5.1 单独构建镜像

```bash
cd apps/admin-web
docker build -t gz-admin-web:latest .
docker run -d --name gz-admin-web -p 8081:80 gz-admin-web:latest
```

> 容器内 nginx 监听 `80`；如直连宿主请映射到非 80 端口（示例用 8081），
> 网关统一入口由 `deploy/conf/nginx/nginx.conf` 提供。

### 5.2 随整套环境构建（推荐）

由 `deploy/docker-compose.yml` 编排，`admin-web` 服务的构建上下文即本目录：

```bash
cd deploy
docker compose build admin-web
docker compose up -d admin-web
```

- 服务名 / 容器名：`admin-web` / `gz-admin-web`
- 镜像名：`gz-admin-web:latest`（可用 `ADMIN_WEB_IMAGE` 覆盖）
- 容器内 nginx 将 `/api/` 反向代理到 `api:8000`，`/health`、`/ready` 透传到后端探针
- 统一网关访问入口：`http://<host>:8080/`（生产建议只暴露网关端口，见 `deploy/README.md`）

### 5.3 镜像内 nginx 要点（`nginx.conf`）

| 路径 | 行为 |
| --- | --- |
| `/assets/` | 带 hash 的静态资源，30 天强缓存（immutable） |
| `/api/` | 反代 `http://api:8000/api/`，透传 `Host / X-Real-IP / X-Forwarded-For / X-Forwarded-Proto` |
| `/health`、`/ready` | 反代后端探针 |
| `/` | `try_files $uri $uri/ /index.html`（history 模式回退），HTML 不缓存 |

---

## 6. 页面清单与对应接口

路由表见 `src/router/routes.ts`；`meta.permission` 为进入页面所需的权限码（`docs/04-接口规范.md` §3）。
所有路径均以 `VITE_API_BASE_URL`（`/api/v1`）为前缀。

| # | 路由 | 页面 | 权限码 | 主要接口 |
| --- | --- | --- | --- | --- |
| 1 | `/login` | 登录 | 公开 | `POST /auth/login`、`GET /auth/me`、`POST /auth/logout`、`POST /auth/change-password` |
| 2 | `/dashboard` | 数据驾驶舱 | `data:read` | `GET /dashboard/overview`、`/dashboard/trend`、`/dashboard/price-trend`、`/dashboard/industry`、`GET /categories/tree` |
| 3 | `/system/user` | 用户管理 | `user:read` | `GET/POST /users`、`GET/PUT/DELETE /users/{id}`、`POST /users/{id}/roles`、`POST /users/{id}/reset-password`；选项：`GET /roles`、`/enterprises`、`/org-units/tree` |
| 4 | `/system/role` | 角色权限 | `role:read` | `GET/POST /roles`、`PUT/DELETE /roles/{id}`、`GET /roles/{id}/permissions`、`PUT /roles/{id}/permissions`、`GET /permissions` |
| 5 | `/system/org` | 组织架构 | `org:read` | `GET /org-units/tree`、`POST /org-units`、`PUT/DELETE /org-units/{id}`；选项：`GET /parks` |
| 6 | `/merchant/enterprise` | 商户档案 | `merchant:read` | `GET/POST /enterprises`、`GET/PUT/DELETE /enterprises/{id}`、`POST /enterprises/{id}/audit`、`GET /enterprises/{id}/stats`、`POST /files/upload`；选项：`GET /parks` |
| 7 | `/merchant/entry` | 入驻审核 | `merchant:read` | `GET /enterprises?audit_status=pending`、`GET /enterprises/{id}`、`GET /enterprises/{id}/stats`、`POST /enterprises/{id}/audit` |
| 8 | `/product/category` | 商品分类 | `product:read` | `GET /categories/tree`、`POST /categories`、`PUT/DELETE /categories/{id}` |
| 9 | `/product/list` | 商品列表 | `product:read` | `GET/POST /products`、`PUT/DELETE /products/{id}`、`POST /products/{id}/publish`、`/offline`、`/audit`、`GET /products/{id}/inventory`；选项：`GET /categories/tree`、`/enterprises` |
| 10 | `/product/detail/:id` | 商品详情（隐藏菜单） | `product:read` | `GET /products/{id}`、`GET /products/{id}/inventory`、`POST /products/{id}/publish`、`/offline`、`/audit` |
| 11 | `/inventory/warehouse` | 仓库库位 | `inventory:read` | `GET/POST /warehouses`、`GET/PUT/DELETE /warehouses/{id}`、`GET/POST /warehouses/{id}/locations`、`PUT/DELETE /locations/{id}`；选项：`GET /enterprises`、`/parks` |
| 12 | `/inventory/stock` | 库存查询 | `inventory:read` | `GET /inventory`、`GET /inventory/summary`；选项：`GET /products`、`/warehouses` |
| 13 | `/inventory/move` | 出入库与流水 | `inventory:read` | `POST /inventory/in`、`/out`、`/transfer`、`/adjust`、`/check`、`GET /inventory/moves`；选项：`GET /products`、`/warehouses`、`/warehouses/{id}/locations` |
| 14 | `/trade/inquiry` | 询价单 | `trade:read` | `GET /inquiries`、`POST /inquiries`、`POST /inquiries/{id}/submit`、`/cancel`；选项：`GET /products`、`/enterprises` |
| 15 | `/trade/inquiry/:id` | 询价详情（隐藏菜单） | `trade:read` | `GET /inquiries/{id}`、`GET/POST /inquiries/{id}/quotations`、`POST /quotations/{id}/accept`、`/reject`、`POST /inquiries/{id}/submit`、`/cancel` |
| 16 | `/trade/order` | 订单管理 | `trade:read` | `GET /orders`、`POST /orders`、`GET /orders/{id}`、`POST /orders/{id}/confirm`、`/deliver`、`/complete`、`/cancel`；选项：`GET /products`、`/enterprises`、`/warehouses` |
| 17 | `/trade/order/:id` | 订单详情（隐藏菜单） | `trade:read` | `GET /orders/{id}`、`GET /orders/{id}/timeline`、`POST /orders/{id}/confirm`、`/deliver`、`/complete`、`/cancel`、`POST /contracts` |
| 18 | `/trade/contract` | 合同管理 | `trade:read` | `GET /contracts`、`POST /contracts`、`GET/PUT /contracts/{id}`、`POST /contracts/{id}/sign`、`POST /files/upload`；选项：`GET /orders`、`/enterprises` |
| 19 | `/settlement/list` | 结算单 | `settlement:read` | `GET /settlements`、`POST /settlements`、`GET /settlements/{id}`、`POST /settlements/{id}/confirm`、`POST /settlements/{id}/payment`；选项：`GET /enterprises` |
| 20 | `/settlement/flow` | 流水与对账 | `settlement:read` | `GET /finance/flows`、`GET /finance/statement`（前端支持导出 CSV / 打印） |
| 21 | `/park/park` | 园区与区域 | `park:read` | `GET/POST /parks`、`PUT/DELETE /parks/{id}`、`GET/POST /parks/{id}/zones`、`PUT/DELETE /zones/{id}` |
| 22 | `/park/stall` | 档口管理 | `park:read` | `GET/POST /stalls`、`PUT/DELETE /stalls/{id}`、`POST /stalls/{id}/assign`、`GET/POST /park-contracts`、`PUT /park-contracts/{id}`、`POST /park-contracts/{id}/effect`、`POST /files/upload`；选项：`GET /parks`、`/parks/{id}/zones`、`/enterprises` |
| 23 | `/trace/batch` | 溯源批次 | `trace:read` | `GET/POST /trace/batches`、`GET /trace/batches/{id}`、`POST /trace/batches/{id}/events`、`GET /trace/public/{batch_no}`、`POST /files/upload`；选项：`GET /products`、`/warehouses` |
| 24 | `/404`、`/:pathMatch(.*)*` | 页面不存在 | 公开 | 无（纯前端页面） |

**API 层已封装、当前无页面引用**（供后续迭代使用，见审查报告）：
`GET /system/info`、`GET /integration/outbox`、`POST /integration/outbox/{id}/retry`（`src/api/system.ts`）、
`GET /products/search`（`src/api/product.ts`）、`GET /quotations`、`GET /stalls/{id}`、`GET /park-contracts/{id}`、`GET /files`。

---

## 7. 权限与路由守卫

- 进入页面所需权限码写在路由 `meta.permission`，守卫按 `GET /auth/me` 返回的 `permissions` 拦截，
  无权限跳转 `/404`；`meta.public: true` 的路由（`/login`、`/404`）无需登录。
- 按钮级权限使用 `v-permission` 指令（`src/directives/permission.ts`），无权限时直接从 DOM 移除元素；
  支持 `module:*` 通配与 `platform_admin` 超级管理员（`src/stores/user.ts` → `hasPermission`）。
- 令牌持久化在 `localStorage`（`src/utils/auth.ts`）；页面刷新后由守卫调用 `/auth/me` 恢复用户态，
  请求遇到 401 时由 `src/api/request.ts` 用 refresh token 静默续期。
- 侧边菜单由 `src/router/routes.ts` 渲染，按 `meta.hidden` 隐藏、按 `meta.permission` 过滤。

---

## 8. 验证状态声明

> **本机未执行 `npm install`、`npm run build` / `npm run type-check`，也未启动 `npm run dev` 验证页面渲染。**
> 交付环境（Windows 主机）的 PowerShell 进程无法启动（错误码 `0xC0000142`），因此没有可用的命令行执行环境。
> 本文档中的命令、端口、代理与接口对照均依据 `package.json`、`vite.config.ts`、`Dockerfile`、
> `nginx.conf`、`.env.*` 与 `docs/04-接口规范.md` 静态核对得出，**构建与运行结果尚未验证**。
> 请在具备 Node.js >= 20 的环境中执行 `npm install && npm run build` 完成首次验证。
