#!/usr/bin/env python3
"""Repeatable, guarded releases for the existing guazi Compose project.

Run on 192.168.3.5 as zhaopeng.  This tool never invokes ``compose down`` and
never touches another Compose project.  See docs/瓜子平台后续升级标准流程.md.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
from datetime import datetime
from pathlib import Path

import yaml


BASE = Path("/home/zhaopeng/guazi")
DEPLOY = BASE / "deploy"
DATA = Path("/data/guazi")
BACKUPS = DATA / "backups"
ACTIVE = DEPLOY / "docker-compose.production-v1.yml"
GATEWAY = "http://127.0.0.1:18083"
REQUIRED = {
    "api": "gz-api",
    "worker": "gz-worker",
    "admin-web": "gz-admin-web",
    "nginx": "gz-nginx",
    "postgres": "gz-postgres",
    "redis": "gz-redis",
    "minio": "gz-minio",
    "frpc": "gz-frpc",
}
HEALTHY = ("api", "worker", "admin-web", "nginx", "postgres", "redis", "minio")
IMAGE_SERVICES = ("api", "worker", "admin-web")
URLS = ("/ready", "/", "/login", "/supply", "/procurement")


def say(message: str) -> None:
    print(f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] {message}", flush=True)


def run(*args: str, input_file: Path | None = None, output_file: Path | None = None) -> str:
    with (input_file.open("rb") if input_file else open(os.devnull, "rb")) as source:
        if output_file:
            with output_file.open("wb") as target:
                subprocess.run(args, cwd=DEPLOY, stdin=source, stdout=target, check=True)
            return ""
        result = subprocess.run(args, cwd=DEPLOY, stdin=source, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=False, text=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(args[:3])} failed ({result.returncode}): {result.stderr[-600:]}")
    return result.stdout.strip()


def dc(compose: Path, *args: str) -> str:
    return run("docker-compose", "-p", "guazi", "-f", str(compose), *args)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)


def manifest(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"release_id", "base_images", "target_images", "db_from", "db_to"}:
        raise ValueError("Plan must contain exactly release_id, base_images, target_images, db_from, db_to")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", data["release_id"]):
        raise ValueError("Invalid release_id")
    for key in ("base_images", "target_images"):
        if set(data[key]) != set(IMAGE_SERVICES):
            raise ValueError(f"{key} must name api, worker, admin-web")
        for service, image in data[key].items():
            prefix = "gz-admin-web:" if service == "admin-web" else "gz-api:"
            if not isinstance(image, str) or not image.startswith(prefix) or image.endswith(":latest"):
                raise ValueError(f"{service} must use an immutable named guazi image tag")
        if data[key]["api"] != data[key]["worker"]:
            raise ValueError("API and worker must use the same image")
    for key in ("db_from", "db_to"):
        if not isinstance(data[key], str) or not re.fullmatch(r"[a-zA-Z0-9_]{3,80}", data[key]):
            raise ValueError(f"Invalid {key}")
    if data["db_from"] != data["db_to"] and data["base_images"]["api"] == data["target_images"]["api"]:
        raise ValueError("A database migration requires a new API image")
    return data


def schema_version() -> str:
    return run("docker", "exec", "gz-postgres", "psql", "-U", "gz", "-d", "gz_platform",
               "-Atc", "SELECT version_num FROM gz.alembic_version")


def inspect(name: str, fmt: str) -> str:
    return run("docker", "inspect", "-f", fmt, name)


def health(name: str) -> str:
    return inspect(name, "{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}")


def wait_healthy(names: tuple[str, ...], timeout: int = 180) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if all(health(REQUIRED[name]) == "healthy" for name in names):
            return
        time.sleep(3)
    raise RuntimeError(f"Health timeout: {', '.join(names)}")


def check_urls() -> None:
    for path in URLS:
        status = run("curl", "-sS", "--connect-timeout", "5", "--max-time", "12",
                     "-o", os.devnull, "-w", "%{http_code}", GATEWAY + path)
        if status != "200":
            raise RuntimeError(f"Internal {path} returned HTTP {status}")


def image_id(image: str) -> str:
    return run("docker", "image", "inspect", "-f", "{{.Id}}", image)


def checked_candidate(plan: dict) -> Path:
    original = yaml.safe_load(ACTIVE.read_text(encoding="utf-8"))
    if original.get("version") != "2.4":
        raise RuntimeError("Expected Compose 1.29-compatible version 2.4")
    services = original["services"]
    for service, container in REQUIRED.items():
        if services[service].get("container_name") != container:
            raise RuntimeError(f"Unexpected container name for {service}")
        if services[service].get("restart") != "always":
            raise RuntimeError(f"{service} must retain restart: always")
    if services["nginx"].get("ports") != ["127.0.0.1:18083:80"]:
        raise RuntimeError("Guazi gateway must remain on 127.0.0.1:18083")
    for service, mount in (("postgres", "/data/guazi/postgres:"),
                           ("minio", "/data/guazi/minio:"),
                           ("api", "/data/guazi/uploads:")):
        if not any(str(value).startswith(mount) for value in services[service].get("volumes", [])):
            raise RuntimeError(f"{service} persistent volume is outside /data/guazi")
    for service in IMAGE_SERVICES:
        if services[service].get("image") != plan["base_images"][service]:
            raise RuntimeError(f"Stale plan: {service} active image changed")
        services[service]["image"] = plan["target_images"][service]
    candidate = DEPLOY / f"docker-compose.candidate-{plan['release_id']}.yml"
    rendered = yaml.safe_dump(original, allow_unicode=True, sort_keys=False)
    if candidate.exists() and candidate.read_text(encoding="utf-8") != rendered:
        raise RuntimeError(f"Candidate exists with different content: {candidate}")
    if not candidate.exists():
        candidate.write_text(rendered, encoding="utf-8")
    dc(candidate, "config", "-q")
    return candidate


def preflight(plan: dict) -> tuple[Path, dict]:
    if not DEPLOY.is_dir() or not DATA.is_dir() or not BACKUPS.is_dir():
        raise RuntimeError("Expected guazi deployment and data directories are missing")
    if run("findmnt", "-no", "TARGET", "-T", str(DATA)) != "/data":
        raise RuntimeError("/data/guazi is not on the separate /data mount")
    if shutil.disk_usage(DATA).free < 5 * 1024**3:
        raise RuntimeError("Less than 5 GiB free on the guazi data disk")
    env_lines = (DEPLOY / ".env").read_text(encoding="utf-8").splitlines()
    if env_lines.count("COMPOSE_PROJECT_NAME=guazi") != 1:
        raise RuntimeError("COMPOSE_PROJECT_NAME must be exactly guazi")
    dc(ACTIVE, "config", "-q")
    candidate = checked_candidate(plan)
    if schema_version() != plan["db_from"]:
        raise RuntimeError("Live database revision differs from the release plan")
    if health("tunyun-value-ops-nginx") != "healthy":
        raise RuntimeError("Existing value-ops gateway must be healthy before release")
    value_ops_id = inspect("tunyun-value-ops-nginx", "{{.Id}}")
    for service, container in REQUIRED.items():
        if inspect(container, '{{index .Config.Labels "com.docker.compose.project"}}') != "guazi":
            raise RuntimeError(f"{container} belongs to another Compose project")
        if service in HEALTHY and health(container) != "healthy":
            raise RuntimeError(f"{container} is not healthy")
    binding = json.loads(inspect("gz-nginx", "{{json .HostConfig.PortBindings}}"))
    if binding.get("80/tcp") != [{"HostIp": "127.0.0.1", "HostPort": "18083"}]:
        raise RuntimeError("Live guazi port differs from 127.0.0.1:18083")
    if inspect("tunyun-value-ops-nginx", "{{.State.Status}}") != "running":
        raise RuntimeError("Value-ops gateway is not running")
    value_ops_binding = json.loads(inspect("tunyun-value-ops-nginx", "{{json .HostConfig.PortBindings}}"))
    if value_ops_binding.get("80/tcp") != [{"HostIp": "127.0.0.1", "HostPort": "18080"}]:
        raise RuntimeError("Value-ops 18080 binding changed; stop before releasing guazi")
    for service in IMAGE_SERVICES:
        if inspect(REQUIRED[service], "{{.Image}}") != image_id(plan["base_images"][service]):
            raise RuntimeError(f"Running {service} image differs from its active Compose tag")
    for image in set(plan["target_images"].values()):
        image_id(image)
        if inspect(image, "{{.Architecture}}") != "amd64":
            raise RuntimeError(f"Target image is not amd64: {image}")
    run("docker", "run", "--rm", "--network", "none", "--entrypoint", "alembic",
        plan["target_images"]["api"], "show", plan["db_to"])
    check_urls()
    say(f"Preflight passed; project=guazi, port=18083, DB={plan['db_from']}")
    return candidate, {"value_ops_id": value_ops_id,
                       "target_image_ids": {s: image_id(i) for s, i in plan["target_images"].items()}}


def dump_db(database: str, destination: Path) -> None:
    partial = destination.with_suffix(".dump.part")
    run("docker", "exec", "gz-postgres", "pg_dump", "-U", "gz", "-Fc", database,
        output_file=partial)
    run("docker", "exec", "-i", "gz-postgres", "pg_restore", "-l", input_file=partial)
    partial.replace(destination)
    (destination.parent / "SHA256SUMS.txt").open("a", encoding="utf-8").write(
        f"{digest(destination)}  {destination.name}\n")


def save_uploads(destination: Path) -> None:
    with tarfile.open(destination, "w") as archive:
        archive.add(DATA / "uploads", arcname="uploads")
    with tarfile.open(destination, "r") as archive:
        if not archive.getmembers():
            raise RuntimeError("Uploads archive is empty")
    (destination.parent / "SHA256SUMS.txt").open("a", encoding="utf-8").write(
        f"{digest(destination)}  {destination.name}\n")


def state(checkpoint: Path, phase: str, **extra: object) -> None:
    path = checkpoint / "state.json"
    current = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    current.update(phase=phase, updated_at=datetime.now().astimezone().isoformat(), **extra)
    save_json(path, current)
    say(f"{phase}: {checkpoint}")


def verify_other_platform(expected_id: str) -> None:
    if inspect("tunyun-value-ops-nginx", "{{.Id}}") != expected_id:
        raise RuntimeError("Value-ops gateway container changed during guazi release")
    if health("tunyun-value-ops-nginx") != "healthy":
        raise RuntimeError("Value-ops gateway health changed during guazi release")


def restore_frpc(checkpoint: Path, compose: Path) -> None:
    details = json.loads((checkpoint / "frpc.json").read_text(encoding="utf-8"))
    if details["status"] == "running":
        dc(compose, "up", "-d", "--no-build", "--no-deps", "frpc")
        if inspect("gz-frpc", "{{.State.Status}}") != "running":
            raise RuntimeError("gz-frpc failed to start")
        started = inspect("gz-frpc", "{{.State.StartedAt}}")
        for _ in range(15):
            logs = subprocess.run(("docker", "logs", "--since", started, "gz-frpc"),
                                  cwd=DEPLOY, stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT, text=True, check=False)
            if logs.returncode == 0 and "start proxy success" in logs.stdout:
                break
            time.sleep(2)
        else:
            raise RuntimeError("gz-frpc is running but proxy startup was not confirmed")
    run("docker", "update", "--restart=" + details["restart"], "gz-frpc")


def restore_same_schema(checkpoint: Path) -> None:
    say("Restoring prior images and Compose; database schema is unchanged")
    dc(ACTIVE, "stop", "frpc", "nginx", "worker", "api", "admin-web")
    run("docker", "update", "--restart=no", "gz-frpc")
    old_plan = json.loads((checkpoint / "plan.json").read_text(encoding="utf-8"))
    if schema_version() != old_plan["db_from"]:
        raise RuntimeError("Database revision changed; refusing an image-only rollback")
    old_containers = json.loads((checkpoint / "old-containers.json").read_text(encoding="utf-8"))
    for service in IMAGE_SERVICES:
        run("docker", "image", "tag", old_containers[service]["image_id"],
            old_plan["base_images"][service])
    shutil.copy2(checkpoint / "active-compose.yml", ACTIVE)
    dc(ACTIVE, "config", "-q")
    dc(ACTIVE, "up", "-d", "--no-build", "--no-deps", "--force-recreate",
       "api", "worker", "admin-web")
    wait_healthy(("api", "worker", "admin-web"))
    dc(ACTIVE, "up", "-d", "--no-build", "--no-deps", "--force-recreate", "nginx")
    wait_healthy(("nginx",))
    check_urls()
    restore_frpc(checkpoint, ACTIVE)
    previous = json.loads((checkpoint / "preflight.json").read_text(encoding="utf-8"))
    verify_other_platform(previous["value_ops_id"])
    state(checkpoint, "rolled-back")


def lock() -> object:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    handle = (BACKUPS / ".guazi-release.lock").open("a+")
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    return handle


def apply(plan: dict) -> None:
    handle = lock()
    candidate, baseline = preflight(plan)
    if plan["base_images"] == plan["target_images"] and plan["db_from"] == plan["db_to"]:
        raise RuntimeError("No version change; refusing to recreate the current stack")
    checkpoint = BACKUPS / f"release-{plan['release_id']}-{datetime.now():%Y%m%d-%H%M%S}"
    checkpoint.mkdir(mode=0o700)
    save_json(checkpoint / "plan.json", plan)
    save_json(checkpoint / "preflight.json", baseline)
    shutil.copy2(ACTIVE, checkpoint / "active-compose.yml")
    shutil.copy2(DEPLOY / ".env", checkpoint / ".env")
    (checkpoint / ".env").chmod(0o600)
    save_json(checkpoint / "old-containers.json", {
        service: {"id": inspect(container, "{{.Id}}"),
                  "image_id": inspect(container, "{{.Image}}")}
        for service, container in REQUIRED.items()
    })
    save_json(checkpoint / "frpc.json", {
        "status": inspect("gz-frpc", "{{.State.Status}}"),
        "restart": inspect("gz-frpc", "{{.HostConfig.RestartPolicy.Name}}"),
    })
    (checkpoint / "db-before.txt").write_text(schema_version() + "\n", encoding="utf-8")
    state(checkpoint, "backing-up")
    stopped = False
    migration_started = False
    try:
        for database in ("gz_platform", "gz_odoo", "superset"):
            dump_db(database, checkpoint / f"{database}.dump")
        for image in set(plan["base_images"].values()):
            tag = f"{image.split(':')[0]}:pre-{plan['release_id']}"
            run("docker", "image", "tag", image_id(image), tag)
        state(checkpoint, "backup-complete")

        stopped = True
        dc(ACTIVE, "stop", "frpc")
        run("docker", "update", "--restart=no", "gz-frpc")
        dc(ACTIVE, "stop", "nginx", "worker", "api", "admin-web")
        state(checkpoint, "old-services-stopped")
        dump_db("gz_platform", checkpoint / "gz_platform-final.dump")
        save_uploads(checkpoint / "uploads-final.tar")

        if plan["db_from"] != plan["db_to"]:
            migration_started = True
            state(checkpoint, "migration-started")
            dc(candidate, "run", "--rm", "--no-deps", "api", "alembic", "upgrade", plan["db_to"])
            if schema_version() != plan["db_to"]:
                raise RuntimeError("Migration did not reach planned revision")
        else:
            if schema_version() != plan["db_from"]:
                raise RuntimeError("Database revision changed during release")
        state(checkpoint, "migration-complete")
        for service, image in plan["target_images"].items():
            if image_id(image) != baseline["target_image_ids"][service]:
                raise RuntimeError(f"Target image tag changed during release: {service}")

        dc(candidate, "up", "-d", "--no-build", "--no-deps", "--force-recreate",
           "api", "worker", "admin-web")
        wait_healthy(("api", "worker", "admin-web"))
        dc(candidate, "up", "-d", "--no-build", "--no-deps", "--force-recreate", "nginx")
        wait_healthy(("nginx",))
        check_urls()
        verify_other_platform(baseline["value_ops_id"])
        state(checkpoint, "internal-healthy")

        # Promote only after all internal checks pass. Keep the candidate file.
        promoted = ACTIVE.with_suffix(".yml.part")
        shutil.copy2(candidate, promoted)
        promoted.replace(ACTIVE)
        restore_frpc(checkpoint, ACTIVE)
        state(checkpoint, "released")
        say("Release complete. Public HTTP/HTTPS checks remain separate gates.")
    except (Exception, KeyboardInterrupt):
        if stopped and not migration_started:
            try:
                restore_same_schema(checkpoint)
            except Exception as rollback_error:
                state(checkpoint, "manual-review-required", reason=str(rollback_error))
                say("Automatic rollback failed. Keep guazi gateway isolated.")
        elif stopped:
            try:
                dc(candidate, "stop", "frpc", "nginx", "worker", "api", "admin-web")
            except Exception as stop_error:
                say(f"Additional stop error: {stop_error}")
            state(checkpoint, "manual-review-required",
                  reason="Migration began; compare current database and final backup before restoring")
            say("Database migration may have written data. FRP and gateway remain stopped.")
        else:
            state(checkpoint, "failed-before-stop")
        raise
    finally:
        handle.close()


def rollback(checkpoint: Path) -> None:
    handle = lock()
    try:
        checkpoint = checkpoint.resolve(strict=True)
        if checkpoint.parent != BACKUPS.resolve():
            raise ValueError("Rollback checkpoint must be a direct child of /data/guazi/backups")
        plan = json.loads((checkpoint / "plan.json").read_text(encoding="utf-8"))
        if plan["db_from"] != plan["db_to"]:
            raise RuntimeError("Schema changed; inspect writes and restore the database separately")
        expected = json.loads((checkpoint / "preflight.json").read_text(encoding="utf-8"))
        for service, image in plan["target_images"].items():
            if inspect(REQUIRED[service], "{{.Image}}") != expected["target_image_ids"][service]:
                raise RuntimeError("Running image differs from this checkpoint; refusing stale rollback")
        restore_same_schema(checkpoint)
    finally:
        handle.close()


def main() -> None:
    os.umask(0o077)
    def interrupted(signum: int, _frame: object) -> None:
        raise RuntimeError(f"Release interrupted by signal {signum}")
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "apply"):
        command = sub.add_parser(name)
        command.add_argument("plan", type=Path)
        if name == "apply":
            command.add_argument("--execute", action="store_true", required=True)
    command = sub.add_parser("rollback")
    command.add_argument("checkpoint", type=Path)
    command.add_argument("--execute", action="store_true", required=True)
    args = parser.parse_args()
    if args.command == "check":
        preflight(manifest(args.plan))
    elif args.command == "apply":
        if not args.execute:
            raise ValueError("Explicit --execute is required")
        apply(manifest(args.plan))
    else:
        if not args.execute:
            raise ValueError("Explicit --execute is required")
        rollback(args.checkpoint)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt,
            subprocess.CalledProcessError) as error:
        say(f"ERROR: {error}")
        sys.exit(1)
