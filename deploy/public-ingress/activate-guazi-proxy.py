"""Activate only the guazi vhosts after syntax validation, with rollback."""
from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


sites = [
    (
        Path("/root/guazi.btszss.com-proxy-https.conf"),
        Path("/etc/nginx/conf.d/guazi.btszss.com-https.conf"),
    ),
    (
        Path("/root/guazi.btszss.com-redirect-http.conf"),
        Path("/etc/nginx/conf.d/guazi.btszss.com.conf"),
    ),
]
ops = Path("/etc/nginx/conf.d/value-ops-ops-domain.conf")
ops_hash = hashlib.sha256(ops.read_bytes()).hexdigest()
expected = "25f7f3cbcd673183a7f9bb06de935cac60c201c0eeb18d208de24f2cacfeeeed"
if ops_hash != expected:
    raise SystemExit("ops vhost changed since preflight; refusing guazi activation")

backup_dir = Path("/root/nginx-backups/guazi-vhost-before-proxy-20261013")
backup_dir.mkdir(parents=True, exist_ok=False)
backup_dir.chmod(0o700)
for source, target in sites:
    if not source.is_file() or not target.is_file():
        raise SystemExit(f"Missing source or active vhost: {source}, {target}")
    shutil.copy2(target, backup_dir / target.name)

def rollback() -> None:
    for _, target in sites:
        shutil.copy2(backup_dir / target.name, target)
    subprocess.run(["nginx", "-t"], check=True)
    subprocess.run(["/etc/nginx/reload-nginx.sh"], check=True)


try:
    for source, target in sites:
        shutil.copy2(source, target)
    subprocess.run(["nginx", "-t"], check=True)
    subprocess.run(["/etc/nginx/reload-nginx.sh"], check=True)
except Exception:
    rollback()
    raise

assert hashlib.sha256(ops.read_bytes()).hexdigest() == expected
print("Activated guazi HTTP redirect and HTTPS FRP proxy; ops vhost hash unchanged")
print(f"Guazi vhost backup: {backup_dir}")
