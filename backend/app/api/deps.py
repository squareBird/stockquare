"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.kis.client import KISClient
from app.services.stock_index import StockMasterIndex


def get_kis_client(request: Request) -> KISClient:
    """Return the KISClient bound to the running app.

    The lifespan handler is responsible for creating the client on startup and
    closing it on shutdown. Tests override this dependency directly, so there
    is no need for a fallback construction path.
    """
    client: KISClient | None = getattr(request.app.state, "kis_client", None)
    if client is None:
        raise RuntimeError("KIS client is not initialized on app.state")
    return client


def get_stock_index(request: Request) -> StockMasterIndex:
    """Return the StockMasterIndex bound to the running app.

    Like :func:`get_kis_client`, the lifespan handler constructs the
    index on startup and tests override this dependency to inject a
    pre-seeded index so they don't hit the public master-file CDN.
    """
    index: StockMasterIndex | None = getattr(request.app.state, "stock_index", None)
    if index is None:
        raise RuntimeError("Stock master index is not initialized on app.state")
    return index


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield an async DB session scoped to a single request.

    Uses an explicit transaction: the session commits on normal exit and rolls
    back on any exception raised inside the request handler.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
