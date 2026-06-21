"""Unit tests for the rule-based indicator math."""

from __future__ import annotations

from app.models.stocks import Candle
from app.models.strategy import SignalAction
from app.services.indicators import evaluate_rule


def _candles(closes: list[float]) -> list[Candle]:
    return [
        Candle(time=f"2026-01-{i + 1:02d}", open=c, high=c, low=c, close=c, volume=0)
        for i, c in enumerate(closes)
    ]


# Series engineered so a 2/3 MA produces a golden cross on the last bar.
_GOLDEN = [10, 10, 10, 8, 14]
# Mirror image: a dead cross on the last bar.
_DEAD = [10, 10, 10, 12, 6]


def test_ma_cross_golden_cross_buys() -> None:
    result = evaluate_rule([{"kind": "ma_cross", "fast": 2, "slow": 3}], _candles(_GOLDEN))
    assert result.action == SignalAction.BUY
    assert result.confidence == 1.0


def test_ma_cross_dead_cross_sells() -> None:
    result = evaluate_rule([{"kind": "ma_cross", "fast": 2, "slow": 3}], _candles(_DEAD))
    assert result.action == SignalAction.SELL


def test_ma_cross_insufficient_data_holds() -> None:
    result = evaluate_rule([{"kind": "ma_cross", "fast": 2, "slow": 3}], _candles([10, 10]))
    assert result.action == SignalAction.HOLD
    assert "insufficient data" in result.rationale


def test_rsi_cross_up_through_oversold_buys() -> None:
    # prev RSI(2) = 0 (<30), curr RSI(2) = 75 (>=30) -> coming out of oversold.
    result = evaluate_rule(
        [{"kind": "rsi", "period": 2, "oversold": 30, "overbought": 70}],
        _candles([10, 7, 6, 9]),
    )
    assert result.action == SignalAction.BUY


def test_bollinger_lower_band_buys() -> None:
    result = evaluate_rule(
        [{"kind": "bollinger", "period": 3, "mult": 1}], _candles([10, 10, 8])
    )
    assert result.action == SignalAction.BUY


def test_bollinger_upper_band_sells() -> None:
    result = evaluate_rule(
        [{"kind": "bollinger", "period": 3, "mult": 1}], _candles([10, 10, 12])
    )
    assert result.action == SignalAction.SELL


def test_unanimity_required_disagreement_holds() -> None:
    # On the golden-cross series the MA buys but a tight Bollinger sells
    # (last close pierces the upper band) -> the rule must resolve to hold.
    indicators = [
        {"kind": "ma_cross", "fast": 2, "slow": 3},
        {"kind": "bollinger", "period": 3, "mult": 1},
    ]
    result = evaluate_rule(indicators, _candles(_GOLDEN))
    assert result.action == SignalAction.HOLD
    assert result.confidence == 0.0


def test_no_indicators_holds() -> None:
    result = evaluate_rule([], _candles(_GOLDEN))
    assert result.action == SignalAction.HOLD
