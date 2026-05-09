from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.paper_trading import (
    ExecutionLoopConfig,
    FakeLiveDataProvider,
    MarketEvent,
    MarketEventType,
    SafeExecutionLoop,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reproduce datos historicos como eventos de mercado tipo live."
    )
    parser.add_argument("--symbol", required=True, help="Ticker ya descargado, por ejemplo SPY.")
    parser.add_argument("--data-dir", default="data/raw")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--heartbeat-every", type=int, default=None)
    parser.add_argument("--max-events", type=int, default=None)
    parser.add_argument("--results-dir", default="reports/live_replay")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = _find_symbol_file(Path(args.data_dir), args.symbol, args.interval)
    frame = load_ohlcv(input_path)
    provider = FakeLiveDataProvider(
        symbol=args.symbol,
        frame=frame,
        heartbeat_every=args.heartbeat_every,
        emit_market_closed=True,
    )

    event_rows: list[dict[str, object]] = []
    loop = SafeExecutionLoop(
        provider=provider,
        on_event=lambda event: event_rows.append(_event_record(event)),
        config=ExecutionLoopConfig(max_events=args.max_events),
    )
    result = loop.run()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{safe_filename_part(args.symbol)}_{safe_filename_part(args.interval)}"
    events_path = results_dir / f"{base_name}_market_events.csv"
    errors_path = results_dir / f"{base_name}_loop_errors.csv"
    summary_path = results_dir / f"{base_name}_loop_summary.json"

    pd.DataFrame(event_rows).to_csv(events_path, index=False)
    result.errors_frame().to_csv(errors_path, index=False)
    summary = {
        "symbol": args.symbol,
        "input_path": str(input_path),
        "events_seen": result.events_seen,
        "bars_seen": result.bars_seen,
        "heartbeats_seen": result.heartbeats_seen,
        "errors": len(result.errors),
        "stopped_reason": result.stopped_reason,
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    _print_summary(summary, events_path, errors_path, summary_path)
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


def _event_record(event: MarketEvent) -> dict[str, object]:
    record: dict[str, object] = {
        "timestamp": event.timestamp,
        "event_type": event.event_type.value,
        "symbol": event.symbol,
        "message": event.message,
    }
    if event.event_type == MarketEventType.BAR and event.bar is not None:
        record.update(event.bar.to_record())
    return record


def _print_summary(
    summary: dict[str, object],
    events_path: Path,
    errors_path: Path,
    summary_path: Path,
) -> None:
    print(f"[ok] market events -> {events_path}")
    print(f"[ok] loop errors -> {errors_path}")
    print(f"[ok] summary -> {summary_path}")
    print("\nResumen:")
    print(f"- symbol: {summary['symbol']}")
    print(f"- eventos: {summary['events_seen']}")
    print(f"- barras: {summary['bars_seen']}")
    print(f"- heartbeats: {summary['heartbeats_seen']}")
    print(f"- errores: {summary['errors']}")
    print(f"- stop: {summary['stopped_reason']}")
