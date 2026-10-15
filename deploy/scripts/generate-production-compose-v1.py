"""Create a standalone Compose 1.29 file for the isolated DOcker host deployment.

Run on the Debian business host from /home/zhaopeng/guazi/deploy. The generated
file inherits the reviewed service definitions from docker-compose.yml and
only changes production mounts, port publication, and restart policies.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml


DEPLOY = Path(__file__).resolve().parents[1]
SOURCE = DEPLOY / "docker-compose.yml"
TARGET = DEPLOY / "docker-compose.production-v1.yml"

config = deepcopy(yaml.safe_load(SOURCE.read_text(encoding="utf-8")))
config["version"] = "2.4"  # docker-compose 1.29.2 on the existing Debian host.
config.pop("x-logging", None)
config.pop("x-api-environment", None)
config.pop("volumes", None)  # Production uses only /data/guazi bind mounts.
config["networks"]["gz-net"]["name"] = "guazi-net"

mounts = {
    "postgres": [
        "/data/guazi/postgres:/var/lib/postgresql/data",
        "./conf/postgres/init-production:/docker-entrypoint-initdb.d:ro",
        "./conf/postgres/init/02-readonly.sql:/opt/guazi/02-readonly.sql:ro",
    ],
    "redis": [
        "/data/guazi/redis:/data",
        "./conf/redis/redis.conf:/usr/local/etc/redis/redis.conf:ro",
    ],
    "minio": ["/data/guazi/minio:/data"],
    "elasticsearch": ["/data/guazi/elasticsearch:/usr/share/elasticsearch/data"],
    "odoo": [
        "/data/guazi/odoo:/var/lib/odoo",
        "/data/guazi/odoo-config:/etc/odoo",
        "../odoo/addons:/mnt/extra-addons:ro",
    ],
    "api": [
        "/data/guazi/uploads:/app/var/files",
        "./conf/production-static/m/index.html:/app/app/static/m/index.html:ro",
        "./conf/production-static/console/index.html:/app/app/static/console/index.html:ro",
    ],
    "superset": [
        "/data/guazi/superset:/app/superset_home",
        "./conf/superset/superset_config.py:/app/pythonpath/superset_config.py:ro",
    ],
    "superset-init": [
        "/data/guazi/superset:/app/superset_home",
        "./conf/superset/superset_config.py:/app/pythonpath/superset_config.py:ro",
    ],
    "nginx": [
        "./conf/nginx/nginx-production.conf:/etc/nginx/nginx.conf:ro",
        "/data/guazi/logs/nginx:/var/log/nginx",
        "./acceptance/site:/usr/share/nginx/html/report:ro",
    ],
}

oneshot = {"minio-init", "superset-init"}
for name, service in config["services"].items():
    service["restart"] = "no" if name in oneshot else "always"
    if name in mounts:
        service["volumes"] = mounts[name]
    service.pop("ports", None)  # No database, object store, Odoo, or API host ports.

# Compose 1.x cannot wait for a completed one-shot service. Run superset-init
# explicitly after PostgreSQL is healthy and before starting superset.
config["services"]["superset"]["depends_on"].pop("superset-init", None)
# The verified mc binary was exported from the local build host with this tag;
# the old digest-only reference would force a registry request on this host.
config["services"]["minio-init"]["image"] = "pgsty/mc:latest"
config["services"]["api"]["environment"].update(
    INITIAL_ADMIN_PASSWORD="${INITIAL_ADMIN_PASSWORD}",
    INITIAL_OPERATOR_PASSWORD="${INITIAL_OPERATOR_PASSWORD}",
)
config["services"]["odoo"]["environment"]["ODOO_LOGIN_PASSWORD"] = "${ODOO_LOGIN_PASSWORD}"
# Compose 1.x interprets shell command substitution in a healthcheck unless
# the dollar sign is escaped. The container must receive `resp=$(...)`.
es_test = config["services"]["elasticsearch"]["healthcheck"]["test"]
es_test[1] = es_test[1].replace("resp=$(cat <&3)", "resp=$$(cat <&3)")

config["services"]["nginx"]["ports"] = ["127.0.0.1:18083:80"]
config["services"]["nginx"]["container_name"] = "gz-nginx"
config["services"]["frpc"] = {
    "image": "alpine:3.20",
    "container_name": "gz-frpc",
    "restart": "always",
    "network_mode": "host",
    "volumes": [
        "./frp/frpc:/usr/local/bin/frpc:ro",
        "/data/guazi/frp/frpc.toml:/etc/frp/frpc.toml:ro",
    ],
    "command": ["/usr/local/bin/frpc", "-c", "/etc/frp/frpc.toml"],
    "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
}

TARGET.write_text(
    "# Generated from docker-compose.yml; do not edit by hand.\n"
    + yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
    encoding="utf-8",
)
print(TARGET)
