"""Deterministic rule-based signal math (Phase 1).

Pure-Python implementations of the moving-average crossover, RSI, and Bollinger
band indicators described in STRATEGY.md §3.1. Kept dependency-free (no pandas)
since the Phase 1 indicator set is small. Each indicator yields a buy/sell/hold
action; multiple indicators combine with **unanimity** — every indicator must
agree on the same non-hold action or the rule resolves to `hold`.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from app.models.stocks import Candle
from app.models.strategy import IndicatorKind, SignalAction


@dataclass(frozen=True)
class RuleSignal:
    action: SignalAction
    confidence: float
    rationale: str


def _sma(values: Sequence[float], period: int) -> float | None:
    """Simple moving average of the last ``period`` values."""
    if period <= 0 or len(values) < period:
        return None
    return sum(values[-period:]) / period


def _rsi(values: Sequence[float], period: int) -> float | None:
    """Classic RSI over the last ``period`` deltas (simple average)."""
    if period <= 0 or len(values) < period + 1:
        return None
    window = values[-(period + 1) :]
    gains = 0.0
    losses = 0.0
    for prev, curr in zip(window[:-1], window[1:], strict=True):
        delta = curr - prev
        if delta >= 0:
            gains += delta
        else:
            losses -= delta
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _eval_ma_cross(closes: Sequence[float], fast: int, slow: int) -> tuple[SignalAction, str]:
    curr_fast = _sma(closes, fast)
    curr_slow = _sma(closes, slow)
    prev_fast = _sma(closes[:-1], fast)
    prev_slow = _sma(closes[:-1], slow)
    label = f"ma_cross({fast}/{slow})"
    if None in (curr_fast, curr_slow, prev_fast, prev_slow):
        return SignalAction.HOLD, f"{label}: insufficient data"
    # mypy/ruff: values are non-None past the guard above.
    assert curr_fast is not None and curr_slow is not None
    assert prev_fast is not None and prev_slow is not None
    if prev_fast <= prev_slow and curr_fast > curr_slow:
        return SignalAction.BUY, f"{label}: golden cross"
    if prev_fast >= prev_slow and curr_fast < curr_slow:
        return SignalAction.SELL, f"{label}: dead cross"
    return SignalAction.HOLD, f"{label}: no cross"


def _eval_rsi(
    closes: Sequence[float], period: int, oversold: float, overbought: float
) -> tuple[SignalAction, str]:
    curr = _rsi(closes, period)
    prev = _rsi(closes[:-1], period)
    label = f"rsi({period})"
    if curr is None or prev is None:
        return SignalAction.HOLD, f"{label}: insufficient data"
    if prev < oversold <= curr:
        return SignalAction.BUY, f"{label}: crossed up through {oversold} ({curr:.1f})"
    if prev > overbought >= curr:
        return SignalAction.SELL, f"{label}: crossed down through {overbought} ({curr:.1f})"
    return SignalAction.HOLD, f"{label}: {curr:.1f}"


def _eval_bollinger(
    closes: Sequence[float], period: int, mult: float
) -> tuple[SignalAction, str]:
    label = f"bollinger({period},{mult})"
    if len(closes) < period:
        return SignalAction.HOLD, f"{label}: insufficient data"
    window = closes[-period:]
    middle = sum(window) / period
    std = statistics.pstdev(window)
    upper = middle + mult * std
    lower = middle - mult * std
    close = closes[-1]
    if close <= lower:
        return SignalAction.BUY, f"{label}: close {close:.0f} at/below lower {lower:.0f}"
    if close >= upper:
        return SignalAction.SELL, f"{label}: close {close:.0f} at/above upper {upper:.0f}"
    return SignalAction.HOLD, f"{label}: within bands"


def _eval_indicator(indicator: dict, closes: Sequence[float]) -> tuple[SignalAction, str]:
    kind = indicator.get("kind")
    if kind == IndicatorKind.MA_CROSS.value:
        return _eval_ma_cross(closes, int(indicator["fast"]), int(indicator["slow"]))
    if kind == IndicatorKind.RSI.value:
        return _eval_rsi(
            closes,
            int(indicator["period"]),
            float(indicator["oversold"]),
            float(indicator["overbought"]),
        )
    if kind == IndicatorKind.BOLLINGER.value:
        return _eval_bollinger(closes, int(indicator["period"]), float(indicator["mult"]))
    return SignalAction.HOLD, f"unknown indicator: {kind}"


def evaluate_rule(indicators: Sequence[dict], candles: Sequence[Candle]) -> RuleSignal:
    """Combine every indicator's action with unanimity.

    A `buy` requires every indicator to signal `buy`; same for `sell`. Any
    disagreement — or any indicator returning `hold` (including on insufficient
    data) — resolves the whole rule to `hold`. Confidence is 1.0 for a unanimous
    non-hold signal, else 0.0.
    """
    if not indicators:
        return RuleSignal(SignalAction.HOLD, 0.0, "no indicators configured")

    closes = [candle.close for candle in candles]
    actions: list[SignalAction] = []
    details: list[str] = []
    for indicator in indicators:
        action, detail = _eval_indicator(indicator, closes)
        actions.append(action)
        details.append(detail)

    rationale = "; ".join(details)
    if all(action == SignalAction.BUY for action in actions):
        return RuleSignal(SignalAction.BUY, 1.0, rationale)
    if all(action == SignalAction.SELL for action in actions):
        return RuleSignal(SignalAction.SELL, 1.0, rationale)
    return RuleSignal(SignalAction.HOLD, 0.0, rationale)
