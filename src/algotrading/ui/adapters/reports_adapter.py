from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True)
class ReportFile:
    label: str
    path: Path
    mime: str


def collect_experiment_report_files(experiment_dir: Path | str) -> list[ReportFile]:
    root = Path(experiment_dir)
    files: list[ReportFile] = []
    for path in [root / "config.json", root / "metadata.json", root / "summary.csv", root / "notes.md"]:
        if path.exists():
            files.append(_report_file(path))
    for symbol_dir in sorted(child for child in root.iterdir() if child.is_dir()):
        for filename in [
            "report.md",
            "equity_drawdown.html",
            "metrics.json",
            "metrics_table.csv",
            "monthly_returns.csv",
            "period_extremes.csv",
            "exposure.csv",
            "equity.csv",
            "trades.csv",
            "orders.csv",
        ]:
            path = symbol_dir / filename
            if path.exists():
                files.append(_report_file(path, label=f"{symbol_dir.name}/{filename}"))
    return files


def build_experiment_zip(experiment_dir: Path | str) -> bytes:
    root = Path(experiment_dir).resolve()
    if not root.exists():
        raise FileNotFoundError(f"No existe la carpeta: {root}")
    if not (root / "summary.csv").exists():
        raise ValueError("No parece ser una carpeta de experimento valida: falta summary.csv.")

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            archive.write(path, arcname=path.relative_to(root))
    return buffer.getvalue()


def _report_file(path: Path, label: str | None = None) -> ReportFile:
    suffix = path.suffix.lower()
    if suffix == ".json":
        mime = "application/json"
    elif suffix == ".csv":
        mime = "text/csv"
    elif suffix == ".md":
        mime = "text/markdown"
    elif suffix == ".html":
        mime = "text/html"
    else:
        mime = "application/octet-stream"
    return ReportFile(label=label or path.name, path=path, mime=mime)
