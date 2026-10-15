"""Add only the guazi FRP remote port, preserving existing tunnel ranges."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


config = Path("/etc/frp/frps.toml")
backup = Path("/root/frp-backups/frps-before-guazi-20261013.toml")
original = config.read_text(encoding="utf-8")
if re.search(r"\bstart\s*=\s*18083\b", original):
    raise SystemExit("Port 18083 already allowed; no change")
pattern = r"(\{\s*start\s*=\s*18082,\s*end\s*=\s*18082\s*\})(\s*\n\])"
updated, count = re.subn(
    pattern,
    r"\1,\n  { start = 18083, end = 18083 }\2",
    original,
)
if count != 1:
    raise SystemExit(f"Expected one existing 18082 entry; found {count}")
backup.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
if backup.exists():
    raise SystemExit(f"Refusing to replace backup {backup}")
shutil.copy2(config, backup)
backup.chmod(0o600)
config.write_text(updated, encoding="utf-8")
result = subprocess.run(
    ["/usr/local/bin/frps", "verify", "-c", str(config)],
    capture_output=True,
    text=True,
)
if result.returncode:
    shutil.copy2(backup, config)
    raise SystemExit(f"FRP validation failed; restored original: {result.stderr}")
print("FRP config verified: existing ranges preserved; added 18083 only")
print(f"Backup: {backup}")
