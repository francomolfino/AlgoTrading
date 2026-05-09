from __future__ import annotations

import math

import numpy as np
import pandas as pd


def calculate_total_return(initial_value: float, final_value: float) -> float:
    if initial_value <= 0:
        raise ValueError("initial_value debe ser mayor a cero.")
    if final_value < 0:
        raise ValueError("final_value no puede ser negativo.")
    return float(final_value / initial_value - 1)


def calculate_cagr(
    initial_value: float,
    final_value: float,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> float:
    total_return = calculate_total_return(initial_value, final_value)
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    days = (end - start).days
    if days <= 0:
        return math.nan

    years = days / 365.25
    return float((1 + total_return) ** (1 / years) - 1)


def calculate_annualized_volatility(
    returns: pd.Series,
    periods_per_year: int = 252,
) -> float:
    if periods_per_year <= 0:
        raise ValueError("periods_per_year debe ser mayor a cero.")

    clean_returns = _clean_returns(returns)
    if len(clean_returns) < 2:
        return math.nan

    volatility = clean_returns.std(ddof=1)
    return float(volatility * np.sqrt(periods_per_year))


def calculate_sharpe_ratio(
    returns: pd.Series,
    periods_per_year: int = 252,
    risk_free_rate: float = 0.0,
) -> float:
    if periods_per_year <= 0:
        raise ValueError("periods_per_year debe ser mayor a cero.")

    clean_returns = _clean_returns(returns)
    if len(clean_returns) < 2:
        return math.nan

    periodic_risk_free = risk_free_rate / periods_per_year
    excess_returns = clean_returns - periodic_risk_free
    volatility = excess_returns.std(ddof=1)
    if volatility <= 0:
        return math.nan

    return float(excess_returns.mean() / volatility * np.sqrt(periods_per_year))


def calculate_drawdown(equity: pd.Series) -> pd.Series:
    clean_equity = pd.to_numeric(equity, errors="coerce")
    if clean_equity.isna().any():
        raise ValueError("Equity contiene valores invalidos.")
    if (clean_equity <= 0).any():
        raise ValueError("Equity debe ser mayor a cero para calcular drawdown.")

    return clean_equity / clean_equity.cummax() - 1


def _clean_returns(returns: pd.Series) -> pd.Series:
    clean_returns = pd.to_numeric(returns, errors="coerce").dropna()
    if not np.isfinite(clean_returns).all():
        raise ValueError("Returns contiene valores infinitos.")
    return clean_returns
