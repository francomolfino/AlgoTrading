from __future__ import annotations

from dataclasses import dataclass
import math

import pandas as pd

from algotrading.metrics import (
    calculate_cagr,
    calculate_drawdown,
    calculate_sharpe_ratio,
    calculate_total_return,
)
from algotrading.risk import (
    RiskLimitState,
    calculate_volatility_target_fraction,
    can_submit_order,
    cap_fraction,
    update_trade_count,
)


@dataclass(frozen=True)
class BacktestConfig:
    initial_capital: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    price_column: str = "adj_close"
    signal_column: str = "signal"
    periods_per_year: int = 252
    close_open_position: bool = True
    allow_missing_signals: bool = False
    position_fraction: float = 1.0
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    max_total_exposure: float = 1.0
    max_drawdown_pct: float | None = None
    max_trades_per_day: int | None = None
    volatility_target_pct: float | None = None
    volatility_window: int = 20


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame
    trades: pd.DataFrame
    orders: pd.DataFrame
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
    orders: list[dict[str, float | int | str | pd.Timestamp]] = []
    next_order_id = 1
    risk_state = RiskLimitState(equity_peak=float(config.initial_capital))
    trade_counts: dict[pd.Timestamp, int] = {}

    for index, row in data.iterrows():
        date = row["date"]
        price = float(row[config.price_column])
        pre_trade_equity = cash + shares * price
        risk_state.update_peak(pre_trade_equity)
        max_drawdown_triggered = risk_state.check_max_drawdown(
            equity=pre_trade_equity,
            max_drawdown_pct=config.max_drawdown_pct,
        )
        desired_position = 0 if risk_state.halted else _desired_position(data, index, config)
        effective_position_fraction = _position_fraction_for_index(data, index, config)
        action = ""
        risk_event = risk_state.halt_reason if risk_state.halted else ""
        blocked_reason = ""

        risk_exit_reason = _risk_exit_reason(price, open_trade, config) if position == 1 else ""
        if position == 1 and max_drawdown_triggered:
            risk_exit_reason = "max_drawdown"
        if position == 1 and risk_exit_reason:
            if not can_submit_order(date, trade_counts, config.max_trades_per_day):
                blocked_reason = "trade_limit"
            else:
                action, cash, shares, closed_trade, order = _exit_long(
                    order_id=next_order_id,
                    date=date,
                    index=index,
                    price=price,
                    cash=cash,
                    shares=shares,
                    open_trade=open_trade,
                    exit_reason=risk_exit_reason,
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                    slippage_bps=config.slippage_bps,
                )
                next_order_id += 1
                update_trade_count(date, trade_counts)
                trades.append(closed_trade)
                orders.append(order)
                open_trade = None
                position = 0

        if not action and desired_position != position:
            if not can_submit_order(date, trade_counts, config.max_trades_per_day):
                blocked_reason = "trade_limit"
            elif desired_position == 1:
                action, cash, shares, open_trade, order = _enter_long(
                    order_id=next_order_id,
                    date=date,
                    index=index,
                    price=price,
                    cash=cash,
                    position_fraction=effective_position_fraction,
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                    slippage_bps=config.slippage_bps,
                )
                next_order_id += 1
                update_trade_count(date, trade_counts)
                orders.append(order)
                position = 1
            else:
                action, cash, shares, closed_trade, order = _exit_long(
                    order_id=next_order_id,
                    date=date,
                    index=index,
                    price=price,
                    cash=cash,
                    shares=shares,
                    open_trade=open_trade,
                    exit_reason=_signal_exit_reason(data, index, config),
                    commission_rate=commission_rate,
                    slippage_rate=slippage_rate,
                    slippage_bps=config.slippage_bps,
                )
                next_order_id += 1
                update_trade_count(date, trade_counts)
                trades.append(closed_trade)
                orders.append(order)
                open_trade = None
                position = 0

        market_value = shares * price
        equity = cash + market_value
        risk_state.update_peak(equity)
        rows.append(
            {
                "date": date,
                "price": price,
                "raw_signal": int(row[config.signal_column]),
                "target_position": desired_position,
                "target_exposure": desired_position * effective_position_fraction,
                "position": position,
                "position_state": "open" if position else "closed",
                "cash": cash,
                "shares": shares,
                "market_value": market_value,
                "equity": equity,
                "action": action,
                "risk_event": risk_event,
                "risk_halted": risk_state.halted,
                "blocked_reason": blocked_reason,
            }
        )

    equity_curve = pd.DataFrame(rows)
    equity_curve["daily_return"] = equity_curve["equity"].pct_change(fill_method=None).fillna(0.0)
    equity_curve["equity_peak"] = equity_curve["equity"].cummax()
    equity_curve["drawdown"] = calculate_drawdown(equity_curve["equity"])
    _add_benchmark_columns(equity_curve, data, config)

    trades_frame = _trades_frame(trades)
    orders_frame = _orders_frame(orders)
    metrics = _calculate_metrics(equity_curve, trades_frame, config)
    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades_frame,
        orders=orders_frame,
        metrics=metrics,
        config=config,
    )



def _enter_long(
    order_id: int,
    date: pd.Timestamp,
    index: int,
    price: float,
    cash: float,
    position_fraction: float,
    commission_rate: float,
    slippage_rate: float,
    slippage_bps: float,
) -> tuple[
    str,
    float,
    float,
    dict[str, float | int | pd.Timestamp],
    dict[str, float | int | str | pd.Timestamp],
]:
    execution_price = price * (1 + slippage_rate)
    requested_total_cost = cash * position_fraction
    entry_notional = requested_total_cost / (1 + commission_rate)
    shares = entry_notional / execution_price
    entry_commission = entry_notional * commission_rate
    new_cash = cash - entry_notional - entry_commission

    open_trade: dict[str, float | int | pd.Timestamp] = {
        "entry_order_id": order_id,
        "entry_date": date,
        "entry_index": index,
        "entry_price": execution_price,
        "shares": shares,
        "entry_notional": entry_notional,
        "entry_commission": entry_commission,
        "entry_total_cost": entry_notional + entry_commission,
    }
    order = _order_record(
        order_id=order_id,
        date=date,
        side="buy",
        reason="signal",
        requested_notional=requested_total_cost,
        requested_shares=math.nan,
        filled_shares=shares,
        mark_price=price,
        execution_price=execution_price,
        notional=entry_notional,
        commission=entry_commission,
        slippage_bps=slippage_bps,
        cash_after=new_cash,
        position_after=shares,
    )
    return "buy", new_cash, shares, open_trade, order


def _exit_long(
    order_id: int,
    date: pd.Timestamp,
    index: int,
    price: float,
    cash: float,
    shares: float,
    open_trade: dict[str, float | int | pd.Timestamp] | None,
    exit_reason: str,
    commission_rate: float,
    slippage_rate: float,
    slippage_bps: float,
) -> tuple[str, float, float, dict[str, float | int | str | pd.Timestamp], dict[str, float | int | str | pd.Timestamp]]:
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
        "entry_order_id": int(open_trade["entry_order_id"]),
        "exit_order_id": order_id,
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
    order = _order_record(
        order_id=order_id,
        date=date,
        side="sell",
        reason=exit_reason,
        requested_notional=exit_notional,
        requested_shares=shares,
        filled_shares=shares,
        mark_price=price,
        execution_price=execution_price,
        notional=exit_notional,
        commission=exit_commission,
        slippage_bps=slippage_bps,
        cash_after=new_cash,
        position_after=0.0,
    )
    return "sell", new_cash, 0.0, trade, order


def _calculate_metrics(
    equity_curve: pd.DataFrame,
    trades: pd.DataFrame,
    config: BacktestConfig,
) -> dict[str, float | int]:
    final_equity = float(equity_curve["equity"].iloc[-1])
    total_return = calculate_total_return(config.initial_capital, final_equity)
    cagr = calculate_cagr(
        initial_value=config.initial_capital,
        final_value=final_equity,
        start_date=equity_curve["date"].iloc[0],
        end_date=equity_curve["date"].iloc[-1],
    )
    sharpe_ratio = calculate_sharpe_ratio(
        equity_curve["daily_return"],
        periods_per_year=config.periods_per_year,
    )

    benchmark_final_equity = float(equity_curve["benchmark_equity"].iloc[-1])
    benchmark_total_return = calculate_total_return(
        config.initial_capital,
        benchmark_final_equity,
    )
    benchmark_cagr = calculate_cagr(
        initial_value=config.initial_capital,
        final_value=benchmark_final_equity,
        start_date=equity_curve["date"].iloc[0],
        end_date=equity_curve["date"].iloc[-1],
    )
    benchmark_sharpe = calculate_sharpe_ratio(
        equity_curve["benchmark_daily_return"],
        periods_per_year=config.periods_per_year,
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
        "benchmark_final_equity": benchmark_final_equity,
        "benchmark_total_return": float(benchmark_total_return),
        "benchmark_cagr": float(benchmark_cagr),
        "benchmark_sharpe_ratio": float(benchmark_sharpe),
        "benchmark_max_drawdown": float(equity_curve["benchmark_drawdown"].min()),
        "excess_return_vs_benchmark": float(total_return - benchmark_total_return),
        "risk_halt_triggered": int(bool(equity_curve["risk_halted"].any()))
        if "risk_halted" in equity_curve.columns
        else 0,
    }


def _prepare_frame(frame: pd.DataFrame, config: BacktestConfig) -> pd.DataFrame:
    required_columns = ["date", config.price_column, config.signal_column]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    data = frame[required_columns].copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data[config.price_column] = pd.to_numeric(data[config.price_column], errors="coerce")
    data[config.signal_column] = pd.to_numeric(data[config.signal_column], errors="coerce")

    invalid_date_or_price = data[["date", config.price_column]].isna().any().any()
    if invalid_date_or_price:
        raise ValueError("Hay fechas o precios invalidos para el backtest.")

    if (data[config.price_column] <= 0).any():
        raise ValueError("Los precios deben ser mayores a cero.")

    if data[config.signal_column].isna().any():
        if not config.allow_missing_signals:
            raise ValueError(
                "Hay senales faltantes. Define allow_missing_signals=True "
                "si queres tratarlas explicitamente como cash."
            )
        data[config.signal_column] = data[config.signal_column].fillna(0)

    signal_values = set(data[config.signal_column].unique())
    if not signal_values.issubset({0, 1}):
        raise ValueError("La senal debe contener solo 0/1 para este backtester long-only.")

    data = data.sort_values("date").reset_index(drop=True)
    if data["date"].duplicated().any():
        raise ValueError("Hay fechas duplicadas para el backtest.")
    if len(data) < 2:
        raise ValueError("Se necesitan al menos dos filas para backtestear.")

    return data


def _desired_position(data: pd.DataFrame, index: int, config: BacktestConfig) -> int:
    if config.close_open_position and index == len(data) - 1:
        return 0
    if index == 0:
        return 0
    return int(data.loc[index - 1, config.signal_column])


def _signal_exit_reason(data: pd.DataFrame, index: int, config: BacktestConfig) -> str:
    if config.close_open_position and index == len(data) - 1:
        return "end_of_backtest"
    return "signal"


def _position_fraction_for_index(
    data: pd.DataFrame,
    index: int,
    config: BacktestConfig,
) -> float:
    capped_base = cap_fraction(config.position_fraction, config.max_total_exposure)
    return calculate_volatility_target_fraction(
        prices=data[config.price_column],
        index=index,
        base_fraction=capped_base,
        target_volatility=config.volatility_target_pct,
        window=config.volatility_window,
        periods_per_year=config.periods_per_year,
    )


def _risk_exit_reason(
    price: float,
    open_trade: dict[str, float | int | pd.Timestamp] | None,
    config: BacktestConfig,
) -> str:
    if open_trade is None:
        return ""

    entry_price = float(open_trade["entry_price"])
    if config.stop_loss_pct is not None and price <= entry_price * (1 - config.stop_loss_pct):
        return "stop_loss"
    if config.take_profit_pct is not None and price >= entry_price * (1 + config.take_profit_pct):
        return "take_profit"
    return ""


def _add_benchmark_columns(
    equity_curve: pd.DataFrame,
    data: pd.DataFrame,
    config: BacktestConfig,
) -> None:
    benchmark_equity = _buy_and_hold_equity(data, config)
    equity_curve["benchmark_equity"] = benchmark_equity
    equity_curve["benchmark_daily_return"] = (
        equity_curve["benchmark_equity"].pct_change(fill_method=None).fillna(0.0)
    )
    equity_curve["benchmark_drawdown"] = calculate_drawdown(equity_curve["benchmark_equity"])


def _buy_and_hold_equity(data: pd.DataFrame, config: BacktestConfig) -> list[float]:
    commission_rate = config.commission_bps / 10_000
    slippage_rate = config.slippage_bps / 10_000
    cash = float(config.initial_capital)
    shares = 0.0
    values: list[float] = []

    for index, row in data.iterrows():
        price = float(row[config.price_column])
        can_enter = index == 1 and (not config.close_open_position or index < len(data) - 1)
        if can_enter:
            execution_price = price * (1 + slippage_rate)
            total_cost = cash * _position_fraction_for_index(data, index, config)
            notional = total_cost / (1 + commission_rate)
            shares = notional / execution_price
            commission = notional * commission_rate
            cash -= notional + commission

        if config.close_open_position and index == len(data) - 1 and shares > 0:
            execution_price = price * (1 - slippage_rate)
            notional = shares * execution_price
            commission = notional * commission_rate
            cash += notional - commission
            shares = 0.0

        values.append(cash + shares * price)

    return values


def _order_record(
    order_id: int,
    date: pd.Timestamp,
    side: str,
    reason: str,
    requested_notional: float,
    requested_shares: float,
    filled_shares: float,
    mark_price: float,
    execution_price: float,
    notional: float,
    commission: float,
    slippage_bps: float,
    cash_after: float,
    position_after: float,
) -> dict[str, float | int | str | pd.Timestamp]:
    return {
        "order_id": order_id,
        "date": date,
        "side": side,
        "status": "filled",
        "reason": reason,
        "requested_notional": requested_notional,
        "requested_shares": requested_shares,
        "filled_shares": filled_shares,
        "mark_price": mark_price,
        "execution_price": execution_price,
        "notional": notional,
        "commission": commission,
        "slippage_bps": slippage_bps,
        "cash_after": cash_after,
        "position_after": position_after,
    }


def _trades_frame(trades: list[dict[str, float | int | str | pd.Timestamp]]) -> pd.DataFrame:
    columns = [
        "entry_order_id",
        "exit_order_id",
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


def _orders_frame(orders: list[dict[str, float | int | str | pd.Timestamp]]) -> pd.DataFrame:
    columns = [
        "order_id",
        "date",
        "side",
        "status",
        "reason",
        "requested_notional",
        "requested_shares",
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


def _validate_config(config: BacktestConfig) -> None:
    if config.initial_capital <= 0:
        raise ValueError("initial_capital debe ser mayor a cero.")
    if config.commission_bps < 0:
        raise ValueError("commission_bps no puede ser negativo.")
    if config.slippage_bps < 0:
        raise ValueError("slippage_bps no puede ser negativo.")
    if config.periods_per_year <= 0:
        raise ValueError("periods_per_year debe ser mayor a cero.")
    if not 0 < config.position_fraction <= 1:
        raise ValueError("position_fraction debe estar entre 0 y 1.")
    if config.stop_loss_pct is not None and not 0 < config.stop_loss_pct < 1:
        raise ValueError("stop_loss_pct debe estar entre 0 y 1.")
    if config.take_profit_pct is not None and config.take_profit_pct <= 0:
        raise ValueError("take_profit_pct debe ser mayor a cero.")
    if not 0 < config.max_total_exposure <= 1:
        raise ValueError("max_total_exposure debe estar entre 0 y 1.")
    if config.max_drawdown_pct is not None and not 0 < config.max_drawdown_pct < 1:
        raise ValueError("max_drawdown_pct debe estar entre 0 y 1.")
    if config.max_trades_per_day is not None and config.max_trades_per_day < 0:
        raise ValueError("max_trades_per_day no puede ser negativo.")
    if config.volatility_target_pct is not None and config.volatility_target_pct <= 0:
        raise ValueError("volatility_target_pct debe ser mayor a cero.")
    if config.volatility_window <= 1:
        raise ValueError("volatility_window debe ser mayor a uno.")
