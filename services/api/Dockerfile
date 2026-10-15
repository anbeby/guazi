# ==============================================================================
# 第十师瓜子油料数字化交易平台 · 自研产业平台后端（FastAPI）
# 多阶段构建：builder 编译依赖 -> runtime 精简运行
# ==============================================================================
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 依赖装到独立前缀，便于整体拷贝到运行阶段
RUN pip install --prefix=/install -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TZ=Asia/Shanghai \
    LANG=C.UTF-8 \
    LOCAL_STORAGE_DIR=/app/var/files

# 时区与运行期系统依赖（libpq 供 psycopg 使用；curl 用于容器健康检查）
RUN sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get update && apt-get install -y --no-install-recommends \
        libpq5 curl tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /install /usr/local

WORKDIR /app

# 应用代码
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini
COPY pytest.ini ./pytest.ini

# 本地降级存储目录（MinIO 不可用时使用，compose 会挂载宿主目录覆盖）
RUN mkdir -p /app/var/files && \
    useradd -r -u 10001 -m -s /sbin/nologin gzapp && \
    chown -R gzapp:gzapp /app
USER gzapp

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).status == 200 else 1)"

# 默认启动 API；worker 服务在 compose 中覆盖 command 为 python -m app.worker
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
