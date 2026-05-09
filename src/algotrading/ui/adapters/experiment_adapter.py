from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
from typing import Any

import pandas as pd

from algotrading.experiments.compare import compare_experiments, find_experiment_dirs
from algotrading.ui.adapters.backtest_adapter import metrics_frame


@dataclass(frozen=True)
class ExperimentRecord:
    path: Path
    name: str
    run_id: str
    created_at: str
    strategy: str
    symbols: tuple[str, ...]
    total_return: float | None
    sharpe_ratio: float | None
    max_drawdown: float | None


@dataclass(frozen=True)
class ExperimentDetails:
    path: Path
    config: dict[str, Any]
    metadata: dict[str, Any]
    summary: pd.DataFrame
    symbol: str | None
    equity: pd.DataFrame
    trades: pd.DataFrame
    orders: pd.DataFrame
    metrics: dict[str, float | int]
    metrics_table: pd.DataFrame
    monthly_returns: pd.DataFrame
    period_extremes: pd.DataFrame
    exposure: pd.DataFrame
    notes: str


def list_experiments(root: Path | str) -> list[ExperimentRecord]:
    records: list[ExperimentRecord] = []
    for directory in find_experiment_dirs(root):
        config = _read_json(directory / "config.json")
        metadata = _read_json(directory / "metadata.json")
        summary = _safe_read_csv(directory / "summary.csv")
        first_row = summary.iloc[0].to_dict() if not summary.empty else {}
        strategy_config = config.get("strategy", {})
        records.append(
            ExperimentRecord(
                path=directory,
                name=str(config.get("experiment_name", directory.name)),
                run_id=str(config.get("run_id", directory.name)),
                created_at=str(metadata.get("created_at_utc", "")),
                strategy=str(first_row.get("strategy") or strategy_config.get("name", "")),
                symbols=tuple(str(symbol) for symbol in config.get("symbols", [])),
                total_return=_optional_float(first_row.get("total_return")),
                sharpe_ratio=_optional_float(first_row.get("sharpe_ratio")),
                max_drawdown=_optional_float(first_row.get("max_drawdown")),
            )
        )
    return sorted(records, key=lambda record: record.created_at or record.run_id, reverse=True)


def records_frame(records: list[ExperimentRecord]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "path": str(record.path),
                "name": record.name,
                "run_id": record.run_id,
                "created_at": record.created_at,
                "strategy": record.strategy,
                "symbols": ", ".join(record.symbols),
                "total_return": record.total_return,
                "sharpe_ratio": record.sharpe_ratio,
                "max_drawdown": record.max_drawdown,
            }
            for record in records
        ]
    )


def filter_records(
    records: list[ExperimentRecord],
    strategy: str | None = None,
    symbol: str | None = None,
) -> list[ExperimentRecord]:
    result = records
    if strategy:
        result = [record for record in result if strategy.lower() in record.strategy.lower()]
    if symbol:
        result = [record for record in result if any(symbol.upper() in item.upper() for item in record.symbols)]
    return result


def sort_records(records: list[ExperimentRecord], by: str, ascending: bool = False) -> list[ExperimentRecord]:
    key_map = {
        "fecha": lambda record: record.created_at or record.run_id,
        "retorno": lambda record: _sort_value(record.total_return),
        "sharpe": lambda record: _sort_value(record.sharpe_ratio),
        "drawdown": lambda record: _sort_value(record.max_drawdown),
        "nombre": lambda record: record.name,
    }
    return sorted(records, key=key_map.get(by, key_map["fecha"]), reverse=not ascending)


def load_experiment_details(path: Path | str, symbol: str | None = None) -> ExperimentDetails:
    directory = Path(path)
    config = _read_json(directory / "config.json")
    metadata = _read_json(directory / "metadata.json")
    summary = _safe_read_csv(directory / "summary.csv")
    symbols = [str(value) for value in config.get("symbols", [])]
    selected_symbol = symbol or (symbols[0] if symbols else _first_symbol_dir(directory))
    symbol_dir = directory / _safe_symbol_dir_name(selected_symbol) if selected_symbol else directory

    metrics = _read_json(symbol_dir / "metrics.json")
    return ExperimentDetails(
        path=directory,
        config=config,
        metadata=metadata,
        summary=summary,
        symbol=selected_symbol,
        equity=_safe_read_csv(symbol_dir / "equity.csv", parse_dates=["date"]),
        trades=_safe_read_csv(symbol_dir / "trades.csv"),
        orders=_safe_read_csv(symbol_dir / "orders.csv"),
        metrics=metrics,
        metrics_table=_safe_read_csv(symbol_dir / "metrics_table.csv"),
        monthly_returns=_safe_read_csv(symbol_dir / "monthly_returns.csv"),
        period_extremes=_safe_read_csv(symbol_dir / "period_extremes.csv"),
        exposure=_safe_read_csv(symbol_dir / "exposure.csv"),
        notes=_read_text(directory / "notes.md"),
    )


def compare_experiment_records(records: list[ExperimentRecord]) -> pd.DataFrame:
    return compare_experiments([record.path for record in records])


def diff_experiment_configs(
    records: list[ExperimentRecord],
    only_changed: bool = True,
) -> pd.DataFrame:
    if len(records) < 2:
        raise ValueError("Selecciona al menos dos experimentos para comparar configs.")

    flattened = {
        record.path.name: _flatten_dict(_read_json(record.path / "config.json"))
        for record in records
    }
    keys = sorted({key for values in flattened.values() for key in values})
    rows = []
    for key in keys:
        row = {"field": key}
        values = []
        for label, config in flattened.items():
            value = config.get(key, "")
            stable_value = _stable_repr(value)
            row[label] = stable_value
            values.append(stable_value)
        row["changed"] = len(set(values)) > 1
        if not only_changed or row["changed"]:
            rows.append(row)
    return pd.DataFrame(rows)


def delete_experiment_dir(
    experiment_dir: Path | str,
    experiments_root: Path | str,
    confirmation: str,
) -> Path:
    target = Path(experiment_dir).resolve()
    root = Path(experiments_root).resolve()
    if root not in target.parents:
        raise ValueError("La carpeta a borrar no esta dentro de experiments_root.")
    if confirmation != target.name:
        raise ValueError("Confirmacion invalida. Escribi exactamente el nombre de la carpeta.")
    if not (target / "summary.csv").exists():
        raise ValueError("No parece ser una carpeta de experimento valida: falta summary.csv.")
    shutil.rmtree(target)
    return target


def load_equity_curves(records: list[ExperimentRecord]) -> dict[str, pd.DataFrame]:
    curves: dict[str, pd.DataFrame] = {}
    for record in records:
        try:
            details = load_experiment_details(record.path)
        except Exception:
            continue
        if details.equity.empty:
            continue
        label = f"{record.name} ({details.symbol})"
        curves[label] = details.equity
    return curves


def critical_reading(details: ExperimentDetails) -> list[str]:
    metrics = details.metrics
    warnings: list[str] = []
    trades = int(metrics.get("number_of_trades") or 0)
    max_drawdown = _optional_float(metrics.get("max_drawdown"))
    sharpe = _optional_float(metrics.get("sharpe_ratio"))
    excess_return = _optional_float(metrics.get("excess_return_vs_benchmark"))

    if trades < 10:
        warnings.append("Hay pocos trades; la muestra es chica para sacar conclusiones fuertes.")
    if max_drawdown is not None and max_drawdown < -0.25:
        warnings.append("El drawdown supera 25%; revisa si sobrevivirias psicologica y financieramente.")
    if sharpe is not None and sharpe > 3:
        warnings.append("Sharpe muy alto: puede ser overfitting, periodo favorable o bug de datos.")
    if excess_return is not None and excess_return < 0:
        warnings.append("La estrategia quedo debajo de buy and hold en este periodo.")
    if len(details.equity) < 252:
        warnings.append("El periodo tiene menos de un ano de barras diarias aproximadas.")
    if len(details.config.get("symbols", [])) <= 1:
        warnings.append("Resultado probado en un solo activo; falta validacion multi-activo.")
    strategy_params = details.config.get("strategy", {}).get("parameters", {})
    if isinstance(strategy_params, dict) and len(strategy_params) > 4:
        warnings.append("Muchos parametros aumentan el riesgo de sobreajuste.")
    return warnings or ["No hay alertas obvias, pero esto no valida rentabilidad futura."]


def details_metrics_frame(details: ExperimentDetails) -> pd.DataFrame:
    if not details.metrics:
        return pd.DataFrame()
    return metrics_frame(details.metrics)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return payload if isinstance(payload, dict) else {}


def _safe_read_csv(path: Path, parse_dates: list[str] | None = None) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=parse_dates)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _optional_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _sort_value(value: float | None) -> float:
    return float("-inf") if value is None else float(value)


def _first_symbol_dir(directory: Path) -> str | None:
    for child in directory.iterdir():
        if child.is_dir() and (child / "equity.csv").exists():
            return child.name
    return None


def _safe_symbol_dir_name(symbol: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in symbol.upper()).strip("_")


def _flatten_dict(payload: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for key, value in payload.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            rows.update(_flatten_dict(value, path))
        elif isinstance(value, list):
            rows[path] = ", ".join(str(item) for item in value)
        else:
            rows[path] = value
    return rows


def _stable_repr(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)
