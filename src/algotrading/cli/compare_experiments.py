from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from algotrading.experiments import compare_experiments, find_experiment_dirs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compara experimentos ya ejecutados.")
    parser.add_argument(
        "--experiments-root",
        default="experiments",
        help="Carpeta raiz donde buscar experimentos.",
    )
    parser.add_argument(
        "--experiment-dirs",
        nargs="*",
        default=None,
        help="Carpetas concretas a comparar. Si se omite, busca en --experiments-root.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="CSV de salida. Por defecto: <experiments-root>/comparison.csv",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    experiment_dirs = (
        [Path(path) for path in args.experiment_dirs]
        if args.experiment_dirs
        else find_experiment_dirs(args.experiments_root)
    )
    comparison = compare_experiments(experiment_dirs)
    output_path = Path(args.output) if args.output else Path(args.experiments_root) / "comparison.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(output_path, index=False)
    _print_comparison(comparison, output_path)
    return 0


def _print_comparison(comparison: pd.DataFrame, output_path: Path) -> None:
    print(f"[ok] comparacion -> {output_path}")
    if comparison.empty:
        print("No encontre experimentos para comparar.")
        return

    columns = [
        "experiment_name",
        "run_id",
        "symbol",
        "strategy",
        "total_return",
        "max_drawdown",
        "sharpe_ratio",
        "excess_return_vs_benchmark",
    ]
    display = comparison[[column for column in columns if column in comparison.columns]].copy()
    for column in ["total_return", "max_drawdown", "excess_return_vs_benchmark"]:
        if column in display.columns:
            display[column] = display[column].map(_format_percent)
    if "sharpe_ratio" in display.columns:
        display["sharpe_ratio"] = display["sharpe_ratio"].map(_format_float)
    print("\nComparacion:")
    print(display.to_string(index=False))


def _format_percent(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2%}"


def _format_float(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2f}"
