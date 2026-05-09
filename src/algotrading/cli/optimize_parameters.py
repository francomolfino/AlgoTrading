from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from algotrading.backtesting import BacktestConfig
from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.evaluation import analyze_parameter_sensitivity
from algotrading.optimization import (
    build_rsi_candidates,
    build_sma_candidates,
    run_controlled_search,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Optimizacion controlada de parametros con train/test."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--symbol", help="Ticker ya descargado en data/raw, por ejemplo SPY.")
    source.add_argument("--input", help="Ruta directa a un CSV/parquet OHLCV.")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--price-column", default="adj_close", choices=("adj_close", "close"))
    parser.add_argument(
        "--strategies",
        nargs="+",
        choices=("sma", "rsi"),
        default=["sma", "rsi"],
        help="Familias a evaluar.",
    )
    parser.add_argument("--sma-fast", nargs="+", type=int, default=[10, 20, 30])
    parser.add_argument("--sma-slow", nargs="+", type=int, default=[50, 100, 200])
    parser.add_argument("--rsi-windows", nargs="+", type=int, default=[14])
    parser.add_argument(
        "--rsi-thresholds",
        nargs="+",
        default=["30:70", "25:75"],
        help="Pares oversold:overbought, por ejemplo 30:70 25:75.",
    )
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--warmup-bars", type=int, default=260)
    parser.add_argument("--max-combinations", type=int, default=30)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--results-dir", default="reports/optimization")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = Path(args.input) if args.input else _find_symbol_file(
        data_dir=Path(args.data_dir),
        symbol=args.symbol,
        interval=args.interval,
    )
    frame = load_ohlcv(input_path)
    candidates = _build_candidates(args)
    config = BacktestConfig(
        initial_capital=args.initial_capital,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        price_column=args.price_column,
        signal_column="signal",
    )
    search_result = run_controlled_search(
        frame=frame,
        candidates=candidates,
        config=config,
        train_ratio=args.train_ratio,
        warmup_bars=args.warmup_bars,
        max_combinations=args.max_combinations,
    )

    label = _output_label(args.symbol, input_path)
    base_name = f"{label}_{safe_filename_part(args.interval)}"
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    ranking_path = results_dir / f"{base_name}_optimization_ranking.csv"
    periods_path = results_dir / f"{base_name}_optimization_periods.csv"
    sensitivity_path = results_dir / f"{base_name}_parameter_sensitivity.csv"
    sensitivity = analyze_parameter_sensitivity(search_result.ranking)
    search_result.ranking.to_csv(ranking_path, index=False)
    search_result.period_results.to_csv(periods_path, index=False)
    sensitivity.to_csv(sensitivity_path, index=False)

    print(f"[ok] ranking -> {ranking_path}")
    print(f"[ok] periodos -> {periods_path}")
    print(f"[ok] sensibilidad -> {sensitivity_path}")
    print("\nTop candidatos, ordenados por test vs buy and hold y estabilidad train/test:")
    _print_top(search_result.ranking, top=args.top)
    print("\nSensibilidad de parametros:")
    _print_sensitivity(sensitivity)
    return 0


def _build_candidates(args: argparse.Namespace):
    candidates = []
    selected = set(args.strategies)
    if "sma" in selected:
        candidates.extend(
            build_sma_candidates(
                fast_windows=args.sma_fast,
                slow_windows=args.sma_slow,
                price_column=args.price_column,
            )
        )
    if "rsi" in selected:
        candidates.extend(
            build_rsi_candidates(
                windows=args.rsi_windows,
                threshold_pairs=_parse_threshold_pairs(args.rsi_thresholds),
                price_column=args.price_column,
            )
        )
    return candidates


def _parse_threshold_pairs(values: list[str]) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    for value in values:
        try:
            oversold_raw, overbought_raw = value.split(":", maxsplit=1)
            oversold = float(oversold_raw)
            overbought = float(overbought_raw)
        except ValueError as exc:
            raise ValueError(f"Umbral RSI invalido: {value}. Usa formato 30:70.") from exc
        pairs.append((oversold, overbought))
    return pairs


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


def _print_top(ranking: pd.DataFrame, top: int) -> None:
    display = ranking.head(top)[
        [
            "rank",
            "strategy",
            "test_total_return",
            "test_vs_buy_and_hold_return",
            "test_max_drawdown",
            "test_sharpe_ratio",
            "abs_train_test_return_gap",
            "test_number_of_trades",
            "comment",
        ]
    ].copy()
    for column in [
        "test_total_return",
        "test_vs_buy_and_hold_return",
        "test_max_drawdown",
        "abs_train_test_return_gap",
    ]:
        display[column] = display[column].map(_format_percent)
    display["test_sharpe_ratio"] = display["test_sharpe_ratio"].map(_format_float)
    print(display.to_string(index=False))


def _print_sensitivity(sensitivity: pd.DataFrame) -> None:
    if sensitivity.empty:
        print("Sin sensibilidad para mostrar.")
        return
    display = sensitivity[
        [
            "family",
            "parameter",
            "values_tested",
            "metric_min",
            "metric_median",
            "metric_max",
            "metric_range",
            "best_value",
            "worst_value",
        ]
    ].copy()
    for column in ["metric_min", "metric_median", "metric_max", "metric_range"]:
        display[column] = display[column].map(_format_percent)
    print(display.to_string(index=False))


def _format_percent(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2%}"


def _format_float(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2f}"
