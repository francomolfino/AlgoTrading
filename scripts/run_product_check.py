from __future__ import annotations

import argparse
from pathlib import Path

from algotrading.product_check import run_product_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ejecuta un flujo offline de validacion end-to-end del producto."
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Carpeta temporal a usar. Si se omite, se crea una carpeta temporal del sistema.",
    )
    parser.add_argument(
        "--report-path",
        default="reports/product_validation_report.md",
        help="Ruta del reporte markdown generado.",
    )
    parser.add_argument(
        "--discard-workspace",
        action="store_true",
        help="Borra la carpeta temporal si el script la creo automaticamente.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_product_check(
        workspace=Path(args.workspace) if args.workspace else None,
        report_path=Path(args.report_path),
        keep_workspace=not args.discard_workspace,
    )
    for step in result.steps:
        status = "PASS" if step.passed else "FAIL"
        print(f"[{status}] {step.name}: {step.detail}")
    print(f"[ok] reporte -> {result.report_path}")
    print(f"[ok] workspace -> {result.workspace}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
