"""Stocks domain — symbol search, quotes, ranking, and chart history.

The package layout keeps the domain's modules together; this `__init__`
re-exports the public surface so callers keep using
`from app.services.stocks import StocksService` unchanged.
"""

from app.services.stocks.service import StockSearchItem, StocksService

__all__ = ["StockSearchItem", "StocksService"]
