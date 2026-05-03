from __future__ import annotations

import argparse
from pathlib import Path

from algotrading.data.storage import build_data_path, save_ohlcv
from algotrading.data.yahoo import download_ohlcv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Descarga datos historicos OHLCV desde Yahoo Finance."
    )
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Tickers a descargar, por ejemplo: SPY QQQ BTC-USD.",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Fecha inicial YYYY-MM-DD.",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="Fecha final YYYY-MM-DD. En datos diarios suele ser exclusiva.",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help="Intervalo de Yahoo Finance, por ejemplo: 1d, 1wk, 1mo.",
    )
    parser.add_argument(
        "--format",
        choices=("csv", "parquet"),
        default="csv",
        help="Formato de salida.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/raw",
        help="Directorio donde guardar los archivos.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Detiene la ejecucion ante el primer simbolo fallido.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    failures: list[tuple[str, str]] = []

    for symbol in args.symbols:
        try:
            frame = download_ohlcv(
                symbol=symbol,
                start=args.start,
                end=args.end,
                interval=args.interval,
            )
            output_path = build_data_path(
                output_dir=output_dir,
                symbol=symbol,
                interval=args.interval,
                file_format=args.format,
            )
            save_ohlcv(frame, output_path)
            print(f"[ok] {symbol}: {len(frame)} filas -> {output_path}")
        except Exception as exc:  # pragma: no cover - CLI boundary
            message = f"{type(exc).__name__}: {exc}"
            failures.append((symbol, message))
            print(f"[error] {symbol}: {message}")
            if args.fail_fast:
                break

    if failures:
        print("\nDescargas fallidas:")
        for symbol, message in failures:
            print(f"- {symbol}: {message}")
        return 1

    return 0
