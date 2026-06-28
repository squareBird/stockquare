"""KIS Open API HTTP client with rate limiting and auth header injection."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from app.core.config import AccountMode, Settings
from app.core.exceptions import InvalidSymbolError, KISAPIError, TokenExpiredError
from app.kis.models import (
    AccountBalanceResponse,
    AccountSummaryResponse,
    DailyCcldResponse,
    DailyChartResponse,
    IndexResponse,
    MinuteChartResponse,
    OrderCashResponse,
    RankingResponse,
    SearchInfoResponse,
    StockPriceResponse,
)
from app.kis.token import TokenManager

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# KIS enforces roughly 20 calls/sec; we leave a 25% safety margin.
_DEFAULT_CALLS_PER_SEC = 15


class RateLimiter:
    """Time-spaced limiter enforcing a minimum interval between requests."""

    def __init__(self, calls_per_second: int = _DEFAULT_CALLS_PER_SEC) -> None:
        self._interval = 1.0 / calls_per_second
        self._lock = asyncio.Lock()
        self._next_available = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._next_available - now
            if wait > 0:
                await asyncio.sleep(wait)
                now = time.monotonic()
            self._next_available = now + self._interval


def _tr_id(real: str, mock: str, mode: AccountMode) -> str:
    return real if mode == AccountMode.REAL else mock


class KISClient:
    """HTTP client for KIS Open API."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
        token_manager: TokenManager | None = None,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._settings = settings
        self._http = http_client or httpx.AsyncClient(
            base_url=settings.kis_base_url,
            timeout=10.0,
            verify=True,
        )
        self._token_manager = token_manager or TokenManager(self._http, settings)
        self._rate_limiter = rate_limiter or RateLimiter()

    @property
    def token_manager(self) -> TokenManager:
        return self._token_manager

    async def close(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Core request wrapper
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        *,
        tr_id: str,
        response_model: type[T],
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> T:
        try:
            return await self._do_request(
                method,
                path,
                tr_id=tr_id,
                response_model=response_model,
                params=params,
                body=body,
            )
        except TokenExpiredError:
            # AUTH.md §5: refresh once and retry exactly one time.
            logger.info("token rejected by KIS, refreshing and retrying once")
            await self._token_manager.refresh()
            return await self._do_request(
                method,
                path,
                tr_id=tr_id,
                response_model=response_model,
                params=params,
                body=body,
            )

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        tr_id: str,
        response_model: type[T],
        params: dict[str, Any] | None,
        body: dict[str, Any] | None,
    ) -> T:
        await self._rate_limiter.acquire()
        token = await self._token_manager.get_token()
        # `custtype: P` identifies the caller as an individual (개인) customer.
        # Several KIS real-mode market-data endpoints (notably
        # `inquire-index-price`) return intermittent HTTP 500 when this
        # header is missing; including it matches the reference samples in
        # the koreainvestment/open-trading-api repository.
        headers = {
            "authorization": f"Bearer {token}",
            "appkey": self._settings.kis_app_key,
            "appsecret": self._settings.kis_app_secret,
            "tr_id": tr_id,
            "custtype": "P",
            "accept": "application/json; charset=utf-8",
            "content-type": "application/json; charset=utf-8",
        }
        try:
            response = await self._http.request(
                method,
                path,
                headers=headers,
                params=params,
                json=body,
            )
        except httpx.HTTPError as exc:
            logger.warning(
                "KIS request network error",
                extra={"tr_id": tr_id, "exc_type": type(exc).__name__},
            )
            raise KISAPIError() from exc

        if response.status_code == 401:
            raise TokenExpiredError()
        if response.status_code >= 400:
            self._log_kis_error_body(tr_id, path, response)
            raise KISAPIError()
        return response_model.model_validate(response.json())

    @staticmethod
    def _log_kis_error_body(tr_id: str, path: str, response: httpx.Response) -> None:
        """Log the KIS error envelope (never the request headers).

        KIS wraps errors in `{rt_cd, msg_cd, msg1}` on both 4xx and 5xx. The
        message usually names the offending field, so capturing it at WARNING
        level is the fastest way to diagnose `FHPUP02100000`-style failures.
        Credentials live in request headers, not the response body, so this
        is safe to emit.
        """
        rt_cd: str | None = None
        msg_cd: str | None = None
        msg1: str | None = None
        body_snippet: str | None = None
        try:
            payload = response.json()
            if isinstance(payload, dict):
                rt_cd = payload.get("rt_cd")
                msg_cd = payload.get("msg_cd")
                msg1 = payload.get("msg1")
        except ValueError:
            body_snippet = response.text[:500] if response.text else None
        logger.warning(
            "KIS request rejected",
            extra={
                "tr_id": tr_id,
                "path": path,
                "status": response.status_code,
                "rt_cd": rt_cd,
                "msg_cd": msg_cd,
                "msg1": msg1,
                "body_snippet": body_snippet,
            },
        )

    # ------------------------------------------------------------------
    # KIS endpoints used by Dashboard APIs
    # ------------------------------------------------------------------

    async def inquire_stock_price(self, symbol: str) -> StockPriceResponse:
        """Fetch current price for a domestic stock."""
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
        }
        result = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-price",
            tr_id="FHKST01010100",
            response_model=StockPriceResponse,
            params=params,
        )
        if result.rt_cd != "0":
            raise InvalidSymbolError(symbol)
        return result

    async def inquire_balance(self) -> AccountBalanceResponse:
        """Fetch the account holdings and cash balance."""
        tr_id = _tr_id("TTTC8434R", "VTTC8434R", self._settings.kis_account_mode)
        params = {
            "CANO": self._settings.kis_account_no,
            "ACNT_PRDT_CD": self._settings.kis_account_product_code,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        return await self._request(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-balance",
            tr_id=tr_id,
            response_model=AccountBalanceResponse,
            params=params,
        )

    async def inquire_account_summary(self) -> AccountSummaryResponse:
        """Fetch the account summary (total asset, P&L)."""
        tr_id = _tr_id("CTRP6548R", "VTRP6548R", self._settings.kis_account_mode)
        params = {
            "CANO": self._settings.kis_account_no,
            "ACNT_PRDT_CD": self._settings.kis_account_product_code,
            "INQR_DVSN_1": "",
            "BSPR_BF_DT_APLY_YN": "",
        }
        return await self._request(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-account-balance",
            tr_id=tr_id,
            response_model=AccountSummaryResponse,
            params=params,
        )

    async def inquire_index(self, index_code: str) -> IndexResponse:
        """Fetch a market index (KOSPI=0001, KOSDAQ=1001)."""
        params = {
            "FID_COND_MRKT_DIV_CODE": "U",
            "FID_INPUT_ISCD": index_code,
        }
        return await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-index-price",
            tr_id="FHPUP02100000",
            response_model=IndexResponse,
            params=params,
        )

    async def search_info(self, symbol: str) -> SearchInfoResponse:
        """Fetch product info for a symbol (used for stock-search by code)."""
        params = {
            "PRDT_TYPE_CD": "300",
            "PDNO": symbol,
        }
        return await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/search-info",
            tr_id="CTPF1002R",
            response_model=SearchInfoResponse,
            params=params,
        )

    async def inquire_daily_itemchartprice(
        self,
        *,
        symbol: str,
        from_date: str,
        to_date: str,
        period_code: str = "D",
    ) -> DailyChartResponse:
        """Fetch the daily OHLCV chart series for a domestic stock.

        `from_date` / `to_date` are `YYYYMMDD` strings; `period_code` is the
        KIS `FID_PERIOD_DIV_CODE` ("D" daily, "W" weekly, "M" monthly). KIS
        returns the candles newest-first in `output2`, so callers reverse them
        to oldest-first. `FID_ORG_ADJ_PRC="0"` requests the adjusted-price
        (수정주가) series.
        """
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_DATE_1": from_date,
            "FID_INPUT_DATE_2": to_date,
            "FID_PERIOD_DIV_CODE": period_code,
            "FID_ORG_ADJ_PRC": "0",
        }
        result = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
            tr_id="FHKST03010100",
            response_model=DailyChartResponse,
            params=params,
        )
        if result.rt_cd != "0":
            raise InvalidSymbolError(symbol)
        return result

    async def inquire_time_itemchartprice(
        self,
        *,
        symbol: str,
        to_time: str,
    ) -> MinuteChartResponse:
        """Fetch one page of intraday 1-minute OHLCV candles for a stock.

        `to_time` is an `HHMMSS` anchor; KIS returns up to ~30 minute candles
        ending at that time, newest-first in `output2`. To assemble a full
        session the caller pages backwards using the oldest returned candle's
        time as the next anchor. `FID_PW_DATA_INCU_YN="Y"` includes the
        pre-market data so the first bars of the session are not dropped.
        """
        params = {
            "FID_ETC_CLS_CODE": "",
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": symbol,
            "FID_INPUT_HOUR_1": to_time,
            "FID_PW_DATA_INCU_YN": "Y",
        }
        result = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice",
            tr_id="FHKST03010200",
            response_model=MinuteChartResponse,
            params=params,
        )
        if result.rt_cd != "0":
            raise InvalidSymbolError(symbol)
        return result

    # ------------------------------------------------------------------
    # Rankings — fluctuation / volume (used by recommendation tools)
    # ------------------------------------------------------------------

    async def ranking_fluctuation(self, *, rising: bool, count: int) -> RankingResponse:
        """Fetch the KRX 등락률 순위 (price-change ranking).

        `rising=True` ranks top gainers (상승률), `False` ranks top losers
        (하락률). `count` bounds how many rows to request from KIS.

        The FID parameter set mirrors the koreainvestment/open-trading-api
        reference for `ranking/fluctuation`; `FID_INPUT_ISCD="0000"` requests
        the whole market and `FID_RANK_SORT_CLS_CODE` selects the direction.
        """
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20170",
            "fid_input_iscd": "0000",
            "fid_rank_sort_cls_code": "0" if rising else "1",
            "fid_input_cnt_1": "0",
            "fid_prc_cls_code": "0",
            "fid_input_price_1": "",
            "fid_input_price_2": "",
            "fid_vol_cnt": "",
            "fid_trgt_cls_code": "0",
            "fid_trgt_exls_cls_code": "0",
            "fid_div_cls_code": "0",
            "fid_rsfl_rate1": "",
            "fid_rsfl_rate2": "",
        }
        result = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/ranking/fluctuation",
            tr_id="FHPST01700000",
            response_model=RankingResponse,
            params=params,
        )
        if result.rt_cd != "0":
            raise KISAPIError("KIS fluctuation ranking failed")
        return RankingResponse(rt_cd=result.rt_cd, output=result.output[:count])

    async def ranking_volume(self, *, count: int) -> RankingResponse:
        """Fetch the KRX 거래량 순위 (trading-volume ranking).

        Requests the whole market (`FID_INPUT_ISCD="0000"`) ordered by
        accumulated volume. `count` bounds how many rows to request.
        """
        params = {
            "fid_cond_mrkt_div_code": "J",
            "fid_cond_scr_div_code": "20171",
            "fid_input_iscd": "0000",
            "fid_div_cls_code": "0",
            "fid_blng_cls_code": "0",
            "fid_trgt_cls_code": "111111111",
            "fid_trgt_exls_cls_code": "0000000000",
            "fid_input_price_1": "",
            "fid_input_price_2": "",
            "fid_vol_cnt": "",
            "fid_input_date_1": "",
        }
        result = await self._request(
            "GET",
            "/uapi/domestic-stock/v1/quotations/volume-rank",
            tr_id="FHPST01710000",
            response_model=RankingResponse,
            params=params,
        )
        if result.rt_cd != "0":
            raise KISAPIError("KIS volume ranking failed")
        return RankingResponse(rt_cd=result.rt_cd, output=result.output[:count])

    # ------------------------------------------------------------------
    # Trading — order placement / cancel / modify / history
    # ------------------------------------------------------------------

    async def order_cash(
        self,
        *,
        symbol: str,
        side: str,
        quantity: int,
        price: int,
        order_type: str,
    ) -> OrderCashResponse:
        """Place a domestic-stock cash order.

        `side` is `"buy"` or `"sell"`; `order_type` is `"limit"` or
        `"market"`. The KIS `ORD_DVSN` is derived from `order_type`:
        `"00"` for limit, `"01"` for market. Market orders send
        `ORD_UNPR="0"` regardless of the passed price.
        """
        if side == "buy":
            tr_id = _tr_id("TTTC0802U", "VTTC0802U", self._settings.kis_account_mode)
        elif side == "sell":
            tr_id = _tr_id("TTTC0801U", "VTTC0801U", self._settings.kis_account_mode)
        else:
            raise ValueError(f"Unknown order side: {side!r}")

        ord_dvsn = "01" if order_type == "market" else "00"
        ord_unpr = "0" if order_type == "market" else str(price)

        body = {
            "CANO": self._settings.kis_account_no,
            "ACNT_PRDT_CD": self._settings.kis_account_product_code,
            "PDNO": symbol,
            "ORD_DVSN": ord_dvsn,
            "ORD_QTY": str(quantity),
            "ORD_UNPR": ord_unpr,
        }
        return await self._request(
            "POST",
            "/uapi/domestic-stock/v1/trading/order-cash",
            tr_id=tr_id,
            response_model=OrderCashResponse,
            body=body,
        )

    async def order_revise_cancel(
        self,
        *,
        krx_fwdg_ord_orgno: str,
        original_order_id: str,
        operation: str,
        quantity: int = 0,
        price: int = 0,
        order_type: str = "limit",
    ) -> OrderCashResponse:
        """Modify or cancel a previously submitted order.

        `operation` is `"modify"` or `"cancel"`. For cancel, quantity/price
        are ignored (KIS expects `ORD_QTY="0"`, `QTY_ALL_ORD_YN="Y"`).
        """
        tr_id = _tr_id("TTTC0803U", "VTTC0803U", self._settings.kis_account_mode)
        rvse_cncl_dvsn_cd = "02" if operation == "cancel" else "01"
        ord_dvsn = "01" if order_type == "market" else "00"

        if operation == "cancel":
            body = {
                "CANO": self._settings.kis_account_no,
                "ACNT_PRDT_CD": self._settings.kis_account_product_code,
                "KRX_FWDG_ORD_ORGNO": krx_fwdg_ord_orgno,
                "ORGN_ODNO": original_order_id,
                "ORD_DVSN": ord_dvsn,
                "RVSE_CNCL_DVSN_CD": rvse_cncl_dvsn_cd,
                "ORD_QTY": "0",
                "ORD_UNPR": "0",
                "QTY_ALL_ORD_YN": "Y",
            }
        else:
            body = {
                "CANO": self._settings.kis_account_no,
                "ACNT_PRDT_CD": self._settings.kis_account_product_code,
                "KRX_FWDG_ORD_ORGNO": krx_fwdg_ord_orgno,
                "ORGN_ODNO": original_order_id,
                "ORD_DVSN": ord_dvsn,
                "RVSE_CNCL_DVSN_CD": rvse_cncl_dvsn_cd,
                "ORD_QTY": str(quantity),
                "ORD_UNPR": str(price),
                "QTY_ALL_ORD_YN": "N",
            }
        return await self._request(
            "POST",
            "/uapi/domestic-stock/v1/trading/order-rvsecncl",
            tr_id=tr_id,
            response_model=OrderCashResponse,
            body=body,
        )

    async def inquire_daily_ccld(
        self,
        *,
        from_date: str,
        to_date: str,
    ) -> DailyCcldResponse:
        """Fetch the account's daily execution / order history.

        `from_date` / `to_date` are `YYYYMMDD` strings. KIS supports up
        to ~90 days of history per call in real mode. Beyond 3 months
        requires a different tr_id (`CTSC9215R` / `VTSC9215R`), which is
        out of scope for Phase 2.
        """
        tr_id = _tr_id("TTTC0081R", "VTTC0081R", self._settings.kis_account_mode)
        params = {
            "CANO": self._settings.kis_account_no,
            "ACNT_PRDT_CD": self._settings.kis_account_product_code,
            "INQR_STRT_DT": from_date,
            "INQR_END_DT": to_date,
            "SLL_BUY_DVSN_CD": "00",
            "INQR_DVSN": "00",
            "PDNO": "",
            "CCLD_DVSN": "00",
            "ORD_GNO_BRNO": "",
            "ODNO": "",
            "INQR_DVSN_3": "00",
            "INQR_DVSN_1": "",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": "",
        }
        return await self._request(
            "GET",
            "/uapi/domestic-stock/v1/trading/inquire-daily-ccld",
            tr_id=tr_id,
            response_model=DailyCcldResponse,
            params=params,
        )
