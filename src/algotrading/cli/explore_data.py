from __future__ import annotations

import argparse
from pathlib import Path

from algotrading.analysis.exploration import (
    moving_average_columns,
    prepare_exploration_frame,
    summarize_exploration,
)
from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.visualization.plots import plot_price_volume_with_moving_averages


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analisis exploratorio: retornos, medias moviles y grafico precio/volumen."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument(
        "--symbol",
        help="Ticker ya descargado en data/raw, por ejemplo SPY o BTC-USD.",
    )
    source.add_argument(
        "--input",
        help="Ruta directa a un CSV/parquet OHLCV.",
    )
    parser.add_argument(
        "--data-dir",
        default="data/raw",
        help="Directorio de datos crudos cuando se usa --symbol.",
    )
    parser.add_argument(
        "--interval",
        default="1d",
        help="Intervalo usado en el nombre del archivo, por ejemplo 1d.",
    )
    parser.add_argument(
        "--windows",
        nargs="+",
        type=int,
        default=[20, 50, 200],
        help="Ventanas de medias moviles simples.",
    )
    parser.add_argument(
        "--price-column",
        default="adj_close",
        choices=("adj_close", "close"),
        help="Columna de precio para retornos y medias moviles.",
    )
    parser.add_argument(
        "--processed-dir",
        default="data/processed",
        help="Directorio para guardar datos enriquecidos.",
    )
    parser.add_argument(
        "--figures-dir",
        default="reports/figures",
        help="Directorio para guardar graficos.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    input_path = Path(args.input) if args.input else _find_symbol_file(
        data_dir=Path(args.data_dir),
        symbol=args.symbol,
        interval=args.interval,
    )

    frame = load_ohlcv(input_path)
    explored = prepare_exploration_frame(
        frame,
        windows=args.windows,
        price_column=args.price_column,
    )

    label = _output_label(args.symbol, input_path)
    processed_path = _processed_path(
        output_dir=Path(args.processed_dir),
        label=label,
        interval=args.interval,
    )
    figure_path = _figure_path(
        output_dir=Path(args.figures_dir),
        label=label,
        interval=args.interval,
    )

    processed_path.parent.mkdir(parents=True, exist_ok=True)
    figure_path.parent.mkdir(parents=True, exist_ok=True)
    explored.to_csv(processed_path, index=False)

    figure = plot_price_volume_with_moving_averages(
        explored,
        title=f"{label} - precio, volumen y medias moviles",
        ma_columns=moving_average_columns(args.windows),
        price_column=args.price_column,
    )
    figure.savefig(figure_path, dpi=140, bbox_inches="tight")

    summary = summarize_exploration(explored, price_column=args.price_column)
    _print_summary(summary, processed_path, figure_path)
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


def _processed_path(output_dir: Path, label: str, interval: str) -> Path:
    interval_label = safe_filename_part(interval)
    return output_dir / f"{label}_{interval_label}_exploration.csv"


def _figure_path(output_dir: Path, label: str, interval: str) -> Path:
    interval_label = safe_filename_part(interval)
    return output_dir / f"{label}_{interval_label}_exploration.png"


def _print_summary(
    summary: dict[str, float | int | str],
    processed_path: Path,
    figure_path: Path,
) -> None:
    print(f"[ok] datos enriquecidos -> {processed_path}")
    print(f"[ok] grafico -> {figure_path}")
    print("\nResumen:")
    print(f"- periodo: {summary['start_date']} a {summary['end_date']}")
    print(f"- filas: {summary['rows']}")
    print(f"- precio inicial/final: {summary['first_price']:.2f} -> {summary['last_price']:.2f}")
    print(f"- retorno total simple: {summary['total_return']:.2%}")
    print(f"- retorno diario promedio: {summary['average_daily_return']:.4%}")
    print(f"- mejor/peor dia: {summary['best_daily_return']:.2%} / {summary['worst_daily_return']:.2%}")
