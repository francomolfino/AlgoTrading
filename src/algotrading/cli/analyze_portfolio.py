from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.portfolio import run_equal_weight_portfolio
from algotrading.visualization.plots import (
    plot_correlation_heatmap,
    plot_portfolio_equity_and_drawdown,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analiza activos multiples y una cartera equal-weight simple."
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Tickers ya descargados, por ejemplo: SPY QQQ BTC-USD ETH-USD.",
    )
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--price-column", default="adj_close", choices=("adj_close", "close"))
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    parser.add_argument(
        "--rebalance-frequency",
        default="daily",
        choices=("daily", "weekly", "monthly", "none"),
        help="Frecuencia de rebalanceo equal-weight.",
    )
    parser.add_argument("--commission-bps", type=float, default=0.0)
    parser.add_argument("--slippage-bps", type=float, default=0.0)
    parser.add_argument("--results-dir", default="reports/portfolio")
    parser.add_argument("--figures-dir", default="reports/figures")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    frames = {
        symbol: load_ohlcv(_find_symbol_file(Path(args.data_dir), symbol, args.interval))
        for symbol in args.symbols
    }
    result = run_equal_weight_portfolio(
        frames=frames,
        initial_capital=args.initial_capital,
        price_column=args.price_column,
        rebalance_frequency=args.rebalance_frequency,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
    )

    label = "_".join(safe_filename_part(symbol) for symbol in args.symbols)
    base_name = f"{label}_{safe_filename_part(args.interval)}"
    results_dir = Path(args.results_dir)
    figures_dir = Path(args.figures_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    prices_path = results_dir / f"{base_name}_prices.csv"
    returns_path = results_dir / f"{base_name}_returns.csv"
    individual_equity_path = results_dir / f"{base_name}_individual_equity.csv"
    portfolio_equity_path = results_dir / f"{base_name}_equal_weight_equity.csv"
    portfolio_orders_path = results_dir / f"{base_name}_equal_weight_orders.csv"
    correlations_path = results_dir / f"{base_name}_correlations.csv"
    summary_path = results_dir / f"{base_name}_summary.csv"
    equity_figure_path = figures_dir / f"{base_name}_portfolio_equity.png"
    correlation_figure_path = figures_dir / f"{base_name}_correlations.png"

    _save_matrix_with_date(result.price_matrix, prices_path)
    _save_matrix_with_date(result.return_matrix, returns_path)
    _save_matrix_with_date(result.individual_equity, individual_equity_path)
    result.portfolio_equity.to_csv(portfolio_equity_path, index=False)
    result.portfolio_orders.to_csv(portfolio_orders_path, index=False)
    result.correlations.to_csv(correlations_path)
    result.summary.to_csv(summary_path, index=False)

    equity_figure = plot_portfolio_equity_and_drawdown(
        individual_equity=result.individual_equity,
        portfolio_equity=result.portfolio_equity,
        title="Cartera equal-weight vs activos individuales",
    )
    equity_figure.savefig(equity_figure_path, dpi=140, bbox_inches="tight")

    correlation_figure = plot_correlation_heatmap(
        result.correlations,
        title="Correlacion de retornos diarios",
    )
    correlation_figure.savefig(correlation_figure_path, dpi=140, bbox_inches="tight")

    _print_summary(
        result.summary,
        result.correlations,
        result.portfolio_orders,
        args.rebalance_frequency,
        summary_path,
        portfolio_orders_path,
        equity_figure_path,
        correlation_figure_path,
    )
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


def _save_matrix_with_date(frame: pd.DataFrame, path: Path) -> None:
    output = frame.copy()
    output.insert(0, "date", output.index)
    output.to_csv(path, index=False)


def _print_summary(
    summary: pd.DataFrame,
    correlations: pd.DataFrame,
    portfolio_orders: pd.DataFrame,
    rebalance_frequency: str,
    summary_path: Path,
    portfolio_orders_path: Path,
    equity_figure_path: Path,
    correlation_figure_path: Path,
) -> None:
    print(f"[ok] resumen -> {summary_path}")
    print(f"[ok] ordenes portfolio -> {portfolio_orders_path}")
    print(f"[ok] grafico portfolio -> {equity_figure_path}")
    print(f"[ok] grafico correlaciones -> {correlation_figure_path}")
    total_commissions = (
        float(portfolio_orders["commission"].sum()) if len(portfolio_orders) else 0.0
    )
    print(f"[ok] rebalanceo -> {rebalance_frequency}")
    print(f"[ok] ordenes/comisiones -> {len(portfolio_orders)} / {total_commissions:.2f}")
    print("\nResumen:")
    display = summary[
        [
            "name",
            "kind",
            "total_return",
            "cagr",
            "annualized_volatility",
            "sharpe_ratio",
            "max_drawdown",
        ]
    ].copy()
    for column in ["total_return", "cagr", "annualized_volatility", "max_drawdown"]:
        display[column] = display[column].map(_format_percent)
    display["sharpe_ratio"] = display["sharpe_ratio"].map(_format_float)
    print(display.to_string(index=False))

    print("\nCorrelaciones:")
    print(correlations.round(2).to_string())


def _format_percent(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2%}"


def _format_float(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2f}"
