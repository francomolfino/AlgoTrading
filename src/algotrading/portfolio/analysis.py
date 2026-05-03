from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Mapping

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PortfolioAnalysisResult:
    price_matrix: pd.DataFrame
    return_matrix: pd.DataFrame
    individual_equity: pd.DataFrame
    portfolio_equity: pd.DataFrame
    correlations: pd.DataFrame
    summary: pd.DataFrame


def build_price_matrix(
    frames: Mapping[str, pd.DataFrame],
    price_column: str = "adj_close",
    join: str = "inner",
) -> pd.DataFrame:
    """Construye una matriz fecha x activo con precios alineados."""
    if not frames:
        raise ValueError("Se requiere al menos un activo.")
    if join != "inner":
        raise ValueError("Por ahora solo soportamos join='inner' para evitar NaNs.")

    series_by_symbol = {}
    for symbol, frame in frames.items():
        missing = [column for column in ["date", price_column] if column not in frame.columns]
        if missing:
            raise ValueError(f"{symbol}: faltan columnas requeridas: {', '.join(missing)}")

        data = frame[["date", price_column]].copy()
        data["date"] = pd.to_datetime(data["date"], errors="coerce")
        data[price_column] = pd.to_numeric(data[price_column], errors="coerce")
        if data.isna().any().any():
            raise ValueError(f"{symbol}: hay fechas o precios invalidos.")
        if (data[price_column] <= 0).any():
            raise ValueError(f"{symbol}: los precios deben ser mayores a cero.")
        if data["date"].duplicated().any():
            raise ValueError(f"{symbol}: hay fechas duplicadas.")

        series_by_symbol[symbol] = data.sort_values("date").set_index("date")[price_column]

    prices = pd.concat(series_by_symbol, axis=1, join=join).dropna().sort_index()
    if len(prices) < 2:
        raise ValueError("No hay suficientes fechas comunes para calcular retornos.")
    return prices


def calculate_return_matrix(price_matrix: pd.DataFrame) -> pd.DataFrame:
    """Retornos simples diarios por activo."""
    if len(price_matrix) < 2:
        raise ValueError("Se necesitan al menos dos filas de precios.")
    returns = price_matrix.pct_change(fill_method=None).dropna(how="any")
    if returns.empty:
        raise ValueError("No se pudieron calcular retornos.")
    return returns


def run_equal_weight_portfolio(
    frames: Mapping[str, pd.DataFrame],
    initial_capital: float = 10_000.0,
    price_column: str = "adj_close",
    periods_per_year: int = 252,
) -> PortfolioAnalysisResult:
    """Compara activos individuales y una cartera equal-weight diaria."""
    if initial_capital <= 0:
        raise ValueError("initial_capital debe ser mayor a cero.")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year debe ser mayor a cero.")

    prices = build_price_matrix(frames, price_column=price_column)
    returns = calculate_return_matrix(prices)
    individual_equity = initial_capital * prices.divide(prices.iloc[0])

    weights = pd.Series(1 / len(prices.columns), index=prices.columns)
    portfolio_returns = returns.mul(weights, axis=1).sum(axis=1)
    portfolio_growth = pd.concat(
        [
            pd.Series([1.0], index=[prices.index[0]]),
            (1 + portfolio_returns).cumprod(),
        ]
    )
    portfolio_equity = pd.DataFrame(
        {
            "date": portfolio_growth.index,
            "equity": initial_capital * portfolio_growth.values,
        }
    )
    portfolio_equity["daily_return"] = portfolio_equity["equity"].pct_change(fill_method=None).fillna(0.0)
    portfolio_equity["drawdown"] = calculate_drawdown(portfolio_equity["equity"])

    correlations = returns.corr()
    summary = _build_summary(
        individual_equity=individual_equity,
        portfolio_equity=portfolio_equity,
        returns=returns,
        portfolio_returns=portfolio_returns,
        initial_capital=initial_capital,
        periods_per_year=periods_per_year,
    )
    return PortfolioAnalysisResult(
        price_matrix=prices,
        return_matrix=returns,
        individual_equity=individual_equity,
        portfolio_equity=portfolio_equity,
        correlations=correlations,
        summary=summary,
    )


def calculate_drawdown(equity: pd.Series) -> pd.Series:
    equity = pd.to_numeric(equity, errors="coerce")
    if equity.isna().any():
        raise ValueError("Equity contiene valores invalidos.")
    return equity / equity.cummax() - 1


def _build_summary(
    individual_equity: pd.DataFrame,
    portfolio_equity: pd.DataFrame,
    returns: pd.DataFrame,
    portfolio_returns: pd.Series,
    initial_capital: float,
    periods_per_year: int,
) -> pd.DataFrame:
    rows = []
    for symbol in individual_equity.columns:
        equity = individual_equity[symbol]
        rows.append(
            _summary_row(
                name=symbol,
                kind="asset",
                equity=equity,
                returns=returns[symbol],
                initial_capital=initial_capital,
                periods_per_year=periods_per_year,
            )
        )

    rows.append(
        _summary_row(
            name="equal_weight_portfolio",
            kind="portfolio",
            equity=portfolio_equity.set_index("date")["equity"],
            returns=portfolio_returns,
            initial_capital=initial_capital,
            periods_per_year=periods_per_year,
        )
    )
    return pd.DataFrame(rows)


def _summary_row(
    name: str,
    kind: str,
    equity: pd.Series,
    returns: pd.Series,
    initial_capital: float,
    periods_per_year: int,
) -> dict[str, float | int | str]:
    final_equity = float(equity.iloc[-1])
    total_return = final_equity / initial_capital - 1
    days = (equity.index[-1] - equity.index[0]).days
    years = days / 365.25 if days > 0 else math.nan
    cagr = (final_equity / initial_capital) ** (1 / years) - 1 if years and years > 0 else math.nan
    volatility = float(returns.std(ddof=1))
    sharpe_ratio = (
        float(returns.mean()) / volatility * math.sqrt(periods_per_year)
        if volatility > 0
        else math.nan
    )
    max_drawdown = float(calculate_drawdown(equity).min())

    return {
        "name": name,
        "kind": kind,
        "start_date": equity.index[0].strftime("%Y-%m-%d"),
        "end_date": equity.index[-1].strftime("%Y-%m-%d"),
        "rows": int(len(equity)),
        "final_equity": final_equity,
        "total_return": float(total_return),
        "cagr": float(cagr),
        "annualized_volatility": float(volatility * np.sqrt(periods_per_year)),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": max_drawdown,
    }
