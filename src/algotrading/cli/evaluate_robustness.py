from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from algotrading.backtesting import BacktestConfig
from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.evaluation import evaluate_train_test, evaluate_walk_forward
from algotrading.strategies.registry import build_default_strategy_specs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evalua estrategias con train/test y walk-forward simple."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--symbol", help="Ticker ya descargado en data/raw, por ejemplo SPY.")
    source.add_argument("--input", help="Ruta directa a un CSV/parquet OHLCV.")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--price-column", default="adj_close", choices=("adj_close", "close"))
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--warmup-bars", type=int, default=260)
    parser.add_argument("--walk-forward", action="store_true")
    parser.add_argument("--wf-train-rows", type=int, default=756)
    parser.add_argument("--wf-test-rows", type=int, default=252)
    parser.add_argument("--wf-step-rows", type=int, default=None)
    parser.add_argument("--sma-fast", type=int, default=50)
    parser.add_argument("--sma-slow", type=int, default=200)
    parser.add_argument("--rsi-window", type=int, default=14)
    parser.add_argument("--rsi-oversold", type=float, default=30)
    parser.add_argument("--rsi-overbought", type=float, default=70)
    parser.add_argument("--breakout-entry-window", type=int, default=55)
    parser.add_argument("--breakout-exit-window", type=int, default=20)
    parser.add_argument("--trend-fast", type=int, default=20)
    parser.add_argument("--trend-slow", type=int, default=100)
    parser.add_argument("--trend-window", type=int, default=200)
    parser.add_argument("--results-dir", default="reports/robustness")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = Path(args.input) if args.input else _find_symbol_file(
        data_dir=Path(args.data_dir),
        symbol=args.symbol,
        interval=args.interval,
    )
    frame = load_ohlcv(input_path)
    label = _output_label(args.symbol, input_path)
    base_name = f"{label}_{safe_filename_part(args.interval)}"
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    specs = build_default_strategy_specs(
        price_column=args.price_column,
        sma_fast=args.sma_fast,
        sma_slow=args.sma_slow,
        rsi_window=args.rsi_window,
        rsi_oversold=args.rsi_oversold,
        rsi_overbought=args.rsi_overbought,
        breakout_entry_window=args.breakout_entry_window,
        breakout_exit_window=args.breakout_exit_window,
        trend_fast=args.trend_fast,
        trend_slow=args.trend_slow,
        trend_window=args.trend_window,
    )
    config = BacktestConfig(
        initial_capital=args.initial_capital,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        price_column=args.price_column,
        signal_column="signal",
    )

    train_test = evaluate_train_test(
        frame=frame,
        strategy_specs=specs,
        config=config,
        train_ratio=args.train_ratio,
        warmup_bars=args.warmup_bars,
    )
    train_test_path = results_dir / f"{base_name}_train_test.csv"
    train_test.to_csv(train_test_path, index=False)

    print(f"[ok] train/test -> {train_test_path}")
    print("\nTrain/test:")
    _print_table(train_test)

    if args.walk_forward:
        walk_forward = evaluate_walk_forward(
            frame=frame,
            strategy_specs=specs,
            config=config,
            train_rows=args.wf_train_rows,
            test_rows=args.wf_test_rows,
            step_rows=args.wf_step_rows,
            warmup_bars=args.warmup_bars,
        )
        walk_forward_path = results_dir / f"{base_name}_walk_forward.csv"
        walk_forward.to_csv(walk_forward_path, index=False)
        print(f"\n[ok] walk-forward -> {walk_forward_path}")
        print("\nWalk-forward test agregado:")
        _print_walk_forward_aggregate(walk_forward)

    return 0


def _find_symbol_file(data_dir: Path, symbol: str, interval: str) -> Path:
    csv_path = build_data_path(data_dir, symbol, interval, "csv")
    parquet_path = build_data_path(data_dir, symbol, interval, "parquet")
    if csv_path.exists():
        return csv_path
    if parquet_path.exists():
        return parquet_path
    raise FileNotFoundError(
        f"No encontre datos para {symbol}. Esperaba {csv_path} o {parquet_path}."
    )


def _output_label(symbol: str | None, input_path: Path) -> str:
    if symbol:
        return safe_filename_part(symbol)
    return safe_filename_part(input_path.stem)


def _print_table(summary: pd.DataFrame) -> None:
    display = summary[
        [
            "period",
            "strategy",
            "total_return",
            "cagr",
            "sharpe_ratio",
            "max_drawdown",
            "number_of_trades",
            "vs_buy_and_hold_return",
        ]
    ].copy()
    for column in ["total_return", "cagr", "max_drawdown", "vs_buy_and_hold_return"]:
        display[column] = display[column].map(_format_percent)
    display["sharpe_ratio"] = display["sharpe_ratio"].map(_format_float)
    print(display.to_string(index=False))


def _print_walk_forward_aggregate(summary: pd.DataFrame) -> None:
    aggregate = (
        summary.groupby("strategy")
        .agg(
            windows=("window", "nunique"),
            average_return=("total_return", "mean"),
            worst_drawdown=("max_drawdown", "min"),
            average_vs_buy_and_hold=("vs_buy_and_hold_return", "mean"),
            positive_windows=("total_return", lambda values: int((values > 0).sum())),
        )
        .reset_index()
    )
    for column in ["average_return", "worst_drawdown", "average_vs_buy_and_hold"]:
        aggregate[column] = aggregate[column].map(_format_percent)
    print(aggregate.to_string(index=False))


def _format_percent(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2%}"


def _format_float(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2f}"
