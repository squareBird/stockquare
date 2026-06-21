"""Strategy business logic — CRUD + manual dry-run evaluation (Phase 1).

Phase 1 never places an order: `evaluate` computes a rule-based signal from the
daily OHLCV series and persists it, but the auto-execution gate stack
(STRATEGY.md §5) is Phase 2. The service reuses `StocksService.get_history` for
the candle series so charting and strategies share one OHLCV path.
"""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidSymbolError, StrategyNotFoundError
from app.db.models import Strategy, StrategySignal
from app.models.stocks import ChartPeriod
from app.models.strategy import (
    SignalResponse,
    StrategyCreateRequest,
    StrategyResponse,
    StrategyUpdateRequest,
)
from app.services.indicators import evaluate_rule
from app.services.stock_index import StockMasterIndex
from app.services.stocks import StocksService

logger = logging.getLogger(__name__)

# Lookback window for indicator math. Three months of daily candles (~60
# trading days) covers the Phase 1 indicators (longest is a 20-period MA /
# Bollinger plus the prior bar needed to detect a crossover).
_EVAL_PERIOD = ChartPeriod.THREE_MONTH


class StrategyService:
    """CRUD and evaluation for rule-based strategies."""

    def __init__(
        self,
        session: AsyncSession,
        stocks: StocksService,
        index: StockMasterIndex,
    ) -> None:
        self._session = session
        self._stocks = stocks
        self._index = index

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_strategies(self) -> list[StrategyResponse]:
        result = await self._session.execute(select(Strategy).order_by(Strategy.id.asc()))
        strategies = list(result.scalars().all())
        out: list[StrategyResponse] = []
        for strategy in strategies:
            last = await self._latest_signal(strategy.id)
            out.append(self._to_response(strategy, last))
        return out

    async def get_strategy(self, strategy_id: int) -> StrategyResponse:
        strategy = await self._get_or_404(strategy_id)
        last = await self._latest_signal(strategy.id)
        return self._to_response(strategy, last)

    async def list_signals(self, strategy_id: int) -> list[SignalResponse]:
        await self._get_or_404(strategy_id)
        result = await self._session.execute(
            select(StrategySignal)
            .where(StrategySignal.strategy_id == strategy_id)
            .order_by(StrategySignal.created_at.desc(), StrategySignal.id.desc())
        )
        return [_to_signal_response(row) for row in result.scalars().all()]

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------

    async def create_strategy(self, req: StrategyCreateRequest) -> StrategyResponse:
        # Validate the symbol against the master index when it is populated.
        # If the index failed to load (empty), skip validation rather than
        # rejecting every symbol — the same best-effort stance as search.
        if not self._index.is_empty() and self._index.by_symbol(req.symbol) is None:
            raise InvalidSymbolError(req.symbol)

        strategy = Strategy(
            name=req.name,
            symbol=req.symbol,
            strategy_type=req.strategy_type.value,
            execution_mode=req.execution_mode.value,
            side_policy=req.side_policy.value,
            config=_build_config(req),
            active=req.active,
        )
        self._session.add(strategy)
        await self._session.flush()
        await self._session.refresh(strategy)
        return self._to_response(strategy, None)

    async def update_strategy(
        self, strategy_id: int, req: StrategyUpdateRequest
    ) -> StrategyResponse:
        strategy = await self._get_or_404(strategy_id)
        if req.name is not None:
            strategy.name = req.name
        if req.active is not None:
            strategy.active = req.active
        if req.rule is not None or req.sizing is not None:
            # Reassign config wholesale so SQLAlchemy flags the JSON column
            # dirty (in-place mutation of the dict would go undetected).
            config = dict(strategy.config)
            if req.rule is not None:
                config["rule"] = {
                    "indicators": [
                        ind.model_dump(exclude_none=True) for ind in req.rule.indicators
                    ]
                }
            if req.sizing is not None:
                config["sizing"] = req.sizing.model_dump(exclude_none=True)
            strategy.config = config
        await self._session.flush()
        await self._session.refresh(strategy)
        last = await self._latest_signal(strategy.id)
        return self._to_response(strategy, last)

    async def delete_strategy(self, strategy_id: int) -> None:
        strategy = await self._get_or_404(strategy_id)
        # No DB-level cascade is configured, so drop the signal history first.
        await self._session.execute(
            delete(StrategySignal).where(StrategySignal.strategy_id == strategy_id)
        )
        await self._session.delete(strategy)

    async def evaluate(self, strategy_id: int) -> SignalResponse:
        """Evaluate a strategy now and persist the signal. Never executes."""
        strategy = await self._get_or_404(strategy_id)
        candles = await self._stocks.get_history(strategy.symbol, _EVAL_PERIOD)
        rule = strategy.config.get("rule") or {}
        indicators = rule.get("indicators", [])
        result = evaluate_rule(indicators, candles)
        signal = StrategySignal(
            strategy_id=strategy.id,
            action=result.action.value,
            confidence=result.confidence,
            rationale=result.rationale,
            executed=False,
            order_id=None,
        )
        self._session.add(signal)
        await self._session.flush()
        await self._session.refresh(signal)
        logger.info(
            "strategy evaluated",
            extra={
                "strategy_id": strategy.id,
                "symbol": strategy.symbol,
                "action": result.action.value,
                "candles": len(candles),
            },
        )
        return _to_signal_response(signal)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_or_404(self, strategy_id: int) -> Strategy:
        strategy = await self._session.get(Strategy, strategy_id)
        if strategy is None:
            raise StrategyNotFoundError(strategy_id)
        return strategy

    async def _latest_signal(self, strategy_id: int) -> StrategySignal | None:
        return await self._session.scalar(
            select(StrategySignal)
            .where(StrategySignal.strategy_id == strategy_id)
            .order_by(StrategySignal.created_at.desc(), StrategySignal.id.desc())
            .limit(1)
        )

    def _name_kr(self, symbol: str) -> str:
        row = self._index.by_symbol(symbol)
        if row is not None:
            return row.name_ko or row.name_en
        return ""

    def _to_response(
        self, strategy: Strategy, last: StrategySignal | None
    ) -> StrategyResponse:
        config = strategy.config or {}
        return StrategyResponse(
            id=strategy.id,
            name=strategy.name,
            symbol=strategy.symbol,
            name_kr=self._name_kr(strategy.symbol),
            strategy_type=strategy.strategy_type,
            execution_mode=strategy.execution_mode,
            side_policy=strategy.side_policy,
            rule=config.get("rule"),
            ai=config.get("ai"),
            sizing=config.get("sizing", {}),
            active=strategy.active,
            created_at=strategy.created_at,
            last_signal=_to_signal_response(last) if last is not None else None,
        )


def _build_config(req: StrategyCreateRequest) -> dict:
    return {
        "rule": (
            {"indicators": [ind.model_dump(exclude_none=True) for ind in req.rule.indicators]}
            if req.rule is not None
            else None
        ),
        "ai": req.ai.model_dump() if req.ai is not None else None,
        "sizing": req.sizing.model_dump(exclude_none=True),
    }


def _to_signal_response(signal: StrategySignal) -> SignalResponse:
    return SignalResponse(
        action=signal.action,
        confidence=signal.confidence,
        rationale=signal.rationale,
        executed=signal.executed,
        order_id=signal.order_id,
        created_at=signal.created_at,
    )
