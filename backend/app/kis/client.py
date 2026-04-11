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
    IndexResponse,
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
