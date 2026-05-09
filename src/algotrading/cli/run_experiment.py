from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from algotrading.experiments import run_experiment_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ejecuta un experimento reproducible desde una config JSON."
    )
    parser.add_argument("--config", required=True, help="Ruta a la config JSON del experimento.")
    parser.add_argument(
        "--output-root",
        default=None,
        help="Carpeta raiz de experimentos. Si se omite, usa output_root de la config.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_experiment_config(
        config_path=Path(args.config),
        output_root=Path(args.output_root) if args.output_root else None,
    )
    _print_summary(result.experiment_dir, result.summary)
    return 0


def _print_summary(experiment_dir: Path, summary: pd.DataFrame) -> None:
    print(f"[ok] experimento -> {experiment_dir}")
    print(f"[ok] config -> {experiment_dir / 'config.json'}")
    print(f"[ok] metadata -> {experiment_dir / 'metadata.json'}")
    print(f"[ok] resumen -> {experiment_dir / 'summary.csv'}")

    display = summary[
        [
            "symbol",
            "strategy",
            "total_return",
            "cagr",
            "sharpe_ratio",
            "max_drawdown",
            "number_of_trades",
            "excess_return_vs_benchmark",
        ]
    ].copy()
    for column in ["total_return", "cagr", "max_drawdown", "excess_return_vs_benchmark"]:
        display[column] = display[column].map(_format_percent)
    display["sharpe_ratio"] = display["sharpe_ratio"].map(_format_float)
    print("\nResumen:")
    print(display.to_string(index=False))


def _format_percent(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2%}"


def _format_float(value: float | int) -> str:
    return "n/a" if pd.isna(value) else f"{value:.2f}"
