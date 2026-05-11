from __future__ import annotations

import argparse
from pathlib import Path

from algotrading.backtesting import run_backtest_correctness_audit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ejecuta la auditoria de correctness del backtester y genera un reporte Markdown."
    )
    parser.add_argument(
        "--report-path",
        default="reports/backtest_correctness_audit.md",
        help="Ruta del reporte Markdown generado.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_backtest_correctness_audit(report_path=Path(args.report_path))
    for check in result.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"[{status}] {check.name}: {check.detail}")
    print(f"[ok] reporte -> {result.report_path}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
