import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from nova_guard_api.core.config import get_settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int) -> None:
        super().__init__(app)
        self.requests_per_minute = max(1, requests_per_minute)
        self._windows: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next) -> Response:
        client = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - 60.0
        bucket = self._windows[client]
        bucket[:] = [t for t in bucket if t > window_start]
        limit = self.requests_per_minute
        reset = int(now + 60)

        if len(bucket) >= limit:
            from fastapi.responses import JSONResponse

            from nova_guard_api.core.errors import problem

            return JSONResponse(
                status_code=429,
                content=problem(
                    type_="https://nova-guard.dev/problems/rate-limit",
                    title="Too Many Requests",
                    status_code=429,
                    detail="Rate limit exceeded",
                    instance=str(request.url),
                ),
                media_type="application/problem+json",
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset),
                },
            )

        bucket.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - len(bucket)))
        response.headers["X-RateLimit-Reset"] = str(reset)
        return response


def rate_limit_middleware_factory():
    s = get_settings()
    return lambda app: RateLimitMiddleware(app, s.rate_limit_per_minute)
