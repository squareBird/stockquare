"""Pydantic models for KIS Open API request/response bodies."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Response from POST /oauth2/tokenP."""

    access_token: str
    token_type: str
    expires_in: int
    access_token_token_expired: str | None = None


class ApprovalKeyResponse(BaseModel):
    """Response from POST /oauth2/Approval (Phase 2)."""

    approval_key: str


class StockPriceOutput(BaseModel):
    """KIS inquire-price output (simplified)."""

    symbol: str = Field(alias="stck_shrn_iscd", default="")
    name: str = Field(alias="hts_kor_isnm", default="")
    price: str = Field(alias="stck_prpr", default="0")
    change: str = Field(alias="prdy_vrss", default="0")
    change_rate: str = Field(alias="prdy_ctrt", default="0")
    volume: str = Field(alias="acml_vol", default="0")

    model_config = {"populate_by_name": True}


class StockPriceResponse(BaseModel):
    """Envelope for inquire-price."""

    rt_cd: str
    msg_cd: str | None = None
    msg1: str | None = None
    output: StockPriceOutput


class AccountBalanceHolding(BaseModel):
    """Single holding in inquire-balance output1."""

    symbol: str = Field(alias="pdno", default="")
    name: str = Field(alias="prdt_name", default="")
    quantity: str = Field(alias="hldg_qty", default="0")
    avg_purchase_price: str = Field(alias="pchs_avg_pric", default="0")
    current_price: str = Field(alias="prpr", default="0")
    evaluation_amount: str = Field(alias="evlu_amt", default="0")
    purchase_amount: str = Field(alias="pchs_amt", default="0")
    profit: str = Field(alias="evlu_pfls_amt", default="0")
    profit_rate: str = Field(alias="evlu_pfls_rt", default="0")

    model_config = {"populate_by_name": True}


class AccountBalanceSummary(BaseModel):
    """Cash summary from inquire-balance output2."""

    cash_balance: str = Field(alias="dnca_tot_amt", default="0")

    model_config = {"populate_by_name": True}


class AccountBalanceResponse(BaseModel):
    """Envelope for inquire-balance."""

    rt_cd: str
    msg_cd: str | None = None
    msg1: str | None = None
    output1: list[AccountBalanceHolding] = Field(default_factory=list)
    output2: list[AccountBalanceSummary] = Field(default_factory=list)


class AccountSummaryOutput(BaseModel):
    """KIS inquire-account-balance output."""

    total_asset: str = Field(alias="tot_asst_amt", default="0")
    total_purchase: str = Field(alias="pchs_amt_smtl", default="0")
    total_profit: str = Field(alias="evlu_pfls_smtl", default="0")
    total_profit_rate: str = Field(alias="evlu_pfls_rt", default="0")
    daily_profit: str = Field(alias="bfdy_cprs_pfls", default="0")

    model_config = {"populate_by_name": True}


class AccountSummaryResponse(BaseModel):
    """Envelope for inquire-account-balance."""

    rt_cd: str
    msg_cd: str | None = None
    msg1: str | None = None
    output2: AccountSummaryOutput | None = None


class IndexOutput(BaseModel):
    """KIS inquire-index-price output."""

    value: str = Field(alias="bstp_nmix_prpr", default="0")
    change: str = Field(alias="bstp_nmix_prdy_vrss", default="0")
    change_rate: str = Field(alias="bstp_nmix_prdy_ctrt", default="0")
    volume: str = Field(alias="acml_vol", default="0")

    model_config = {"populate_by_name": True}


class IndexResponse(BaseModel):
    """Envelope for inquire-index-price."""

    rt_cd: str
    msg_cd: str | None = None
    msg1: str | None = None
    output: IndexOutput


class SearchInfoOutput(BaseModel):
    """KIS search-info output (stock info lookup)."""

    symbol: str = Field(alias="shtn_pdno", default="")
    name: str = Field(alias="prdt_name", default="")
    market_code: str = Field(alias="mket_id_cd", default="")

    model_config = {"populate_by_name": True}


class SearchInfoResponse(BaseModel):
    """Envelope for search-info."""

    rt_cd: str
    msg_cd: str | None = None
    msg1: str | None = None
    output: SearchInfoOutput


# ---------------------------------------------------------------------------
# Internal token state (not sent to KIS)
# ---------------------------------------------------------------------------


class TokenState(BaseModel):
    """Internal in-memory token state."""

    access_token: str
    expires_at: datetime


class MarketStatus(str, Enum):
    """Market open/closed status."""

    OPEN = "open"
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    POST_MARKET = "post_market"


# ---------------------------------------------------------------------------
# Trading — KIS order-cash / order-rvsecncl / inquire-daily-ccld envelopes
# ---------------------------------------------------------------------------


class OrderCashOutput(BaseModel):
    """KIS `order-cash` output.

    `KRX_FWDG_ORD_ORGNO` is the KRX branch office code (5 digits) and
    `ODNO` is the order number (10 digits). The pair together identifies
    an order for later cancel/modify calls.
    """

    krx_fwdg_ord_orgno: str = Field(alias="KRX_FWDG_ORD_ORGNO", default="")
    odno: str = Field(alias="ODNO", default="")
    ord_tmd: str = Field(alias="ORD_TMD", default="")

    model_config = {"populate_by_name": True}


class OrderCashResponse(BaseModel):
    """Envelope for order-cash + order-rvsecncl."""

    rt_cd: str
    msg_cd: str | None = None
    msg1: str | None = None
    output: OrderCashOutput | None = None


class DailyCcldOutput(BaseModel):
    """Single row from inquire-daily-ccld output1."""

    order_id: str = Field(alias="odno", default="")
    origin_order_id: str = Field(alias="orgn_odno", default="")
    branch_office: str = Field(alias="ord_gno_brno", default="")
    symbol: str = Field(alias="pdno", default="")
    name: str = Field(alias="prdt_name", default="")
    side_code: str = Field(alias="sll_buy_dvsn_cd", default="")
    order_type_code: str = Field(alias="ord_dvsn_cd", default="")
    order_quantity: str = Field(alias="ord_qty", default="0")
    filled_quantity: str = Field(alias="tot_ccld_qty", default="0")
    order_price: str = Field(alias="ord_unpr", default="0")
    filled_price: str = Field(alias="avg_prvs", default="0")
    order_time: str = Field(alias="ord_tmd", default="")
    cancel_yn: str = Field(alias="cncl_yn", default="N")

    model_config = {"populate_by_name": True}


class DailyCcldResponse(BaseModel):
    """Envelope for inquire-daily-ccld."""

    rt_cd: str
    msg_cd: str | None = None
    msg1: str | None = None
    output1: list[DailyCcldOutput] = Field(default_factory=list)
