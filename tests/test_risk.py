import pandas as pd
import pytest

from algotrading.risk import (
    RiskLimitState,
    calculate_volatility_target_fraction,
    can_submit_order,
    cap_fraction,
    update_trade_count,
)


def test_cap_fraction_keeps_long_only_bounds():
    assert cap_fraction(1.5, 1.0) == pytest.approx(1.0)
    assert cap_fraction(-0.5, 1.0) == pytest.approx(0.0)


def test_risk_limit_state_halts_on_max_drawdown():
    state = RiskLimitState(equity_peak=1_000)

    assert state.check_max_drawdown(950, max_drawdown_pct=0.10) is False
    assert state.check_max_drawdown(890, max_drawdown_pct=0.10) is True
    assert state.halted is True
    assert state.halt_reason == "max_drawdown"


def test_volatility_target_fraction_uses_only_previous_prices():
    prices = pd.Series([100, 120, 90, 130, 80])

    fraction = calculate_volatility_target_fraction(
        prices=prices,
        index=4,
        base_fraction=1.0,
        target_volatility=0.10,
        window=2,
    )

    assert 0 < fraction < 1.0


def test_trade_count_limits_orders_per_day():
    counts = {}
    timestamp = pd.Timestamp("2024-01-01 15:30")

    assert can_submit_order(timestamp, counts, max_trades_per_day=1) is True
    update_trade_count(timestamp, counts)
    assert can_submit_order(timestamp, counts, max_trades_per_day=1) is False
