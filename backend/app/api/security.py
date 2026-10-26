"""HTTP-level protections: rate limiting, a request-body size cap, and security headers.

Written as plain ASGI middleware (no extra dependencies) so each one is easy to read and test.

Limits are kept in memory, which is right for a single server instance (the free Render
tier). With several instances you'd move the counters to a shared store such as Redis.
"""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Awaitable, Callable

Scope = dict
Message = dict
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

MAX_BODY_BYTES = 64 * 1024  # the largest legitimate request (a full league for /moves) is a few KB


@dataclass(frozen=True)
class RateRule:
    path_prefix: str  # "" matches every path
    limit: int
    window_seconds: float


# Most specific first. Endpoints that call ESPN or Sleeper get tighter limits.
DEFAULT_RULES = (
    RateRule("/leagues", 10, 60),
    RateRule("/moves", 30, 60),
    RateRule("", 120, 60),
)


async def _send_json(send: Send, status: int, payload: dict, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
            + (headers or []),
        }
    )
    await send({"type": "http.response.body", "body": body})


class RateLimitMiddleware:
    """Sliding-window limit per client IP and rule. Over the limit -> 429 with Retry-After."""

    def __init__(self, app: ASGIApp, rules: tuple[RateRule, ...] = DEFAULT_RULES, clock=time.monotonic) -> None:
        self.app = app
        self.rules = rules
        self.clock = clock
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def _check(self, client: str, path: str) -> float | None:
        """Record a hit; return seconds to wait if the client is over the limit, else None."""
        rule = next(r for r in self.rules if path.startswith(r.path_prefix))
        now = self.clock()
        hits = self._hits.setdefault((client, rule.path_prefix), deque())
        while hits and now - hits[0] >= rule.window_seconds:
            hits.popleft()
        if len(hits) >= rule.limit:
            return rule.window_seconds - (now - hits[0])
        hits.append(now)
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] == "OPTIONS":  # CORS preflights don't count
            return await self.app(scope, receive, send)
        client = (scope.get("client") or ("unknown", 0))[0]
        wait = self._check(client, scope["path"])
        if wait is not None:
            retry = str(max(1, int(wait + 0.999)))
            return await _send_json(
                send,
                429,
                {"error": {"code": "rate_limited", "message": f"Too many requests. Try again in {retry} seconds."}},
                [(b"retry-after", retry.encode())],
            )
        await self.app(scope, receive, send)


class BodySizeLimitMiddleware:
    """Refuse request bodies over max_bytes with 413, whether or not Content-Length is sent.

    The body is read here, up to the limit, and then handed to the app in one piece. (Raising
    from inside the app's own body reading doesn't work: FastAPI turns it into a vague 400.)
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            return await self.app(scope, receive, send)
        too_large = {"error": {"code": "body_too_large", "message": "Request body is too large."}}
        declared = dict(scope.get("headers") or []).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.max_bytes:
            return await _send_json(send, 413, too_large)

        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":  # client disconnected
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self.max_bytes:
                return await _send_json(send, 413, too_large)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break

        body_sent = False

        async def replay() -> Message:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()  # after the body, pass through (e.g. disconnect notices)

        await self.app(scope, replay, send)


# Swagger/ReDoc pages load their own scripts and styles, so they get the headers below but not the strict CSP.
DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")

BASE_HEADERS = [
    (b"x-content-type-options", b"nosniff"),  # browsers must not guess content types
    (b"x-frame-options", b"DENY"),  # the API can't be embedded in other sites
    (b"referrer-policy", b"no-referrer"),
    (b"strict-transport-security", b"max-age=31536000; includeSubDomains"),  # HTTPS only (ignored on http)
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
]
API_CSP = (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")  # JSON needs nothing


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        extra = list(BASE_HEADERS)
        if not scope["path"].startswith(DOCS_PATHS):
            extra.append(API_CSP)

        async def with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [h for h in extra if h[0] not in existing]
            await send(message)

        await self.app(scope, receive, with_headers)
