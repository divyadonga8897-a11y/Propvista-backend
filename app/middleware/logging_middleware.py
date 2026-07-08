"""
logging_middleware.py — Request/response logging middleware for FastAPI.
Logs method, path, status code, and processing time for every request.
"""
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from app.utils.logging import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs:
    - Incoming: method + path + client IP
    - Outgoing: status code + duration
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.time()

        # Log incoming request
        logger.info(
            f"[{request_id}] ➡  {request.method} {request.url.path} "
            f"— client: {request.client.host if request.client else 'unknown'}"
        )

        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = round((time.time() - start_time) * 1000)
            logger.error(
                f"[{request_id}] ❌ {request.method} {request.url.path} "
                f"— EXCEPTION after {duration_ms}ms: {exc}"
            )
            raise

        duration_ms = round((time.time() - start_time) * 1000)
        status = response.status_code
        emoji = "✅" if status < 400 else ("⚠️ " if status < 500 else "❌")

        logger.info(
            f"[{request_id}] {emoji} {request.method} {request.url.path} "
            f"→ {status} ({duration_ms}ms)"
        )

        # Add request ID header for debugging
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = str(duration_ms)

        return response
