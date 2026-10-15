"""Create a separate guazi FRP client without editing the value-ops client."""
from __future__ import annotations

import json
import os
import shutil
import tomllib
from pathlib import Path


deploy = Path(__file__).resolve().parents[1]
existing = Path("/home/zhaopeng/tunyun-value-ops/frp")
source_config = existing / "value-ops-frpc.toml"
source_binary = existing / "frpc"
target_binary = deploy / "frp" / "frpc"
target_config = Path("/data/guazi/frp/frpc.toml")

if target_config.exists():
    raise SystemExit(f"Refusing to overwrite {target_config}")
with source_config.open("rb") as stream:
    current = tomllib.load(stream)
token = current["auth"]["token"]
if not token or not source_binary.is_file():
    raise SystemExit("Existing FRP client configuration or binary is incomplete")

target_binary.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source_binary, target_binary)
target_binary.chmod(0o755)

content = (
    f"serverAddr = {json.dumps(current['serverAddr'])}\n"
    f"serverPort = {int(current['serverPort'])}\n"
    'user = "guazi-zhaopeng"\n'
    'auth.method = "token"\n'
    f"auth.token = {json.dumps(token)}\n"
    'transport.tls.enable = true\n'
    '[[proxies]]\n'
    'name = "guazi-web"\n'
    'type = "tcp"\n'
    'localIP = "127.0.0.1"\n'
    'localPort = 18083\n'
    'remotePort = 18083\n'
)
fd = os.open(target_config, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w", encoding="utf-8") as stream:
    stream.write(content)
print("Created independent guazi FRP binary and private configuration; token hidden")
