# -*- coding: utf-8 -*-
"""安全工具：密码散列（PBKDF2-SHA256）与 JWT(HS256)。

刻意只使用 Python 标准库实现，避免 passlib/bcrypt/pyjwt 的版本兼容问题，
同时满足等保对密码存储强度的要求（PBKDF2-SHA256，26 万轮，16 字节随机盐）。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional

from app.core.config import settings

HASH_ALGORITHM = "pbkdf2_sha256"


class TokenError(Exception):
    """令牌非法或已过期。"""


# --------------------------------------------------------------------------- 密码


def hash_password(password: str, rounds: Optional[int] = None) -> str:
    if not password:
        raise ValueError("密码不能为空")
    rounds = rounds or settings.PASSWORD_PBKDF2_ROUNDS
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), rounds)
    return f"{HASH_ALGORITHM}${rounds}${salt}${digest.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    if not password or not hashed:
        return False
    try:
        algorithm, rounds_raw, salt, digest_hex = hashed.split("$", 3)
        if algorithm != HASH_ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(rounds_raw)
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def password_strength_error(password: str) -> Optional[str]:
    """返回错误描述，None 表示通过。"""
    if len(password or "") < 8:
        return "密码长度不得少于 8 位"
    if password.isdigit() or password.isalpha():
        return "密码需同时包含字母与数字"
    return None


# --------------------------------------------------------------------------- JWT


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _sign(message: bytes) -> str:
    signature = hmac.new(settings.JWT_SECRET.encode("utf-8"), message, hashlib.sha256).digest()
    return _b64url_encode(signature)


def create_token(
    subject: str,
    token_type: str = "access",
    expires_in: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """签发令牌。token_type ∈ {access, refresh}。"""
    if expires_in is None:
        expires_in = (
            settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            if token_type == "access"
            else settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
        )
    issued_at = int(time.time())
    payload: Dict[str, Any] = {
        "sub": str(subject),
        "typ": token_type,
        "iat": issued_at,
        "exp": issued_at + int(expires_in),
        "jti": secrets.token_hex(12),
        "iss": "gz-platform",
    }
    if extra:
        for key, value in extra.items():
            if key not in payload:
                payload[key] = value
    header = {"alg": settings.JWT_ALGORITHM, "typ": "JWT"}
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")),
    ]
    signing_input = ".".join(segments).encode("ascii")
    segments.append(_sign(signing_input))
    return ".".join(segments)


def decode_token(token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
    if not token or token.count(".") != 2:
        raise TokenError("令牌格式非法")
    header_seg, payload_seg, signature_seg = token.split(".")
    signing_input = f"{header_seg}.{payload_seg}".encode("ascii")
    if not hmac.compare_digest(_sign(signing_input), signature_seg):
        raise TokenError("令牌签名校验失败")
    try:
        header = json.loads(_b64url_decode(header_seg))
        payload = json.loads(_b64url_decode(payload_seg))
    except (ValueError, TypeError) as exc:
        raise TokenError("令牌内容无法解析") from exc
    if header.get("alg") != settings.JWT_ALGORITHM:
        raise TokenError("不支持的签名算法")
    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("令牌已过期")
    if expected_type and payload.get("typ") != expected_type:
        raise TokenError("令牌类型不匹配")
    return payload


def token_remaining_seconds(payload: Dict[str, Any]) -> int:
    return max(0, int(payload.get("exp", 0)) - int(time.time()))


# --------------------------------------------------------------------------- 集成签名


def sign_integration(timestamp: str, raw_body: bytes) -> str:
    message = f"{timestamp}.".encode("utf-8") + raw_body
    return hmac.new(settings.INTEGRATION_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_integration_signature(timestamp: str, raw_body: bytes, signature: str) -> bool:
    try:
        if abs(int(time.time()) - int(timestamp)) > settings.INTEGRATION_SIGN_TOLERANCE:
            return False
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(sign_integration(timestamp, raw_body), signature or "")
