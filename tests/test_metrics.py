import math

import pandas as pd
import pytest

from algotrading.metrics import (
    calculate_annualized_volatility,
    calculate_cagr,
    calculate_drawdown,
    calculate_sharpe_ratio,
    calculate_total_return,
)


def test_calculate_total_return_uses_initial_and_final_values():
    assert calculate_total_return(100, 125) == pytest.approx(0.25)


def test_calculate_total_return_rejects_non_positive_initial_value():
    with pytest.raises(ValueError, match="initial_value"):
        calculate_total_return(0, 125)


def test_calculate_cagr_annualizes_return_between_dates():
    cagr = calculate_cagr(
        initial_value=100,
        final_value=121,
        start_date=pd.Timestamp("2020-01-01"),
        end_date=pd.Timestamp("2022-01-01"),
    )

    assert cagr == pytest.approx(0.10, abs=0.001)


def test_calculate_cagr_returns_nan_when_period_has_no_time():
    cagr = calculate_cagr(
        initial_value=100,
        final_value=110,
        start_date=pd.Timestamp("2020-01-01"),
        end_date=pd.Timestamp("2020-01-01"),
    )

    assert math.isnan(cagr)


def test_calculate_drawdown_returns_peak_to_trough_declines():
    drawdown = calculate_drawdown(pd.Series([100, 120, 90, 150]))

    assert drawdown.tolist() == pytest.approx([0.0, 0.0, -0.25, 0.0])


def test_calculate_drawdown_rejects_non_positive_equity():
    with pytest.raises(ValueError, match="mayor a cero"):
        calculate_drawdown(pd.Series([100, 0, 90]))


def test_annualized_volatility_and_sharpe_handle_returns():
    returns = pd.Series([0.01, -0.01, 0.02, 0.00])

    assert calculate_annualized_volatility(returns, periods_per_year=252) > 0
    assert calculate_sharpe_ratio(returns, periods_per_year=252) == pytest.approx(
        returns.mean() / returns.std(ddof=1) * (252**0.5)
    )
