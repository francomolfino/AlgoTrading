from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]
CANONICAL_COLUMNS = ["date", "open", "high", "low", "close", "adj_close", "volume"]
NUMERIC_COLUMNS = ["open", "high", "low", "close", "adj_close", "volume"]

_COLUMN_ALIASES = {
    "date": "date",
    "datetime": "date",
    "open": "open",
    "high": "high",
    "low": "low",
    "close": "close",
    "adj close": "adj_close",
    "adj_close": "adj_close",
    "adjusted close": "adj_close",
    "volume": "volume",
}


class ValidationError(ValueError):
    """Error de contrato de datos OHLCV."""


def normalize_ohlcv_dataframe(frame: pd.DataFrame) -> pd.DataFrame:
    """Convierte datos OHLCV a un esquema estable para el resto del proyecto."""
    if frame.empty:
        raise ValidationError("El DataFrame esta vacio.")

    normalized = _ensure_date_column(frame.copy())
    normalized = _rename_columns(normalized)

    missing = [column for column in REQUIRED_COLUMNS if column not in normalized.columns]
    if missing:
        raise ValidationError(f"Faltan columnas requeridas: {', '.join(missing)}")

    if "adj_close" not in normalized.columns:
        normalized["adj_close"] = normalized["close"]

    normalized = normalized[CANONICAL_COLUMNS].copy()
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce").dt.tz_localize(None)

    for column in NUMERIC_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")

    normalized = normalized.sort_values("date").reset_index(drop=True)
    validate_ohlcv_dataframe(normalized)
    return normalized


def validate_ohlcv_dataframe(frame: pd.DataFrame) -> None:
    """Valida que los datos tengan el contrato minimo para analizar y backtestear."""
    if frame.empty:
        raise ValidationError("El DataFrame esta vacio.")

    missing = [column for column in CANONICAL_COLUMNS if column not in frame.columns]
    if missing:
        raise ValidationError(f"Faltan columnas requeridas: {', '.join(missing)}")

    null_columns = [
        column for column in CANONICAL_COLUMNS if frame[column].isna().any()
    ]
    if null_columns:
        raise ValidationError(f"Hay valores nulos en: {', '.join(null_columns)}")

    if frame["date"].duplicated().any():
        raise ValidationError("Hay fechas duplicadas.")

    if not frame["date"].is_monotonic_increasing:
        raise ValidationError("Las fechas deben estar ordenadas de menor a mayor.")

    if (frame["high"] < frame["low"]).any():
        raise ValidationError("Hay filas con high menor que low.")

    if (frame["volume"] < 0).any():
        raise ValidationError("Hay volumen negativo.")


def _ensure_date_column(frame: pd.DataFrame) -> pd.DataFrame:
    if _has_date_like_column(frame):
        return frame

    index_name = frame.index.name or "date"
    if isinstance(frame.index, pd.DatetimeIndex):
        return frame.reset_index(names=index_name)

    raise ValidationError("No se encontro columna de fecha ni indice DatetimeIndex.")


def _has_date_like_column(frame: pd.DataFrame) -> bool:
    normalized_names = {_normalize_column_name(column) for column in frame.columns}
    return "date" in normalized_names or "datetime" in normalized_names


def _rename_columns(frame: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in frame.columns:
        normalized_name = _normalize_column_name(column)
        if normalized_name in _COLUMN_ALIASES:
            rename_map[column] = _COLUMN_ALIASES[normalized_name]
    return frame.rename(columns=rename_map)


def _normalize_column_name(column: object) -> str:
    return str(column).strip().lower().replace("_", " ")
