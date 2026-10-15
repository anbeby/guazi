# ---------- 第一阶段：构建 ----------
FROM node:20-alpine AS builder

WORKDIR /app

# 依赖层（利用 docker 缓存）
COPY package.json ./
RUN npm config set registry https://registry.npmmirror.com \
    && npm install --no-audit --no-fund

# 源码层
COPY . .
RUN npm run build:only

# ---------- 第二阶段：运行 ----------
FROM nginx:alpine AS runner

# 站点配置（history 模式 fallback + /api 反向代理到 api:8000）
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
