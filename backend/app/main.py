"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import router as api_v1_router
from app.core.config import get_settings, log_credential_status
from app.core.exceptions import StockquareError
from app.db.session import init_db
from app.kis.client import KISClient
from app.services.stock_index import StockMasterIndex, refresh_stock_master_index

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    log_credential_status(settings)
    await init_db()
    app.state.kis_client = KISClient(settings=settings)

    # Master-file CDN lives on a different host from the KIS API, so we
    # use a dedicated short-lived httpx client with a 30s timeout — each
    # zip is a few megabytes and is fetched exactly once on startup.
    app.state.stock_index = StockMasterIndex()
    cache_dir = Path(__file__).resolve().parent.parent / ".cache" / "kis_master"
    cache_dir.mkdir(parents=True, exist_ok=True)
    master_http = httpx.AsyncClient(timeout=30.0)
    try:
        await refresh_stock_master_index(master_http, app.state.stock_index, cache_dir)
    except Exception:
        logger.warning("stock master refresh failed", exc_info=True)
    finally:
        await master_http.aclose()

    try:
        yield
    finally:
        client: KISClient | None = getattr(app.state, "kis_client", None)
        if client is not None:
            await client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Stockquare Backend", version="0.1.0", lifespan=lifespan)

    # Cross-origin resource sharing — browsers enforce Same-Origin Policy
    # between the Next.js frontend (`:3000`) and this API (`:8000`).
    # Without this middleware, cross-origin fetches from the browser are
    # blocked before the response reaches JavaScript even though the
    # backend itself returned 200. CORS response headers wrap every
    # response, including the JSON error bodies emitted by the
    # `_stockquare_error_handler` below.
    #
    # Phase 1: cookie-less auth, so `allow_credentials=False`. This is
    # what lets us use `allow_headers=["*"]` safely — browsers accept the
    # wildcard only when credentials are disallowed. Revisit this when
    # cookie auth lands in Phase 2.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.exception_handler(StockquareError)
    async def _stockquare_error_handler(request: Request, exc: StockquareError) -> JSONResponse:
        logger.info(
            "stockquare error",
            extra={"code": exc.code, "path": request.url.path, "status": exc.http_status},
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={"code": exc.code, "message": exc.message},
        )

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(api_v1_router)
    return app


app = create_app()
