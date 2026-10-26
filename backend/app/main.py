"""Fleece Detector API entry point.  Run:  uvicorn app.main:app --reload"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.api.security import (
    DEFAULT_RULES,
    MAX_BODY_BYTES,
    BodySizeLimitMiddleware,
    RateLimitMiddleware,
    RateRule,
    SecurityHeadersMiddleware,
)
from app.config import get_settings
from app.integrations.espn import EspnError
from app.services.errors import TradeValidationError, UnknownPlayerError
from app.services.league_import import EspnLeagueService
from app.services.player_repository import PlayerRepository, create_repository
from app.services.trending import TrendingService

logging.basicConfig(level=logging.INFO)


def create_app(
    repository: PlayerRepository | None = None,
    trending: TrendingService | None = None,
    espn: EspnLeagueService | None = None,
    rate_rules: tuple[RateRule, ...] = DEFAULT_RULES,
) -> FastAPI:
    settings = get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.repository = repository or create_repository(settings)
        app.state.trending = trending or TrendingService()
        app.state.espn = espn or EspnLeagueService()
        yield

    app = FastAPI(
        title="Fleece Detector API",
        version="0.1.0",
        description="Explainable, roster-aware fantasy football trade evaluation.",
        lifespan=lifespan,
        debug=False,  # never show tracebacks to clients; unexpected errors return a plain 500
    )
    # Middleware runs outermost-last-added. Order, outside in: CORS -> security headers -> rate limit
    # -> body size cap -> app. CORS is outermost so even 429/413 responses are readable by the frontend.
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=MAX_BODY_BYTES)
    app.add_middleware(RateLimitMiddleware, rules=rate_rules)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # only the frontend's own address(es), never "*"
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,  # the API uses no cookies or logins
    )

    @app.exception_handler(UnknownPlayerError)
    async def _unknown_player(_: Request, exc: UnknownPlayerError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "unknown_player", "message": str(exc), "player_ids": exc.player_ids}},
        )

    @app.exception_handler(EspnError)
    async def _espn_error(_: Request, exc: EspnError) -> JSONResponse:
        status = {"not_found": 404, "private": 403}.get(exc.code, 502)
        return JSONResponse(status_code=status, content={"error": {"code": f"espn_{exc.code}", "message": str(exc)}})

    @app.exception_handler(TradeValidationError)
    async def _invalid_trade(_: Request, exc: TradeValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "invalid_trade", "message": str(exc)}},
        )

    app.include_router(router)
    return app


app = create_app()
