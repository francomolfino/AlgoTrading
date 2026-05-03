from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from algotrading.data.schema import normalize_ohlcv_dataframe, validate_ohlcv_dataframe

SUPPORTED_FORMATS = {"csv", "parquet"}


def build_data_path(
    output_dir: Path | str,
    symbol: str,
    interval: str,
    file_format: str,
) -> Path:
    file_format = file_format.lower()
    if file_format not in SUPPORTED_FORMATS:
        raise ValueError(f"Formato no soportado: {file_format}")

    filename = f"{safe_filename_part(symbol)}_{safe_filename_part(interval)}.{file_format}"
    return Path(output_dir) / filename


def save_ohlcv(frame: pd.DataFrame, path: Path | str) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    normalized = normalize_ohlcv_dataframe(frame)
    suffix = output_path.suffix.lower()

    if suffix == ".csv":
        normalized.to_csv(output_path, index=False)
    elif suffix == ".parquet":
        normalized.to_parquet(output_path, index=False)
    else:
        raise ValueError(f"Extension no soportada: {suffix}")

    return output_path


def load_ohlcv(path: Path | str) -> pd.DataFrame:
    input_path = Path(path)
    suffix = input_path.suffix.lower()

    if suffix == ".csv":
        frame = pd.read_csv(input_path, parse_dates=["date"])
    elif suffix == ".parquet":
        frame = pd.read_parquet(input_path)
    else:
        raise ValueError(f"Extension no soportada: {suffix}")

    validate_ohlcv_dataframe(frame)
    return frame


def safe_filename_part(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().upper()).strip("_")
    if not safe:
        raise ValueError("El nombre de archivo resultante esta vacio.")
    return safe
