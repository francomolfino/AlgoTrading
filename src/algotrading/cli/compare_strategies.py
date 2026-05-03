from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from algotrading.backtesting import BacktestConfig, BacktestResult, run_backtest
from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.strategies.registry import StrategySpec, build_default_strategy_specs
from algotrading.visualization.plots import (
    plot_equity_comparison,
    plot_equity_curve_with_drawdown,
)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compara estrategias long-only simples contra buy and hold."
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
    parser.add_argument("--results-dir", default="reports/strategy_comparison")
    parser.add_argument("--figures-dir", default="reports/figures")
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
    config = BacktestConfig(
        initial_capital=args.initial_capital,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        price_column=args.price_column,
        signal_column="signal",
    )

    specs = _strategy_specs(args)
    results = [_run_strategy(frame, spec, config) for spec in specs]
    buy_and_hold_metrics = results[0][1].metrics

    results_dir = Path(args.results_dir)
    figures_dir = Path(args.figures_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{label}_{safe_filename_part(args.interval)}"

    summary_rows = []
    equity_for_plot: dict[str, pd.DataFrame] = {}
    for spec, result in results:
        strategy_name = safe_filename_part(spec.name)
        equity_path = results_dir / f"{base_name}_{strategy_name}_equity.csv"
        trades_path = results_dir / f"{base_name}_{strategy_name}_trades.csv"
        metrics_path = results_dir / f"{base_name}_{strategy_name}_metrics.json"
        figure_path = figures_dir / f"{base_name}_{strategy_name}_equity.png"

        result.equity_curve.to_csv(equity_path, index=False)
        result.trades.to_csv(trades_path, index=False)
        metrics_path.write_text(
            json.dumps(_json_safe_metrics(result.metrics), indent=2),
            encoding="utf-8",
        )
        figure = plot_equity_curve_with_drawdown(
            result.equity_curve,
            title=f"{label} - {spec.name}",
        )
        figure.savefig(figure_path, dpi=140, bbox_inches="tight")

        summary_rows.append(
            _summary_row(
                name=spec.name,
                result=result,
                buy_and_hold_metrics=buy_and_hold_metrics,
            )
        )
        equity_for_plot[spec.name] = result.equity_curve

    summary = pd.DataFrame(summary_rows)
    summary_path = results_dir / f"{base_name}_summary.csv"
    comparison_figure_path = figures_dir / f"{base_name}_strategy_comparison.png"
    summary.to_csv(summary_path, index=False)
    comparison_figure = plot_equity_comparison(
        equity_for_plot,
        title=f"{label} - comparacion de estrategias",
    )
    comparison_figure.savefig(comparison_figure_path, dpi=140, bbox_inches="tight")

    _print_summary(summary, summary_path, comparison_figure_path)
    return 0


def _strategy_specs(args: argparse.Namespace) -> list[StrategySpec]:
    return build_default_strategy_specs(
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


def _run_strategy(
    frame: pd.DataFrame,
    spec: StrategySpec,
    config: BacktestConfig,
) -> tuple[StrategySpec, BacktestResult]:
    signal_frame = spec.function(frame, signal_column=config.signal_column, **spec.parameters)
    return spec, run_backtest(signal_frame, config=config)


def _summary_row(
    name: str,
    result: BacktestResult,
    buy_and_hold_metrics: dict[str, float | int],
) -> dict[str, float | int | str]:
    metrics = result.metrics
    total_return_delta = float(metrics["total_return"] - buy_and_hold_metrics["total_return"])
    return {
        "strategy": name,
        "final_equity": metrics["final_equity"],
        "total_return": metrics["total_return"],
        "cagr": metrics["cagr"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "max_drawdown": metrics["max_drawdown"],
        "win_rate": metrics["win_rate"],
        "number_of_trades": metrics["number_of_trades"],
        "total_commissions": metrics["total_commissions"],
        "vs_buy_and_hold_return": total_return_delta,
        "comment": _commentary(name, metrics, buy_and_hold_metrics),
    }


def _commentary(
    name: str,
    metrics: dict[str, float | int],
    buy_and_hold_metrics: dict[str, float | int],
) -> str:
    if name == "buy_and_hold":
        return "Benchmark base para comparar las demas estrategias."

    total_return = float(metrics["total_return"])
    benchmark_return = float(buy_and_hold_metrics["total_return"])
    drawdown = float(metrics["max_drawdown"])
    benchmark_drawdown = float(buy_and_hold_metrics["max_drawdown"])

    if total_return >= benchmark_return and drawdown >= benchmark_drawdown:
        return "Mejoro retorno y drawdown vs buy and hold en este periodo."
    if total_return < benchmark_return and drawdown > benchmark_drawdown:
        return "Redujo drawdown, pero sacrifico retorno vs buy and hold."
    if total_return > benchmark_return and drawdown < benchmark_drawdown:
        return "Mejoro retorno, pero con peor drawdown."
    return "No supero a buy and hold en retorno ni drawdown."


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


def _json_safe_metrics(metrics: dict[str, float | int]) -> dict[str, float | int | None]:
    safe: dict[str, float | int | None] = {}
    for key, value in metrics.items():
        if isinstance(value, float) and math.isnan(value):
            safe[key] = None
        else:
            safe[key] = value
    return safe


def _print_summary(
    summary: pd.DataFrame,
    summary_path: Path,
    comparison_figure_path: Path,
) -> None:
    display = summary[
        [
            "strategy",
            "total_return",
            "cagr",
            "sharpe_ratio",
            "max_drawdown",
            "win_rate",
            "number_of_trades",
            "vs_buy_and_hold_return",
        ]
    ].copy()
    for column in [
        "total_return",
        "cagr",
        "max_drawdown",
        "win_rate",
        "vs_buy_and_hold_return",
    ]:
        display[column] = display[column].map(_format_percent)
    display["sharpe_ratio"] = display["sharpe_ratio"].map(_format_float)

    print(f"[ok] resumen -> {summary_path}")
    print(f"[ok] grafico comparativo -> {comparison_figure_path}")
    print("\nComparacion:")
    print(display.to_string(index=False))


def _format_percent(value: float | int) -> str:
    return "n/a" if isinstance(value, float) and math.isnan(value) else f"{value:.2%}"


def _format_float(value: float | int) -> str:
    return "n/a" if isinstance(value, float) and math.isnan(value) else f"{value:.2f}"
