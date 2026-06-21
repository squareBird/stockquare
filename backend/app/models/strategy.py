"""Strategy domain models (Pydantic).

Phase 1 scope: rule-based strategies + manual dry-run evaluation. AI / hybrid
signals, the background scheduler, and auto-execution are deferred to Phase 2,
so create/update reject anything other than `strategy_type=rule` and
`execution_mode=signal_only` (see STRATEGY.md §11 phasing).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class StrategyType(str, Enum):
    RULE = "rule"
    AI = "ai"
    HYBRID = "hybrid"


class ExecutionMode(str, Enum):
    SIGNAL_ONLY = "signal_only"
    AUTO = "auto"


class SidePolicy(str, Enum):
    LONG_ONLY = "long_only"
    BOTH = "both"


class SignalAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class IndicatorKind(str, Enum):
    MA_CROSS = "ma_cross"
    RSI = "rsi"
    BOLLINGER = "bollinger"


class SizingMode(str, Enum):
    FIXED_QUANTITY = "fixed_quantity"
    FIXED_AMOUNT = "fixed_amount"


class IndicatorConfig(BaseModel):
    """One indicator rule. Params are kind-specific and validated below."""

    kind: IndicatorKind
    fast: int | None = Field(default=None, gt=0)
    slow: int | None = Field(default=None, gt=0)
    period: int | None = Field(default=None, gt=0)
    oversold: float | None = None
    overbought: float | None = None
    mult: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_params(self) -> IndicatorConfig:
        if self.kind == IndicatorKind.MA_CROSS:
            if self.fast is None or self.slow is None:
                raise ValueError("ma_cross requires 'fast' and 'slow'")
            if self.fast >= self.slow:
                raise ValueError("ma_cross requires fast < slow")
        elif self.kind == IndicatorKind.RSI:
            if self.period is None or self.oversold is None or self.overbought is None:
                raise ValueError("rsi requires 'period', 'oversold', and 'overbought'")
            if not 0 <= self.oversold < self.overbought <= 100:
                raise ValueError("rsi requires 0 <= oversold < overbought <= 100")
        elif self.kind == IndicatorKind.BOLLINGER:
            if self.period is None or self.mult is None:
                raise ValueError("bollinger requires 'period' and 'mult'")
        return self


class RuleConfig(BaseModel):
    indicators: list[IndicatorConfig] = Field(min_length=1)


class AIConfig(BaseModel):
    """Reserved for Phase 2 AI / hybrid strategies; unused in Phase 1."""

    enabled: bool = False
    model: str | None = None
    role: str | None = None


class SizingConfig(BaseModel):
    mode: SizingMode
    quantity: int | None = Field(default=None, gt=0)
    amount_krw: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def _check_sizing(self) -> SizingConfig:
        if self.mode == SizingMode.FIXED_QUANTITY and self.quantity is None:
            raise ValueError("fixed_quantity sizing requires 'quantity'")
        if self.mode == SizingMode.FIXED_AMOUNT and self.amount_krw is None:
            raise ValueError("fixed_amount sizing requires 'amount_krw'")
        return self


class StrategyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    strategy_type: StrategyType = StrategyType.RULE
    execution_mode: ExecutionMode = ExecutionMode.SIGNAL_ONLY
    side_policy: SidePolicy = SidePolicy.LONG_ONLY
    rule: RuleConfig | None = None
    ai: AIConfig | None = None
    sizing: SizingConfig
    active: bool = False

    @model_validator(mode="after")
    def _phase1_scope(self) -> StrategyCreateRequest:
        if self.strategy_type != StrategyType.RULE:
            raise ValueError("Phase 1 supports strategy_type='rule' only")
        if self.execution_mode != ExecutionMode.SIGNAL_ONLY:
            raise ValueError("Phase 1 supports execution_mode='signal_only' only")
        if self.rule is None:
            raise ValueError("a rule strategy requires 'rule'")
        return self


class StrategyUpdateRequest(BaseModel):
    """Partial update. Phase 1 allows editing name, rule, sizing, active."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    rule: RuleConfig | None = None
    sizing: SizingConfig | None = None
    active: bool | None = None


class SignalResponse(BaseModel):
    action: SignalAction
    confidence: float
    rationale: str
    executed: bool
    order_id: str | None = None
    created_at: datetime


class StrategyResponse(BaseModel):
    id: int
    name: str
    symbol: str
    name_kr: str  # resolved from the stocks index
    strategy_type: StrategyType
    execution_mode: ExecutionMode
    side_policy: str
    rule: dict | None
    ai: dict | None
    sizing: dict
    active: bool
    created_at: datetime
    last_signal: SignalResponse | None = None


class StrategiesResponse(BaseModel):
    strategies: list[StrategyResponse]
    count: int


class SignalsResponse(BaseModel):
    signals: list[SignalResponse]
    count: int
