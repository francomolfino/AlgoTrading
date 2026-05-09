from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from algotrading.data.schema import CANONICAL_COLUMNS, ValidationError, validate_ohlcv_dataframe
from algotrading.data.storage import build_data_path, load_ohlcv, save_ohlcv
from algotrading.data.yahoo import download_ohlcv


@dataclass(frozen=True)
class DataAsset:
    symbol_hint: str
    interval: str
    file_format: str
    path: Path
    rows: int
    start_date: str
    end_date: str


@dataclass(frozen=True)
class DataQualityReport:
    rows: int
    start_date: str
    end_date: str
    missing_columns: tuple[str, ...]
    null_counts: dict[str, int]
    duplicate_dates: int
    gap_count: int
    max_gap_days: int
    suspicious_rows: int
    is_valid: bool
    message: str


def parse_symbols(raw: str) -> list[str]:
    symbols = [part.strip().upper() for part in raw.replace(",", " ").split()]
    return list(dict.fromkeys(symbol for symbol in symbols if symbol))


def list_data_assets(data_dir: Path | str, interval: str | None = None) -> list[DataAsset]:
    root = Path(data_dir)
    if not root.exists():
        return []

    assets: list[DataAsset] = []
    for path in sorted([*root.glob("*.csv"), *root.glob("*.parquet")]):
        parsed = _parse_data_filename(path)
        if parsed is None:
            continue
        symbol_hint, parsed_interval = parsed
        if interval is not None and parsed_interval.lower() != interval.lower():
            continue
        try:
            frame = load_ohlcv(path)
        except Exception:
            assets.append(
                DataAsset(
                    symbol_hint=symbol_hint,
                    interval=parsed_interval,
                    file_format=path.suffix.lstrip("."),
                    path=path,
                    rows=0,
                    start_date="error",
                    end_date="error",
                )
            )
            continue
        assets.append(
            DataAsset(
                symbol_hint=symbol_hint,
                interval=parsed_interval,
                file_format=path.suffix.lstrip("."),
                path=path,
                rows=int(len(frame)),
                start_date=_date_string(frame["date"].iloc[0]),
                end_date=_date_string(frame["date"].iloc[-1]),
            )
        )
    return assets


def assets_frame(assets: list[DataAsset]) -> pd.DataFrame:
    return pd.DataFrame([asset.__dict__ for asset in assets])


def find_data_file(data_dir: Path | str, symbol: str, interval: str = "1d") -> Path:
    root = Path(data_dir)
    csv_path = build_data_path(root, symbol, interval, "csv")
    parquet_path = build_data_path(root, symbol, interval, "parquet")
    if csv_path.exists():
        return csv_path
    if parquet_path.exists():
        return parquet_path
    raise FileNotFoundError(f"No encontre datos para {symbol}: {csv_path} o {parquet_path}.")


def load_symbol_data(
    data_dir: Path | str,
    symbol: str,
    interval: str = "1d",
) -> tuple[pd.DataFrame, Path]:
    path = find_data_file(data_dir, symbol, interval)
    return load_ohlcv(path), path


def load_data_file(path: Path | str) -> pd.DataFrame:
    return load_ohlcv(path)


def download_and_save(
    symbol: str,
    start: str,
    end: str | None,
    interval: str,
    data_dir: Path | str,
    file_format: str = "csv",
) -> tuple[pd.DataFrame, Path]:
    frame = download_ohlcv(symbol=symbol, start=start, end=end, interval=interval)
    output_path = build_data_path(data_dir, symbol, interval, file_format)
    save_ohlcv(frame, output_path)
    return frame, output_path


def filter_by_dates(
    frame: pd.DataFrame,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    data = frame.copy()
    dates = pd.to_datetime(data["date"], errors="coerce")
    if start:
        data = data.loc[dates >= pd.Timestamp(start)]
        dates = pd.to_datetime(data["date"], errors="coerce")
    if end:
        data = data.loc[dates <= pd.Timestamp(end)]
    return data.reset_index(drop=True)


def validate_data_quality(frame: pd.DataFrame) -> DataQualityReport:
    missing_columns = tuple(column for column in CANONICAL_COLUMNS if column not in frame.columns)
    duplicate_dates = _duplicate_dates(frame)
    null_counts = {
        column: int(frame[column].isna().sum()) for column in frame.columns if frame[column].isna().any()
    }
    gap_count, max_gap_days = _date_gaps(frame)
    suspicious_rows = _suspicious_ohlcv_rows(frame)

    is_valid = True
    message = "Datos validos."
    try:
        validate_ohlcv_dataframe(frame)
    except ValidationError as exc:
        is_valid = False
        message = str(exc)

    return DataQualityReport(
        rows=int(len(frame)),
        start_date=_safe_boundary_date(frame, first=True),
        end_date=_safe_boundary_date(frame, first=False),
        missing_columns=missing_columns,
        null_counts=null_counts,
        duplicate_dates=duplicate_dates,
        gap_count=gap_count,
        max_gap_days=max_gap_days,
        suspicious_rows=suspicious_rows,
        is_valid=is_valid,
        message=message,
    )


def data_summary(frame: pd.DataFrame) -> pd.DataFrame:
    columns = [column for column in ["open", "high", "low", "close", "adj_close", "volume"] if column in frame]
    if not columns:
        return pd.DataFrame()
    return frame[columns].describe().T.reset_index(names="column")


def quality_report_frame(report: DataQualityReport) -> pd.DataFrame:
    frame = pd.DataFrame(
        [
            {"check": "filas", "value": report.rows},
            {"check": "fecha inicial", "value": report.start_date},
            {"check": "fecha final", "value": report.end_date},
            {"check": "columnas faltantes", "value": ", ".join(report.missing_columns) or "ninguna"},
            {"check": "fechas duplicadas", "value": report.duplicate_dates},
            {"check": "gaps grandes", "value": report.gap_count},
            {"check": "max gap dias", "value": report.max_gap_days},
            {"check": "filas sospechosas OHLCV", "value": report.suspicious_rows},
            {"check": "estado", "value": "ok" if report.is_valid else "revisar"},
            {"check": "mensaje", "value": report.message},
        ]
    )
    frame["value"] = frame["value"].astype(str)
    return frame


def _parse_data_filename(path: Path) -> tuple[str, str] | None:
    stem = path.stem
    if "_" not in stem:
        return None
    symbol_part, interval = stem.rsplit("_", maxsplit=1)
    return symbol_part, interval.lower()


def _date_string(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _safe_boundary_date(frame: pd.DataFrame, first: bool) -> str:
    if frame.empty or "date" not in frame:
        return "n/a"
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if dates.empty:
        return "n/a"
    return _date_string(dates.iloc[0 if first else -1])


def _duplicate_dates(frame: pd.DataFrame) -> int:
    if "date" not in frame:
        return 0
    dates = pd.to_datetime(frame["date"], errors="coerce")
    return int(dates.duplicated().sum())


def _date_gaps(frame: pd.DataFrame) -> tuple[int, int]:
    if "date" not in frame or len(frame) < 2:
        return 0, 0
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna().sort_values()
    gaps = dates.diff().dt.days.dropna()
    large_gaps = gaps[gaps > 4]
    return int(len(large_gaps)), int(large_gaps.max()) if len(large_gaps) else 0


def _suspicious_ohlcv_rows(frame: pd.DataFrame) -> int:
    required = {"open", "high", "low", "close", "volume"}
    if not required.issubset(frame.columns):
        return 0
    numeric = frame[list(required)].apply(pd.to_numeric, errors="coerce")
    suspicious = (
        (numeric["high"] < numeric["low"])
        | (numeric["open"] > numeric["high"])
        | (numeric["open"] < numeric["low"])
        | (numeric["close"] > numeric["high"])
        | (numeric["close"] < numeric["low"])
        | (numeric["volume"] < 0)
    )
    return int(suspicious.sum())
