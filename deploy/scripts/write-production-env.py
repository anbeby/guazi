"""Write a new private .env for the isolated guazi Compose deployment.

Run once on the business host. Existing credentials are never overwritten and
the generated values are never printed to stdout.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path


target = Path(__file__).resolve().parents[1] / ".env"
if target.exists():
    raise SystemExit(f"Refusing to replace existing {target}")

def secret() -> str:
    return secrets.token_hex(24)


pg = secret()
ro = secret()
redis = secret()
minio = secret()
values = {
    "TZ": "Asia/Shanghai",
    "APP_ENV": "production",
    "DEBUG": "false",
    "POSTGRES_USER": "gz",
    "POSTGRES_PASSWORD": pg,
    "POSTGRES_DB": "gz_platform",
    "POSTGRES_READONLY_USER": "gz_ro",
    "POSTGRES_READONLY_PASSWORD": ro,
    "ODOO_DB": "gz_odoo",
    "PLATFORM_DB": "gz_platform",
    "SUPERSET_DB": "superset",
    "REDIS_PASSWORD": redis,
    "REDIS_URL": f"redis://:{redis}@redis:6379/0",
    "MINIO_ROOT_USER": "gzminio",
    "MINIO_ROOT_PASSWORD": minio,
    "MINIO_BUCKET": "gz-product",
    "MINIO_ENDPOINT": "minio:9000",
    "MINIO_SECURE": "false",
    "ELASTICSEARCH_URL": "http://elasticsearch:9200",
    "ES_JAVA_OPTS": "-Xms1g -Xmx1g",
    "ODOO_ADMIN_PASSWD": secret(),
    "ODOO_ADMIN_USER": "admin",
    "ODOO_LOGIN_PASSWORD": secret(),
    "ODOO_URL": "http://odoo:8069",
    "ODOO_LIST_DB": "False",
    "ODOO_WITHOUT_DEMO": "all",
    "ODOO_WORKERS": "2",
    "ODOO_MAX_CRON_THREADS": "2",
    "API_SECRET_KEY": secret(),
    "JWT_SECRET": secret(),
    "INTEGRATION_SECRET": secret(),
    "DATABASE_URL": f"postgresql+psycopg://gz:{pg}@postgres:5432/gz_platform",
    "INITIAL_ADMIN_PASSWORD": secret(),
    "INITIAL_OPERATOR_PASSWORD": secret(),
    "SUPERSET_SECRET_KEY": secret(),
    "SUPERSET_ADMIN_USERNAME": "admin",
    "SUPERSET_ADMIN_PASSWORD": secret(),
    "SUPERSET_ADMIN_EMAIL": "admin@btszss.com",
    "SUPERSET_ADMIN_FIRSTNAME": "平台",
    "SUPERSET_ADMIN_LASTNAME": "管理员",
    "SUPERSET_DATABASE_URI": f"postgresql+psycopg2://gz:{pg}@postgres:5432/superset",
    "SUPERSET_PLATFORM_URI": f"postgresql://gz_ro:{ro}@postgres:5432/gz_platform",
    "SUPERSET_ODOO_URI": f"postgresql://gz_ro:{ro}@postgres:5432/gz_odoo",
    "CORS_ORIGINS": "https://guazi.btszss.com",
}

descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(descriptor, "w", encoding="utf-8") as output:
    output.write("# Generated for guazi.btszss.com; keep this file private.\n")
    for key, value in values.items():
        output.write(f"{key}={value}\n")
print(f"Created {target} with mode 0600 ({len(values)} keys; values hidden)")
