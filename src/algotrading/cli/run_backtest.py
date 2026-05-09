from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pandas as pd

from algotrading.analysis.exploration import add_moving_averages
from algotrading.backtesting import BacktestConfig, run_backtest
from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.visualization.plots import plot_equity_curve_with_drawdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backtest long-only simple con comisiones, slippage y metricas basicas."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--symbol", help="Ticker ya descargado en data/raw, por ejemplo SPY.")
    source.add_argument("--input", help="Ruta directa a un CSV/parquet OHLCV.")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--price-column", default="adj_close", choices=("adj_close", "close"))
    parser.add_argument(
        "--signal-column",
        default="signal",
        help="Columna 0/1 a usar. Si no existe, se crea una senal demo precio > SMA.",
    )
    parser.add_argument(
        "--demo-sma-window",
        type=int,
        default=200,
        help="Ventana SMA para crear una senal demo cuando no existe --signal-column.",
    )
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument(
        "--position-fraction",
        type=float,
        default=1.0,
        help="Fraccion del equity a usar al entrar long. 1.0 equivale a 100%%.",
    )
    parser.add_argument(
        "--stop-loss-pct",
        type=float,
        default=None,
        help="Stop loss close-based opcional. Ejemplo: 0.10 equivale a 10%%.",
    )
    parser.add_argument(
        "--take-profit-pct",
        type=float,
        default=None,
        help="Take profit close-based opcional. Ejemplo: 0.25 equivale a 25%%.",
    )
    parser.add_argument("--max-total-exposure", type=float, default=1.0)
    parser.add_argument(
        "--max-drawdown-pct",
        type=float,
        default=None,
        help="Corta la estrategia si el drawdown alcanza este umbral. Ejemplo: 0.20.",
    )
    parser.add_argument("--max-trades-per-day", type=int, default=None)
    parser.add_argument(
        "--volatility-target-pct",
        type=float,
        default=None,
        help="Target de volatilidad anual para reducir exposicion. Ejemplo: 0.15.",
    )
    parser.add_argument("--volatility-window", type=int, default=20)
    parser.add_argument(
        "--allow-missing-signals-as-cash",
        action="store_true",
        help="Trata senales NaN como 0. Por defecto el backtester falla.",
    )
    parser.add_argument("--results-dir", default="reports/backtests")
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
    frame, signal_name = _ensure_signal(
        frame=frame,
        signal_column=args.signal_column,
        price_column=args.price_column,
        demo_sma_window=args.demo_sma_window,
    )

    config = BacktestConfig(
        initial_capital=args.initial_capital,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        price_column=args.price_column,
        signal_column=args.signal_column,
        allow_missing_signals=args.allow_missing_signals_as_cash,
        position_fraction=args.position_fraction,
        stop_loss_pct=args.stop_loss_pct,
        take_profit_pct=args.take_profit_pct,
        max_total_exposure=args.max_total_exposure,
        max_drawdown_pct=args.max_drawdown_pct,
        max_trades_per_day=args.max_trades_per_day,
        volatility_target_pct=args.volatility_target_pct,
        volatility_window=args.volatility_window,
    )
    result = run_backtest(frame, config=config)

    label = _output_label(args.symbol, input_path)
    base_name = f"{label}_{safe_filename_part(args.interval)}_{safe_filename_part(signal_name)}"
    results_dir = Path(args.results_dir)
    figures_dir = Path(args.figures_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    equity_path = results_dir / f"{base_name}_equity.csv"
    trades_path = results_dir / f"{base_name}_trades.csv"
    orders_path = results_dir / f"{base_name}_orders.csv"
    metrics_path = results_dir / f"{base_name}_metrics.json"
    figure_path = figures_dir / f"{base_name}_equity.png"

    result.equity_curve.to_csv(equity_path, index=False)
    result.trades.to_csv(trades_path, index=False)
    result.orders.to_csv(orders_path, index=False)
    metrics_path.write_text(
        json.dumps(_json_safe_metrics(result.metrics), indent=2),
        encoding="utf-8",
    )

    figure = plot_equity_curve_with_drawdown(
        result.equity_curve,
        title=f"{label} - backtest {signal_name}",
    )
    figure.savefig(figure_path, dpi=140, bbox_inches="tight")

    _print_result(
        result.metrics,
        equity_path,
        trades_path,
        orders_path,
        metrics_path,
        figure_path,
    )
    return 0


def _ensure_signal(
    frame: pd.DataFrame,
    signal_column: str,
    price_column: str,
    demo_sma_window: int,
) -> tuple[pd.DataFrame, str]:
    if signal_column in frame.columns:
        return frame, signal_column

    if demo_sma_window <= 0:
        raise ValueError("--demo-sma-window debe ser positivo.")

    result = add_moving_averages(frame, windows=[demo_sma_window], price_column=price_column)
    sma_column = f"sma_{demo_sma_window}"
    result[signal_column] = (result[price_column] > result[sma_column]).astype(int)
    result.loc[result[sma_column].isna(), signal_column] = 0
    return result, f"demo_sma_{demo_sma_window}"


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


def _print_result(
    metrics: dict[str, float | int],
    equity_path: Path,
    trades_path: Path,
    orders_path: Path,
    metrics_path: Path,
    figure_path: Path,
) -> None:
    print(f"[ok] equity curve -> {equity_path}")
    print(f"[ok] trades -> {trades_path}")
    print(f"[ok] orders -> {orders_path}")
    print(f"[ok] metricas -> {metrics_path}")
    print(f"[ok] grafico -> {figure_path}")
    print("\nMetricas:")
    print(f"- capital inicial: {metrics['initial_capital']:.2f}")
    print(f"- equity final: {metrics['final_equity']:.2f}")
    print(f"- retorno total: {metrics['total_return']:.2%}")
    print(f"- CAGR: {_format_percent(metrics['cagr'])}")
    print(f"- Sharpe aprox.: {_format_float(metrics['sharpe_ratio'])}")
    print(f"- max drawdown: {metrics['max_drawdown']:.2%}")
    print(f"- risk halt: {metrics['risk_halt_triggered']}")
    print(f"- benchmark retorno: {metrics['benchmark_total_return']:.2%}")
    print(f"- exceso vs benchmark: {metrics['excess_return_vs_benchmark']:.2%}")
    print(f"- win rate: {_format_percent(metrics['win_rate'])}")
    print(f"- trades: {metrics['number_of_trades']}")
    print(f"- comisiones totales: {metrics['total_commissions']:.2f}")


def _format_percent(value: float | int) -> str:
    return "n/a" if isinstance(value, float) and math.isnan(value) else f"{value:.2%}"


def _format_float(value: float | int) -> str:
    return "n/a" if isinstance(value, float) and math.isnan(value) else f"{value:.2f}"
