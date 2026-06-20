"""Signed anonymous session credentials with no external dependency."""

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Optional


class SessionTokenError(ValueError):
    pass


class SessionSigner:
    def __init__(self, secret_key: str, ttl_seconds: int):
        self.secret = secret_key.encode("utf-8")
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def issue(self) -> tuple[str, str, int]:
        session_id = f"session_{secrets.token_urlsafe(24)}"
        expires_at = int(time.time()) + self.ttl_seconds
        payload = self._encode(
            json.dumps({"sid": session_id, "exp": expires_at}, separators=(",", ":")).encode()
        )
        signature = self._encode(
            hmac.new(self.secret, payload.encode("ascii"), hashlib.sha256).digest()
        )
        return session_id, f"{payload}.{signature}", expires_at

    def verify(self, token: str, expected_session_id: Optional[str] = None) -> str:
        try:
            payload, signature = token.split(".", 1)
            expected_signature = self._encode(
                hmac.new(self.secret, payload.encode("ascii"), hashlib.sha256).digest()
            )
            if not hmac.compare_digest(signature, expected_signature):
                raise SessionTokenError("Invalid session credential")
            data = json.loads(self._decode(payload))
            session_id = str(data["sid"])
            if int(data["exp"]) < int(time.time()):
                raise SessionTokenError("Session credential has expired")
            if expected_session_id and session_id != expected_session_id:
                raise SessionTokenError("Session credential mismatch")
            return session_id
        except SessionTokenError:
            raise
        except Exception as exc:
            raise SessionTokenError("Invalid session credential") from exc
