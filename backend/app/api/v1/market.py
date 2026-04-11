"""Market endpoints — indices."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_kis_client
from app.core.exceptions import KISAPIError, KISNotConfiguredError
from app.kis.client import KISClient
from app.models.market import (
    MarketIndexErrorResponse,
    MarketIndexResponse,
    MarketIndicesResponse,
)
from app.services.market import MarketService

router = APIRouter(prefix="/market", tags=["market"])


def _get_service(kis: KISClient = Depends(get_kis_client)) -> MarketService:
    return MarketService(kis=kis)


@router.get("/indices", response_model=MarketIndicesResponse)
async def market_indices(
    service: MarketService = Depends(_get_service),
) -> MarketIndicesResponse:
    result = await service.get_market_indices()

    # All indices failed → surface a single upstream error. Partial success
    # returns 200 with the healthy subset + an `errors[]` array for the
    # failed slots. When the full failure is caused by missing credentials,
    # preserve the 503 `KIS_NOT_CONFIGURED` semantic so the frontend can
    # show an onboarding hint instead of a generic upstream error.
    if not result.indices and result.errors:
        if all(err.error_code == "KIS_NOT_CONFIGURED" for err in result.errors):
            raise KISNotConfiguredError([])
        raise KISAPIError()

    return MarketIndicesResponse(
        indices=[
            MarketIndexResponse(
                code=item.code,
                name=item.name,
                value=item.value,
                change=item.change,
                change_rate=item.change_rate,
                volume=item.volume,
                status=item.status,
            )
            for item in result.indices
        ],
        errors=[
            MarketIndexErrorResponse(
                code=err.code,
                name=err.name,
                error_code=err.error_code,
                message=err.message,
            )
            for err in result.errors
        ],
    )
