from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    price_column: str = "adj_close"
    signal_column: str = "signal"
    periods_per_year: int = 252
    close_open_position: bool = True


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    metrics: dict[str, float | int]
    config: BacktestConfig


def run_backtest(frame: pd.DataFrame, config: BacktestConfig | None = None) -> BacktestResult:
    """Ejecuta un backtest long-only con senales 0/1 y ejecucion al dia siguiente."""
    config = config or BacktestConfig()
    _validate_config(config)
    data = _prepare_frame(frame, config)

    commission_rate = config.commission_bps / 10_000
    slippage_rate = config.slippage_bps / 10_000
    cash = float(config.initial_capital)
    shares = 0.0
    position = 0
    open_trade: dict[str, float | int | pd.Timestamp] | None = None
    rows: list[dict[str, float | int | str | pd.Timestamp]] = []
    trades: list[dict[str, float | int | str | pd.Timestamp]] = []

    for index, row in data.iterrows():
        date = row["date"]
        price = float(row[config.price_column])
        desired_position = _desired_position(data, index, config)
        action = ""

        if desired_position != position:
            if desired_position == 1:
                action, cash, shares, open_trade = _enter_long(
                    date=date,
                    index=index,
                    price=price,
                    cash=cash,
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                )
                position = 1
            else:
                action, cash, shares, closed_trade = _exit_long(
                    date=date,
                    index=index,
                    price=price,
                    cash=cash,
                    shares=shares,
                    open_trade=open_trade,
                    exit_reason=_exit_reason(data, index, config),
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                )
                trades.append(closed_trade)
                open_trade = None
                position = 0

        equity = cash + shares * price
        rows.append(
            {
                "date": date,
                "price": price,
                "raw_signal": int(row[config.signal_column]),
                "target_position": desired_position,
                "position": position,
                "cash": cash,
                "shares": shares,
                "equity": equity,
                "action": action,
            }
        )

    equity_curve = pd.DataFrame(rows)
    equity_curve["daily_return"] = equity_curve["equity"].pct_change(fill_method=None).fillna(0.0)
    equity_curve["equity_peak"] = equity_curve["equity"].cummax()
    equity_curve["drawdown"] = equity_curve["equity"] / equity_curve["equity_peak"] - 1

    trades_frame = _trades_frame(trades)
    metrics = _calculate_metrics(equity_curve, trades_frame, config)
    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades_frame,
        metrics=metrics,
        config=config,
    )


def _enter_long(
    date: pd.Timestamp,
    index: int,
    price: float,
    cash: float,
    commission_rate: float,
    slippage_rate: float,
) -> tuple[str, float, float, dict[str, float | int | pd.Timestamp]]:
    execution_price = price * (1 + slippage_rate)
    entry_notional = cash / (1 + commission_rate)
    shares = entry_notional / execution_price
    entry_commission = entry_notional * commission_rate
    new_cash = cash - entry_notional - entry_commission

    open_trade: dict[str, float | int | pd.Timestamp] = {
        "entry_date": date,
        "entry_index": index,
        "entry_price": execution_price,
        "shares": shares,
        "entry_notional": entry_notional,
        "entry_commission": entry_commission,
        "entry_total_cost": entry_notional + entry_commission,
    }
    return "buy", new_cash, shares, open_trade


def _exit_long(
    date: pd.Timestamp,
    index: int,
    price: float,
    cash: float,
    shares: float,
    open_trade: dict[str, float | int | pd.Timestamp] | None,
    exit_reason: str,
    commission_rate: float,
    slippage_rate: float,
) -> tuple[str, float, float, dict[str, float | int | str | pd.Timestamp]]:
    if open_trade is None:
        raise ValueError("No hay trade abierto para cerrar.")

    execution_price = price * (1 - slippage_rate)
    exit_notional = shares * execution_price
    exit_commission = exit_notional * commission_rate
    exit_net = exit_notional - exit_commission
    new_cash = cash + exit_net
    entry_total_cost = float(open_trade["entry_total_cost"])
    pnl = exit_net - entry_total_cost

    trade = {
        "entry_date": open_trade["entry_date"],
        "exit_date": date,
        "entry_price": float(open_trade["entry_price"]),
        "exit_price": execution_price,
        "shares": shares,
        "entry_notional": float(open_trade["entry_notional"]),
        "exit_notional": exit_notional,
        "entry_commission": float(open_trade["entry_commission"]),
        "exit_commission": exit_commission,
        "pnl": pnl,
        "return_pct": pnl / entry_total_cost,
        "bars_held": int(index - int(open_trade["entry_index"])),
        "exit_reason": exit_reason,
    }
    return "sell", new_cash, 0.0, trade


def _calculate_metrics(
    equity_curve: pd.DataFrame,
    trades: pd.DataFrame,
    config: BacktestConfig,
) -> dict[str, float | int]:
    final_equity = float(equity_curve["equity"].iloc[-1])
    total_return = final_equity / config.initial_capital - 1
    days = (equity_curve["date"].iloc[-1] - equity_curve["date"].iloc[0]).days
    years = days / 365.25 if days > 0 else math.nan
    cagr = (final_equity / config.initial_capital) ** (1 / years) - 1 if years and years > 0 else math.nan

    returns = equity_curve["daily_return"].dropna()
    volatility = float(returns.std(ddof=1))
    sharpe_ratio = (
        float(returns.mean()) / volatility * math.sqrt(config.periods_per_year)
        if volatility > 0
        else math.nan
    )

    closed_trades = int(len(trades))
    winning_trades = int((trades["pnl"] > 0).sum()) if closed_trades else 0
    total_commissions = (
        float((trades["entry_commission"] + trades["exit_commission"]).sum())
        if closed_trades
        else 0.0
    )

    return {
        "initial_capital": float(config.initial_capital),
        "final_equity": final_equity,
        "total_return": float(total_return),
        "cagr": float(cagr),
        "sharpe_ratio": float(sharpe_ratio),
        "max_drawdown": float(equity_curve["drawdown"].min()),
        "win_rate": float(winning_trades / closed_trades) if closed_trades else math.nan,
        "number_of_trades": closed_trades,
        "winning_trades": winning_trades,
        "total_commissions": total_commissions,
    }


def _prepare_frame(frame: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    required_columns = ["date", config.price_column, config.signal_column]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    data = frame[required_columns].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data[config.price_column] = pd.to_numeric(data[config.price_column], errors="coerce")
    data[config.signal_column] = pd.to_numeric(data[config.signal_column], errors="coerce").fillna(0)

    if data.isna().any().any():
        raise ValueError("Hay fechas o precios invalidos para el backtest.")
    if (data[config.price_column] <= 0).any():
        raise ValueError("Los precios deben ser mayores a cero.")

    signal_values = set(data[config.signal_column].unique())
    if not signal_values.issubset({0, 1}):
        raise ValueError("La senal debe contener solo 0/1 para este backtester long-only.")

    data = data.sort_values("date").reset_index(drop=True)
    if len(data) < 2:
        raise ValueError("Se necesitan al menos dos filas para backtestear.")

    return data


def _desired_position(data: pd.DataFrame, index: int, config: BacktestConfig) -> int:
    if config.close_open_position and index == len(data) - 1:
        return 0
    if index == 0:
        return 0
    return int(data.loc[index - 1, config.signal_column])


def _exit_reason(data: pd.DataFrame, index: int, config: BacktestConfig) -> str:
    if config.close_open_position and index == len(data) - 1:
        return "end_of_backtest"
    return "signal"


def _trades_frame(trades: list[dict[str, float | int | str | pd.Timestamp]]) -> pd.DataFrame:
    columns = [
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "shares",
        "entry_notional",
        "exit_notional",
        "entry_commission",
        "exit_commission",
        "pnl",
        "return_pct",
        "bars_held",
        "exit_reason",
    ]
    return pd.DataFrame(trades, columns=columns)


def _validate_config(config: BacktestConfig) -> None:
    if config.initial_capital <= 0:
        raise ValueError("initial_capital debe ser mayor a cero.")
    if config.commission_bps < 0:
        raise ValueError("commission_bps no puede ser negativo.")
    if config.slippage_bps < 0:
        raise ValueError("slippage_bps no puede ser negativo.")
    if config.periods_per_year <= 0:
        raise ValueError("periods_per_year debe ser mayor a cero.")
