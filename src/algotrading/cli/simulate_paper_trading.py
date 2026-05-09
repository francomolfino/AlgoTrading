from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.paper_trading import (
    BuyAndHoldPaperStrategy,
    FakeBroker,
    HistoricalDataProvider,
    MovingAverageCrossoverPaperStrategy,
    PaperTradingEngine,
    RiskManager,
    RiskManagerConfig,
)
from algotrading.visualization.plots import plot_equity_curve_with_drawdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Simula paper trading con data historica, broker fake y logs."
    )
    parser.add_argument("--symbol", required=True, help="Ticker ya descargado, por ejemplo SPY.")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--price-column", default="adj_close", choices=("adj_close", "close"))
    parser.add_argument("--strategy", choices=("sma_cross", "buy_and_hold"), default="sma_cross")
    parser.add_argument("--fast-window", type=int, default=20)
    parser.add_argument("--slow-window", type=int, default=200)
    parser.add_argument("--initial-cash", type=float, default=10_000.0)
    parser.add_argument("--commission-bps", type=float, default=1.0)
    parser.add_argument("--slippage-bps", type=float, default=2.0)
    parser.add_argument("--max-position-fraction", type=float, default=1.0)
    parser.add_argument("--max-total-exposure", type=float, default=1.0)
    parser.add_argument("--max-drawdown-pct", type=float, default=None)
    parser.add_argument("--max-trades-per-day", type=int, default=None)
    parser.add_argument("--min-trade-value", type=float, default=25.0)
    parser.add_argument("--dry-run", action="store_true", help="Registra ordenes sin llenar fills.")
    parser.add_argument(
        "--state-path",
        default=None,
        help="Ruta JSON para persistir estado del broker fake al finalizar.",
    )
    parser.add_argument("--results-dir", default="reports/paper_trading")
    parser.add_argument("--figures-dir", default="reports/figures")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = _find_symbol_file(Path(args.data_dir), args.symbol, args.interval)
    frame = load_ohlcv(input_path)
    strategy = _build_strategy(args)
    provider = HistoricalDataProvider(symbol=args.symbol, frame=frame)
    broker = FakeBroker(
        initial_cash=args.initial_cash,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        dry_run=args.dry_run,
        auto_persist_path=args.state_path,
    )
    risk_manager = RiskManager(
        RiskManagerConfig(
            max_position_fraction=args.max_position_fraction,
            max_total_exposure=args.max_total_exposure,
            max_drawdown_pct=args.max_drawdown_pct,
            max_trades_per_day=args.max_trades_per_day,
            min_trade_value=args.min_trade_value,
        )
    )
    engine = PaperTradingEngine(
        data_provider=provider,
        strategy=strategy,
        broker=broker,
        risk_manager=risk_manager,
        price_column=args.price_column,
    )
    result = engine.run()

    base_name = (
        f"{safe_filename_part(args.symbol)}_"
        f"{safe_filename_part(args.interval)}_"
        f"{safe_filename_part(strategy.name)}"
    )
    results_dir = Path(args.results_dir)
    figures_dir = Path(args.figures_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)

    account_path = results_dir / f"{base_name}_account.csv"
    orders_path = results_dir / f"{base_name}_orders.csv"
    order_events_path = results_dir / f"{base_name}_order_events.csv"
    fills_path = results_dir / f"{base_name}_fills.csv"
    errors_path = results_dir / f"{base_name}_errors.csv"
    summary_path = results_dir / f"{base_name}_summary.json"
    figure_path = figures_dir / f"{base_name}_paper_equity.png"

    result.account_history.to_csv(account_path, index=False)
    result.orders.to_csv(orders_path, index=False)
    result.order_events.to_csv(order_events_path, index=False)
    result.fills.to_csv(fills_path, index=False)
    result.errors.to_csv(errors_path, index=False)
    summary_path.write_text(json.dumps(result.summary, indent=2), encoding="utf-8")
    if args.state_path:
        broker.save_state(args.state_path)

    figure = plot_equity_curve_with_drawdown(
        result.account_history,
        title=f"{args.symbol} paper trading fake - {strategy.name}",
    )
    figure.savefig(figure_path, dpi=140, bbox_inches="tight")

    _print_summary(
        result.summary,
        account_path,
        orders_path,
        order_events_path,
        fills_path,
        errors_path,
        summary_path,
        figure_path,
        Path(args.state_path) if args.state_path else None,
    )
    return 0


def _build_strategy(args: argparse.Namespace):
    if args.strategy == "buy_and_hold":
        return BuyAndHoldPaperStrategy()
    return MovingAverageCrossoverPaperStrategy(
        fast_window=args.fast_window,
        slow_window=args.slow_window,
        price_column=args.price_column,
    )


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


def _print_summary(
    summary: dict[str, float | int | str],
    account_path: Path,
    orders_path: Path,
    order_events_path: Path,
    fills_path: Path,
    errors_path: Path,
    summary_path: Path,
    figure_path: Path,
    state_path: Path | None,
) -> None:
    print(f"[ok] account history -> {account_path}")
    print(f"[ok] orders -> {orders_path}")
    print(f"[ok] order events -> {order_events_path}")
    print(f"[ok] fills -> {fills_path}")
    print(f"[ok] errors -> {errors_path}")
    print(f"[ok] summary -> {summary_path}")
    if state_path:
        print(f"[ok] broker state -> {state_path}")
    print(f"[ok] grafico -> {figure_path}")
    print("\nResumen:")
    print(f"- estrategia: {summary['strategy']}")
    print(f"- periodo: {summary['start_date']} a {summary['end_date']}")
    print(f"- equity final: {summary['final_equity']:.2f}")
    print(f"- retorno total: {summary['total_return']:.2%}")
    print(f"- max drawdown: {summary['max_drawdown']:.2%}")
    print(f"- risk halt: {summary['risk_halt_triggered']}")
    print(f"- dry-run: {summary['dry_run']}")
    print(f"- ordenes/eventos/fills/errores: {summary['orders']} / {summary['order_events']} / {summary['fills']} / {summary['errors']}")
    print(f"- comisiones: {summary['total_commissions']:.2f}")
    print(f"- posicion final: {summary['final_position_quantity']:.6f}")
