from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

import pandas as pd

from algotrading.metrics import (
    calculate_annualized_volatility,
    calculate_cagr,
    calculate_drawdown,
    calculate_sharpe_ratio,
    calculate_total_return,
)


@dataclass(frozen=True)
class PortfolioAnalysisResult:
    price_matrix: pd.DataFrame
    return_matrix: pd.DataFrame
    individual_equity: pd.DataFrame
    portfolio_equity: pd.DataFrame
    portfolio_orders: pd.DataFrame
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
    rebalance_frequency: str = "daily",
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> PortfolioAnalysisResult:
    """Compara activos individuales y una cartera equal-weight rebalanceada."""
    if initial_capital <= 0:
        raise ValueError("initial_capital debe ser mayor a cero.")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year debe ser mayor a cero.")
    if commission_bps < 0:
        raise ValueError("commission_bps no puede ser negativo.")
    if slippage_bps < 0:
        raise ValueError("slippage_bps no puede ser negativo.")

    prices = build_price_matrix(frames, price_column=price_column)
    returns = calculate_return_matrix(prices)
    individual_equity = initial_capital * prices.divide(prices.iloc[0])

    portfolio_equity, portfolio_orders = simulate_equal_weight_rebalancing(
        price_matrix=prices,
        initial_capital=initial_capital,
        rebalance_frequency=rebalance_frequency,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )
    portfolio_returns = portfolio_equity.set_index("date")["daily_return"].iloc[1:]

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
        portfolio_orders=portfolio_orders,
        correlations=correlations,
        summary=summary,
    )


def simulate_equal_weight_rebalancing(
    price_matrix: pd.DataFrame,
    initial_capital: float = 10_000.0,
    rebalance_frequency: str = "daily",
    commission_bps: float = 0.0,
    slippage_bps: float = 0.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simula rebalanceo equal-weight con cash, posiciones y costos simples."""
    _validate_rebalance_inputs(
        price_matrix=price_matrix,
        initial_capital=initial_capital,
        rebalance_frequency=rebalance_frequency,
        commission_bps=commission_bps,
        slippage_bps=slippage_bps,
    )

    symbols = list(price_matrix.columns)
    target_weights = pd.Series(1 / len(symbols), index=symbols)
    shares = pd.Series(0.0, index=symbols)
    cash = float(initial_capital)
    commission_rate = commission_bps / 10_000
    slippage_rate = slippage_bps / 10_000
    previous_rebalance_key = None
    next_order_id = 1
    rows: list[dict[str, float | int | bool | pd.Timestamp]] = []
    orders: list[dict[str, float | int | str | pd.Timestamp]] = []

    for date, prices in price_matrix.iterrows():
        prices = prices.astype(float)
        pre_trade_equity = cash + float((shares * prices).sum())
        rebalance_key = _rebalance_key(pd.Timestamp(date), rebalance_frequency)
        should_rebalance = (
            previous_rebalance_key is None
            or (rebalance_frequency != "none" and rebalance_key != previous_rebalance_key)
        )
        day_turnover = 0.0
        day_commissions = 0.0

        if should_rebalance:
            previous_rebalance_key = rebalance_key
            target_values = target_weights * pre_trade_equity
            current_values = shares * prices
            deltas = target_values - current_values

            sell_orders = deltas[deltas < -1e-9].sort_values()
            for symbol, delta in sell_orders.items():
                order, cash, shares, executed_mark_value = _execute_portfolio_order(
                    order_id=next_order_id,
                    date=pd.Timestamp(date),
                    symbol=symbol,
                    side="sell",
                    requested_mark_value=abs(float(delta)),
                    prices=prices,
                    shares=shares,
                    cash=cash,
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                    slippage_bps=slippage_bps,
                )
                next_order_id += 1
                orders.append(order)
                day_turnover += executed_mark_value / pre_trade_equity
                day_commissions += float(order["commission"])

            current_values = shares * prices
            deltas = target_values - current_values
            buy_orders = deltas[deltas > 1e-9]
            buy_cost = float(
                (buy_orders * (1 + slippage_rate) * (1 + commission_rate)).sum()
            )
            buy_scale = 1.0 if buy_cost <= cash or buy_cost <= 0 else cash / buy_cost

            for symbol, delta in buy_orders.items():
                order, cash, shares, executed_mark_value = _execute_portfolio_order(
                    order_id=next_order_id,
                    date=pd.Timestamp(date),
                    symbol=symbol,
                    side="buy",
                    requested_mark_value=float(delta) * buy_scale,
                    prices=prices,
                    shares=shares,
                    cash=cash,
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                    slippage_bps=slippage_bps,
                )
                next_order_id += 1
                orders.append(order)
                day_turnover += executed_mark_value / pre_trade_equity
                day_commissions += float(order["commission"])

        position_values = shares * prices
        equity = cash + float(position_values.sum())
        row = {
            "date": pd.Timestamp(date),
            "equity": equity,
            "cash": cash,
            "rebalanced": should_rebalance,
            "turnover": day_turnover,
            "commissions": day_commissions,
        }
        for symbol in symbols:
            row[f"shares_{symbol}"] = float(shares[symbol])
            row[f"weight_{symbol}"] = (
                float(position_values[symbol] / equity) if equity > 0 else 0.0
            )
        rows.append(row)

    portfolio_equity = pd.DataFrame(rows)
    portfolio_equity["daily_return"] = portfolio_equity["equity"].pct_change(fill_method=None).fillna(0.0)
    portfolio_equity["drawdown"] = calculate_drawdown(portfolio_equity["equity"])
    portfolio_orders = _portfolio_orders_frame(orders)
    return portfolio_equity, portfolio_orders


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
    total_return = calculate_total_return(initial_capital, final_equity)
    cagr = calculate_cagr(
        initial_value=initial_capital,
        final_value=final_equity,
        start_date=equity.index[0],
        end_date=equity.index[-1],
    )
    annualized_volatility = calculate_annualized_volatility(
        returns,
        periods_per_year=periods_per_year,
    )
    sharpe_ratio = calculate_sharpe_ratio(
        returns,
        periods_per_year=periods_per_year,
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
        "annualized_volatility": float(annualized_volatility),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": max_drawdown,
    }


def _execute_portfolio_order(
    order_id: int,
    date: pd.Timestamp,
    symbol: str,
    side: str,
    requested_mark_value: float,
    prices: pd.Series,
    shares: pd.Series,
    cash: float,
    commission_rate: float,
    slippage_rate: float,
    slippage_bps: float,
) -> tuple[dict[str, float | int | str | pd.Timestamp], float, pd.Series, float]:
    mark_price = float(prices[symbol])
    if side == "buy":
        execution_price = mark_price * (1 + slippage_rate)
        requested_shares = requested_mark_value / mark_price
        max_affordable_shares = cash / (execution_price * (1 + commission_rate))
        filled_shares = min(requested_shares, max_affordable_shares)
        notional = filled_shares * execution_price
        commission = notional * commission_rate
        cash -= notional + commission
        shares[symbol] += filled_shares
    elif side == "sell":
        execution_price = mark_price * (1 - slippage_rate)
        requested_shares = requested_mark_value / mark_price
        filled_shares = min(requested_shares, float(shares[symbol]))
        notional = filled_shares * execution_price
        commission = notional * commission_rate
        cash += notional - commission
        shares[symbol] -= filled_shares
        if abs(shares[symbol]) <= 1e-12:
            shares[symbol] = 0.0
    else:
        raise ValueError(f"Side no soportado: {side}")

    executed_mark_value = filled_shares * mark_price
    order = {
        "order_id": order_id,
        "date": date,
        "symbol": symbol,
        "side": side,
        "status": "filled",
        "requested_mark_value": requested_mark_value,
        "filled_shares": filled_shares,
        "mark_price": mark_price,
        "execution_price": execution_price,
        "notional": notional,
        "commission": commission,
        "slippage_bps": slippage_bps,
        "cash_after": cash,
        "position_after": float(shares[symbol]),
    }
    return order, cash, shares, executed_mark_value


def _portfolio_orders_frame(
    orders: list[dict[str, float | int | str | pd.Timestamp]],
) -> pd.DataFrame:
    columns = [
        "order_id",
        "date",
        "symbol",
        "side",
        "status",
        "requested_mark_value",
        "filled_shares",
        "mark_price",
        "execution_price",
        "notional",
        "commission",
        "slippage_bps",
        "cash_after",
        "position_after",
    ]
    return pd.DataFrame(orders, columns=columns)


def _validate_rebalance_inputs(
    price_matrix: pd.DataFrame,
    initial_capital: float,
    rebalance_frequency: str,
    commission_bps: float,
    slippage_bps: float,
) -> None:
    if price_matrix.empty:
        raise ValueError("price_matrix no puede estar vacio.")
    if len(price_matrix) < 2:
        raise ValueError("Se necesitan al menos dos filas de precios.")
    if initial_capital <= 0:
        raise ValueError("initial_capital debe ser mayor a cero.")
    if rebalance_frequency not in {"daily", "weekly", "monthly", "none"}:
        raise ValueError("rebalance_frequency debe ser daily, weekly, monthly o none.")
    if commission_bps < 0:
        raise ValueError("commission_bps no puede ser negativo.")
    if slippage_bps < 0:
        raise ValueError("slippage_bps no puede ser negativo.")
    if price_matrix.isna().any().any():
        raise ValueError("price_matrix tiene valores faltantes.")
    if (price_matrix <= 0).any().any():
        raise ValueError("Los precios deben ser mayores a cero.")


def _rebalance_key(date: pd.Timestamp, rebalance_frequency: str) -> object:
    if rebalance_frequency == "daily":
        return date.normalize()
    if rebalance_frequency == "weekly":
        iso = date.isocalendar()
        return (iso.year, iso.week)
    if rebalance_frequency == "monthly":
        return (date.year, date.month)
    if rebalance_frequency == "none":
        return "initial"
    raise ValueError("rebalance_frequency debe ser daily, weekly, monthly o none.")
