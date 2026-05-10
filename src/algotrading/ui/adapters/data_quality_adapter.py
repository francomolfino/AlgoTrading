from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any

import pandas as pd

from algotrading.data.market_calendar import diagnose_calendar_gaps


REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "adj_close", "volume")


@dataclass(frozen=True)
class DataQualityIssue:
    check: str
    severity: str
    message: str
    count: int = 0
    penalty: float = 0.0


@dataclass(frozen=True)
class AdvancedDataQualityReport:
    symbol: str
    interval: str
    asset_type: str
    calendar: str
    calendar_provider: str
    calendar_precision: str
    calendar_early_closes: tuple[str, ...]
    rows: int
    start_date: str
    end_date: str
    score: float
    severity: str
    issues: tuple[DataQualityIssue, ...]

    @property
    def is_usable(self) -> bool:
        return self.severity != "critical"


def build_advanced_data_quality_report(
    frame: pd.DataFrame,
    *,
    symbol: str = "",
    interval: str = "1d",
) -> AdvancedDataQualityReport:
    data = frame.copy()
    asset_type = infer_asset_type(symbol)
    issues: list[DataQualityIssue] = []
    rows = int(len(data))
    start_date, end_date = _date_bounds(data)

    missing_columns = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing_columns:
        issues.append(
            DataQualityIssue(
                check="columnas requeridas",
                severity="critical",
                message="Faltan columnas: " + ", ".join(missing_columns),
                count=len(missing_columns),
                penalty=35,
            )
        )

    if rows == 0:
        issues.append(
            DataQualityIssue(
                check="filas",
                severity="critical",
                message="El dataset esta vacio.",
                penalty=50,
            )
        )
        return _final_report(symbol, interval, asset_type, rows, start_date, end_date, issues, None)

    dates = _dates(data)
    if dates.isna().any():
        issues.append(
            DataQualityIssue(
                check="fechas invalidas",
                severity="critical",
                message="Hay fechas que no se pudieron convertir.",
                count=int(dates.isna().sum()),
                penalty=25,
            )
        )
    duplicate_dates = int(dates.duplicated().sum()) if not dates.empty else 0
    if duplicate_dates:
        issues.append(
            DataQualityIssue(
                check="fechas duplicadas",
                severity="critical",
                message="Hay fechas duplicadas; el backtest podria contar barras dos veces.",
                count=duplicate_dates,
                penalty=min(30, duplicate_dates * 5),
            )
        )

    _add_null_issues(data, issues)
    calendar_diagnostic = diagnose_calendar_gaps(
        dates,
        asset_type=asset_type,
        interval=interval,
        symbol=symbol,
    )
    _add_gap_issues(calendar_diagnostic, issues)
    _add_ohlc_issues(data, issues)
    _add_outlier_issues(data, issues, asset_type=asset_type)
    _add_volume_issues(data, issues, asset_type=asset_type)
    _add_adjusted_close_issues(data, issues)

    return _final_report(symbol, interval, asset_type, rows, start_date, end_date, issues, calendar_diagnostic)


def diagnose_asset_mix(symbols: list[str] | tuple[str, ...]) -> DataQualityIssue | None:
    types = {infer_asset_type(symbol) for symbol in symbols if symbol}
    if "crypto" in types and len(types) > 1:
        return DataQualityIssue(
            check="mezcla de activos",
            severity="warning",
            message="Estas mezclando cripto con ETFs/acciones; los calendarios y gaps no son equivalentes.",
            count=len(symbols),
            penalty=5,
        )
    return None


def advanced_quality_frame(report: AdvancedDataQualityReport) -> pd.DataFrame:
    if not report.issues:
        return pd.DataFrame(
            [
                {
                    "check": "estado",
                    "severity": "ok",
                    "message": "No se detectaron problemas relevantes.",
                    "count": 0,
                    "penalty": 0.0,
                }
            ]
        )
    return pd.DataFrame([asdict(issue) for issue in report.issues])


def advanced_quality_to_dict(report: AdvancedDataQualityReport) -> dict[str, Any]:
    payload = asdict(report)
    payload["issues"] = [asdict(issue) for issue in report.issues]
    return payload


def advanced_quality_from_dict(payload: dict[str, Any]) -> AdvancedDataQualityReport | None:
    if not payload:
        return None
    issues = tuple(DataQualityIssue(**item) for item in payload.get("issues", []))
    return AdvancedDataQualityReport(
        symbol=str(payload.get("symbol", "")),
        interval=str(payload.get("interval", "")),
        asset_type=str(payload.get("asset_type", "unknown")),
        calendar=str(payload.get("calendar", "unknown")),
        calendar_provider=str(payload.get("calendar_provider", "unknown")),
        calendar_precision=str(payload.get("calendar_precision", "unknown")),
        calendar_early_closes=tuple(str(value) for value in payload.get("calendar_early_closes", [])),
        rows=int(payload.get("rows", 0) or 0),
        start_date=str(payload.get("start_date", "n/a")),
        end_date=str(payload.get("end_date", "n/a")),
        score=float(payload.get("score", 0.0) or 0.0),
        severity=str(payload.get("severity", "warning")),
        issues=issues,
    )


def infer_asset_type(symbol: str | None) -> str:
    value = (symbol or "").upper()
    if value.endswith("-USD") or value.endswith("USDT") or value in {"BTC", "ETH", "SOL", "ADA"}:
        return "crypto"
    if value.endswith("=F"):
        return "futures"
    if value:
        return "traditional"
    return "unknown"


def _final_report(
    symbol: str,
    interval: str,
    asset_type: str,
    rows: int,
    start_date: str,
    end_date: str,
    issues: list[DataQualityIssue],
    calendar_diagnostic,
) -> AdvancedDataQualityReport:
    score = max(0.0, min(100.0, 100.0 - sum(issue.penalty for issue in issues)))
    if any(issue.severity == "critical" for issue in issues) or score < 50:
        severity = "critical"
    elif any(issue.severity == "warning" for issue in issues) or score < 85:
        severity = "warning"
    else:
        severity = "ok"
    return AdvancedDataQualityReport(
        symbol=symbol,
        interval=interval,
        asset_type=asset_type,
        calendar=calendar_diagnostic.calendar_key if calendar_diagnostic else "unknown",
        calendar_provider=calendar_diagnostic.provider if calendar_diagnostic else "unknown",
        calendar_precision=calendar_diagnostic.precision if calendar_diagnostic else "unknown",
        calendar_early_closes=calendar_diagnostic.early_closes if calendar_diagnostic else (),
        rows=rows,
        start_date=start_date,
        end_date=end_date,
        score=round(score, 1),
        severity=severity,
        issues=tuple(issues),
    )


def _dates(frame: pd.DataFrame) -> pd.Series:
    if "date" not in frame:
        return pd.Series(dtype="datetime64[ns]")
    return pd.to_datetime(frame["date"], errors="coerce")


def _date_bounds(frame: pd.DataFrame) -> tuple[str, str]:
    dates = _dates(frame).dropna()
    if dates.empty:
        return "n/a", "n/a"
    return dates.min().strftime("%Y-%m-%d"), dates.max().strftime("%Y-%m-%d")


def _numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce")


def _add_null_issues(frame: pd.DataFrame, issues: list[DataQualityIssue]) -> None:
    columns = [column for column in REQUIRED_COLUMNS if column in frame.columns]
    null_counts = {column: int(frame[column].isna().sum()) for column in columns}
    null_counts = {column: count for column, count in null_counts.items() if count > 0}
    if null_counts:
        total = sum(null_counts.values())
        issues.append(
            DataQualityIssue(
                check="nulos",
                severity="critical" if any(column != "volume" for column in null_counts) else "warning",
                message="Valores nulos por columna: " + ", ".join(f"{key}={value}" for key, value in null_counts.items()),
                count=total,
                penalty=min(30, total * 3),
            )
        )


def _add_gap_issues(calendar_diagnostic, issues: list[DataQualityIssue]) -> None:
    missing_count = len(calendar_diagnostic.missing_dates)
    unexpected_count = len(calendar_diagnostic.unexpected_dates)
    if missing_count:
        preview = ", ".join(calendar_diagnostic.missing_dates[:8])
        suffix = "..." if missing_count > 8 else ""
        issues.append(
            DataQualityIssue(
                check="calendario",
                severity="warning",
                message=(
                    f"Faltan {missing_count} fecha(s) esperadas por calendario. "
                    f"Calendario usado: {calendar_diagnostic.calendar_key}. "
                    f"Fuente: {calendar_diagnostic.provider}. Precision: {calendar_diagnostic.precision}. "
                    f"{calendar_diagnostic.note} Ejemplos: {preview}{suffix}"
                ),
                count=missing_count,
                penalty=min(25, missing_count * 3),
            )
        )
    elif calendar_diagnostic.calendar_key:
        issues.append(
            DataQualityIssue(
                check="calendario",
                severity="info",
                message=(
                    f"Calendario usado: {calendar_diagnostic.calendar_key}. "
                    f"Fuente: {calendar_diagnostic.provider}. Precision: {calendar_diagnostic.precision}. "
                    f"{calendar_diagnostic.note} Fechas esperadas: {calendar_diagnostic.expected_count}."
                ),
                count=0,
                penalty=0,
            )
        )
    if unexpected_count:
        preview = ", ".join(calendar_diagnostic.unexpected_dates[:8])
        suffix = "..." if unexpected_count > 8 else ""
        issues.append(
            DataQualityIssue(
                check="fechas fuera de calendario",
                severity="warning",
                message=(
                    f"Hay {unexpected_count} fecha(s) fuera del calendario esperado. "
                    f"Calendario usado: {calendar_diagnostic.calendar_key}. "
                    f"Fuente: {calendar_diagnostic.provider}. Ejemplos: {preview}{suffix}"
                ),
                count=unexpected_count,
                penalty=min(20, unexpected_count * 2),
            )
        )


def _add_ohlc_issues(frame: pd.DataFrame, issues: list[DataQualityIssue]) -> None:
    if not {"open", "high", "low", "close"}.issubset(frame.columns):
        return
    open_ = _numeric(frame, "open")
    high = _numeric(frame, "high")
    low = _numeric(frame, "low")
    close = _numeric(frame, "close")
    invalid = (high < low) | (high < open_) | (high < close) | (low > open_) | (low > close)
    count = int(invalid.fillna(False).sum())
    if count:
        issues.append(
            DataQualityIssue(
                check="OHLC inconsistente",
                severity="critical",
                message="Hay barras donde high/low no contienen open y close.",
                count=count,
                penalty=min(35, count * 6),
            )
        )


def _add_outlier_issues(frame: pd.DataFrame, issues: list[DataQualityIssue], *, asset_type: str) -> None:
    price_column = "adj_close" if "adj_close" in frame.columns else "close"
    prices = _numeric(frame, price_column)
    returns = prices.pct_change(fill_method=None).replace([math.inf, -math.inf], pd.NA).dropna()
    if returns.empty:
        return
    threshold = 0.60 if asset_type == "crypto" else 0.35
    count = int((returns.abs() > threshold).sum())
    if count:
        issues.append(
            DataQualityIssue(
                check="outliers de retorno",
                severity="warning",
                message=f"Hay {count} retornos diarios mayores a {threshold:.0%} en valor absoluto.",
                count=count,
                penalty=min(20, count * 5),
            )
        )


def _add_volume_issues(frame: pd.DataFrame, issues: list[DataQualityIssue], *, asset_type: str) -> None:
    if "volume" not in frame.columns:
        return
    volume = _numeric(frame, "volume")
    non_positive = int((volume <= 0).fillna(False).sum())
    if non_positive:
        issues.append(
            DataQualityIssue(
                check="volumen sospechoso",
                severity="warning",
                message="Hay barras con volumen cero o negativo.",
                count=non_positive,
                penalty=min(15, non_positive * (1 if asset_type == "crypto" else 3)),
            )
        )
    positive = volume[volume > 0].dropna()
    if len(positive) >= 20:
        median = float(positive.median())
        if median > 0:
            spikes = int((positive > median * 25).sum())
            if spikes:
                issues.append(
                    DataQualityIssue(
                        check="spikes de volumen",
                        severity="info",
                        message="Hay volumen muy superior a la mediana; puede ser real, pero conviene revisarlo.",
                        count=spikes,
                        penalty=min(5, spikes),
                    )
                )


def _add_adjusted_close_issues(frame: pd.DataFrame, issues: list[DataQualityIssue]) -> None:
    if not {"close", "adj_close"}.issubset(frame.columns):
        return
    close = _numeric(frame, "close")
    adjusted = _numeric(frame, "adj_close")
    ratio = (close / adjusted).replace([math.inf, -math.inf], pd.NA).dropna()
    if ratio.empty:
        return
    max_diff = float((ratio - 1).abs().max())
    if max_diff > 0.10:
        issues.append(
            DataQualityIssue(
                check="close vs adjusted close",
                severity="info",
                message=f"Close y adjusted close difieren hasta {max_diff:.1%}. Puede deberse a dividendos/splits.",
                count=int(((ratio - 1).abs() > 0.10).sum()),
                penalty=2,
            )
        )
