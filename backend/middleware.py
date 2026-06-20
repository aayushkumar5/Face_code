"""Small ASGI safeguards that do not require an external service."""

import logging
import hashlib
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class ProductionGuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_request_bytes: int, production: bool):
        super().__init__(app)
        self.max_request_bytes = max_request_bytes
        self.production = production
        self.logger = logging.getLogger("facecode.access")

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))[:128]
        content_length = request.headers.get("content-length")
        try:
            body_too_large = bool(content_length) and int(content_length) > self.max_request_bytes
        except ValueError:
            body_too_large = True
        if body_too_large:
            return JSONResponse(
                {"detail": "Request body is too large"},
                status_code=413,
                headers={"X-Request-ID": request_id},
            )

        started = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
        response.headers["Cache-Control"] = "no-store"
        if self.production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        self.logger.info(
            "request_complete method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            (time.monotonic() - started) * 1000,
            request_id,
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-process protection; the reverse proxy supplies the global limit."""

    def __init__(self, app):
        super().__init__(app)
        self.events = defaultdict(deque)
        self.lock = Lock()

    @staticmethod
    def _limit(path: str) -> int:
        if path in {"/api/execute-code", "/api/submit-solution"}:
            return 20
        if path in {"/api/analyze-emotion", "/api/activity"}:
            return 90
        return 180

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        now = time.monotonic()
        authorization = request.headers.get("authorization")
        client = (
            hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:24]
            if authorization
            else request.client.host if request.client else "unknown"
        )
        key = (client, request.url.path)
        with self.lock:
            if key not in self.events and len(self.events) >= 10_000:
                oldest_key = min(
                    self.events,
                    key=lambda item: self.events[item][-1] if self.events[item] else 0,
                )
                self.events.pop(oldest_key, None)
            bucket = self.events[key]
            while bucket and now - bucket[0] >= 60:
                bucket.popleft()
            if len(bucket) >= self._limit(request.url.path):
                return JSONResponse(
                    {"detail": "Rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            bucket.append(now)
        return await call_next(request)
