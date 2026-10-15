"""Build a Compose 1.29-compatible V1.1 candidate beside the active file.

The active Compose file is left untouched until a successful cutover. Only the
API/worker/frontend image tags and the two obsolete API static index mounts
change; all databases, networks, ports and other services stay identical.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import yaml


DEPLOY = Path(__file__).resolve().parents[1]
ACTIVE = DEPLOY / "docker-compose.production-v1.yml"
CANDIDATE = DEPLOY / "docker-compose.production-v11.yml"

active = yaml.safe_load(ACTIVE.read_text(encoding="utf-8"))
candidate = deepcopy(active)
services = candidate["services"]

assert active["version"] == "2.4", "Expected Docker Compose 1.29 production file"
assert services["api"]["container_name"] == "gz-api"
assert services["worker"]["container_name"] == "gz-worker"
assert services["admin-web"]["container_name"] == "gz-admin-web"

services["api"]["image"] = "gz-api:v1.1-rc1"
services["worker"]["image"] = "gz-api:v1.1-rc1"
services["admin-web"]["image"] = "gz-admin-web:v1.1-rc1"

obsolete = {
    "./conf/production-static/m/index.html:/app/app/static/m/index.html:ro",
    "./conf/production-static/console/index.html:/app/app/static/console/index.html:ro",
}
api_mounts = services["api"]["volumes"]
assert obsolete.issubset(set(api_mounts)), "Active API static mounts differ from reviewed baseline"
services["api"]["volumes"] = [mount for mount in api_mounts if mount not in obsolete]
assert "/data/guazi/uploads:/app/var/files" in services["api"]["volumes"]

output = (
    "# V1.1 candidate generated from docker-compose.production-v1.yml.\n"
    "# Use docker-compose -p guazi; do not edit the active file before cutover.\n"
    + yaml.safe_dump(candidate, allow_unicode=True, sort_keys=False)
)
if CANDIDATE.exists() and CANDIDATE.read_text(encoding="utf-8") != output:
    raise SystemExit(f"Candidate already exists with different content: {CANDIDATE}")
CANDIDATE.write_text(output, encoding="utf-8")
print(CANDIDATE)
