"""Tests for StocksService.rank_stocks + get_quote (KIS ranking capability)."""

from __future__ import annotations

import pytest

from app.core.exceptions import KISAPIError
from app.kis.master import StockMasterRow
from app.kis.models import RankingResponse, RankingRow, StockPriceOutput, StockPriceResponse
from app.models.stocks import RankBy, RankDirection, StockMarket
from app.services.stock_index import StockMasterIndex
from app.services.stocks import StocksService
from tests.conftest import FakeKISClient


def _index(*rows: tuple[str, str]) -> StockMasterIndex:
    idx = StockMasterIndex()
    idx.replace([StockMasterRow(symbol=s, name_ko=n, name_en="", market=StockMarket.KOSPI) for s, n in rows])
    return idx


@pytest.mark.asyncio
async def test_rank_stocks_fluctuation_resolves_index_name() -> None:
    kis = FakeKISClient()
    kis.ranking_fluctuation.return_value = RankingResponse(
        rt_cd="0",
        output=[
            RankingRow(stck_shrn_iscd="005930", stck_prpr="72000", prdy_ctrt="5.1", acml_vol="100"),
            RankingRow(stck_shrn_iscd="000660", stck_prpr="180000", prdy_ctrt="3.2", acml_vol="50"),
        ],
    )
    service = StocksService(kis=kis, index=_index(("005930", "삼성전자"), ("000660", "SK하이닉스")))

    ranked = await service.rank_stocks(by=RankBy.FLUCTUATION, direction=RankDirection.UP, limit=5)

    assert [r.symbol for r in ranked] == ["005930", "000660"]
    assert ranked[0].name == "삼성전자"
    assert ranked[0].price == 72000
    assert ranked[0].change_rate == pytest.approx(5.1)
    kis.ranking_fluctuation.assert_awaited_once()
    assert kis.ranking_fluctuation.await_args.kwargs == {"rising": True, "count": 5}


@pytest.mark.asyncio
async def test_rank_stocks_volume_uses_volume_endpoint() -> None:
    kis = FakeKISClient()
    kis.ranking_volume.return_value = RankingResponse(
        rt_cd="0",
        output=[RankingRow(stck_shrn_iscd="005930", stck_prpr="72000", prdy_ctrt="1.0", acml_vol="999")],
    )
    service = StocksService(kis=kis, index=_index(("005930", "삼성전자")))

    ranked = await service.rank_stocks(by=RankBy.VOLUME, limit=3)

    assert ranked[0].volume == 999
    kis.ranking_volume.assert_awaited_once()
    kis.ranking_fluctuation.assert_not_called()


@pytest.mark.asyncio
async def test_rank_stocks_limit_clamped() -> None:
    kis = FakeKISClient()
    kis.ranking_fluctuation.return_value = RankingResponse(rt_cd="0", output=[])
    service = StocksService(kis=kis, index=_index())

    await service.rank_stocks(by=RankBy.FLUCTUATION, limit=999)

    assert kis.ranking_fluctuation.await_args.kwargs["count"] == 20


@pytest.mark.asyncio
async def test_rank_stocks_propagates_kis_error() -> None:
    kis = FakeKISClient()
    kis.ranking_fluctuation.side_effect = KISAPIError()
    service = StocksService(kis=kis, index=_index())

    with pytest.raises(KISAPIError):
        await service.rank_stocks(by=RankBy.FLUCTUATION)


@pytest.mark.asyncio
async def test_get_quote_resolves_name_and_price() -> None:
    kis = FakeKISClient()
    kis.inquire_stock_price.return_value = StockPriceResponse(
        rt_cd="0",
        output=StockPriceOutput(stck_shrn_iscd="005930", stck_prpr="72000", prdy_ctrt="2.1", acml_vol="10"),
    )
    service = StocksService(kis=kis, index=_index(("005930", "삼성전자")))

    quote = await service.get_quote("005930")

    assert quote.name == "삼성전자"
    assert quote.price == 72000
    assert quote.change_rate == pytest.approx(2.1)
