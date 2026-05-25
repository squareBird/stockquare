"""Unit tests for StockMasterIndex ranking and lookup."""

from __future__ import annotations

import unicodedata

from app.kis.master import StockMasterRow
from app.models.stocks import StockMarket
from app.services.stock_index import StockMasterIndex


def _row(
    symbol: str,
    name_ko: str = "",
    name_en: str = "",
    market: StockMarket = StockMarket.KOSPI,
) -> StockMasterRow:
    return StockMasterRow(symbol=symbol, name_ko=name_ko, name_en=name_en, market=market)


def test_search_exact_symbol_beats_name_match() -> None:
    index = StockMasterIndex()
    index.replace(
        [
            _row(symbol="005930", name_ko="삼성전자"),
            _row(symbol="AMZN", name_en="005930 CORP", market=StockMarket.NASDAQ),
        ]
    )
    hits = index.search("005930", limit=5)
    assert len(hits) == 2
    assert hits[0].symbol == "005930"


def test_search_exact_name_beats_prefix() -> None:
    index = StockMasterIndex()
    index.replace(
        [
            _row(symbol="111111", name_ko="삼성전자우"),  # prefix match on "삼성전자"
            _row(symbol="005930", name_ko="삼성전자"),  # exact
        ]
    )
    hits = index.search("삼성전자", limit=5)
    assert hits[0].symbol == "005930"
    assert hits[1].symbol == "111111"


def test_search_nfc_normalization() -> None:
    decomposed = unicodedata.normalize("NFD", "삼성전자")
    assert decomposed != "삼성전자"  # sanity
    index = StockMasterIndex()
    index.replace([_row(symbol="005930", name_ko=decomposed)])
    hits = index.search("삼성전자", limit=5)
    assert len(hits) == 1
    assert hits[0].symbol == "005930"


def test_search_is_case_insensitive() -> None:
    index = StockMasterIndex()
    index.replace(
        [
            _row(
                symbol="AMZN",
                name_en="Amazon.com Inc",
                market=StockMarket.NASDAQ,
            ),
        ]
    )
    lower = index.search("amazon", limit=5)
    upper = index.search("AMAZON", limit=5)
    mixed = index.search("AmAzOn", limit=5)
    assert [h.symbol for h in lower] == ["AMZN"]
    assert [h.symbol for h in upper] == ["AMZN"]
    assert [h.symbol for h in mixed] == ["AMZN"]


def test_search_respects_limit() -> None:
    index = StockMasterIndex()
    index.replace(
        [
            _row(symbol="005930", name_ko="삼성전자"),
            _row(symbol="006400", name_ko="삼성SDI"),
            _row(symbol="028260", name_ko="삼성물산"),
            _row(symbol="207940", name_ko="삼성바이오로직스"),
        ]
    )
    hits = index.search("삼성", limit=2)
    assert len(hits) == 2


def test_search_empty_index_returns_empty() -> None:
    index = StockMasterIndex()
    assert index.search("anything", limit=5) == []


def test_search_empty_query_returns_empty() -> None:
    index = StockMasterIndex()
    index.replace([_row(symbol="005930", name_ko="삼성전자")])
    assert index.search("", limit=5) == []
    assert index.search("   ", limit=5) == []


def test_by_symbol_roundtrip() -> None:
    index = StockMasterIndex()
    row = _row(symbol="005930", name_ko="삼성전자")
    index.replace([row])
    assert index.by_symbol("005930") == row
    assert index.by_symbol("999999") is None


def test_replace_is_atomic_under_repeat() -> None:
    index = StockMasterIndex()
    index.replace([_row(symbol="005930", name_ko="삼성전자")])
    assert len(index) == 1
    index.replace(
        [
            _row(symbol="AMZN", name_en="Amazon", market=StockMarket.NASDAQ),
            _row(symbol="NVDA", name_en="NVIDIA", market=StockMarket.NASDAQ),
        ]
    )
    assert len(index) == 2
    assert index.by_symbol("005930") is None
    assert index.by_symbol("AMZN") is not None
