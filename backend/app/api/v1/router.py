"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    assistant,
    auth,
    market,
    portfolio,
    stocks,
    strategy,
    trading,
    watchlist,
)

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(portfolio.router)
router.include_router(watchlist.router)
router.include_router(market.router)
router.include_router(stocks.router)
router.include_router(trading.router)
router.include_router(strategy.router)
router.include_router(assistant.router)
