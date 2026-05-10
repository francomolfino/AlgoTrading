from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from algotrading.backtesting import BacktestConfig, BacktestResult, run_backtest
from algotrading.data.storage import safe_filename_part
from algotrading.experiments.runner import collect_environment_metadata
from algotrading.reports import generate_backtest_report
from algotrading.ui.adapters.data_adapter import filter_by_dates, load_symbol_data, validate_data_quality
from algotrading.ui.adapters.risk_adapter import RiskSettings, validate_risk_settings
from algotrading.ui.adapters.strategy_adapter import (
    generate_strategy_signals,
    signal_summary,
    strategy_display_name,
    validate_strategy_parameters,
)


MIN_BACKTEST_BARS_BY_INTERVAL = {
    "1d": 252,
    "1wk": 104,
    "1mo": 36,
}

MIN_NON_BH_ENTRIES = 1
LOW_SIGNAL_SAMPLE_ENTRIES = 5
EXPERIMENT_METADATA_FILENAME = "experiment_metadata.json"


@dataclass(frozen=True)
class BacktestRequest:
    symbol: str
    strategy_key: str
    strategy_parameters: dict[str, int | float]
    data_dir: Path | str = "data/raw"
    interval: str = "1d"
    start: str | None = None
    end: str | None = None
    price_column: str = "adj_close"
    initial_capital: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    risk: RiskSettings = RiskSettings()
    experiment_name: str = "ui_backtest"
    notes: str = ""
    save_experiment: bool = True
    experiments_root: Path | str = "experiments"


@dataclass(frozen=True)
class BacktestRunArtifacts:
    request: BacktestRequest
    result: BacktestResult
    signal_frame: pd.DataFrame
    strategy_name: str
    experiment_dir: Path | None = None
    report_path: Path | None = None


@dataclass(frozen=True)
class BacktestPreflight:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    rows: int = 0
    start_date: str = "n/a"
    end_date: str = "n/a"
    entries: int = 0
    exits: int = 0
    exposure_ratio: float = 0.0

    @property
    def can_run(self) -> bool:
        return not self.errors


def run_backtest_request(request: BacktestRequest) -> BacktestRunArtifacts:
    warnings = validate_backtest_request(request)
    if warnings:
        # Las advertencias se devuelven visualmente desde la UI; aca solo validamos duro.
        pass

    frame, _ = load_symbol_data(request.data_dir, request.symbol, request.interval)
    frame = filter_by_dates(frame, request.start, request.end)
    if len(frame) < 2:
        raise ValueError("El periodo filtrado necesita al menos dos filas.")

    signal_frame = generate_strategy_signals(
        frame,
        strategy_key=request.strategy_key,
        parameters=request.strategy_parameters,
        price_column=request.price_column,
    )
    config = _backtest_config(request)
    result = run_backtest(signal_frame, config=config)
    strategy_name = strategy_display_name(request.strategy_key, request.strategy_parameters)

    experiment_dir = None
    report_path = None
    if request.save_experiment:
        experiment_dir, report_path = save_backtest_experiment(
            request=request,
            result=result,
            signal_frame=signal_frame,
            strategy_name=strategy_name,
        )

    return BacktestRunArtifacts(
        request=request,
        result=result,
        signal_frame=signal_frame,
        strategy_name=strategy_name,
        experiment_dir=experiment_dir,
        report_path=report_path,
    )


def preflight_backtest_request(request: BacktestRequest) -> BacktestPreflight:
    errors: list[str] = []
    warnings: list[str] = []
    rows = 0
    start_date = "n/a"
    end_date = "n/a"
    entries = 0
    exits = 0
    exposure_ratio = 0.0

    try:
        warnings.extend(validate_backtest_request(request))
    except ValueError as exc:
        errors.append(str(exc))
        return BacktestPreflight(errors=tuple(errors), warnings=tuple(warnings))

    try:
        frame, _ = load_symbol_data(request.data_dir, request.symbol, request.interval)
        frame = filter_by_dates(frame, request.start, request.end)
    except Exception as exc:
        errors.append(f"No pude cargar datos para {request.symbol}: {exc}")
        return BacktestPreflight(errors=tuple(errors), warnings=tuple(warnings))

    rows = int(len(frame))
    start_date = _boundary_date(frame, first=True)
    end_date = _boundary_date(frame, first=False)
    if rows == 0:
        errors.append("El periodo seleccionado no tiene datos.")
        return BacktestPreflight(
            errors=tuple(errors),
            warnings=tuple(warnings),
            rows=rows,
            start_date=start_date,
            end_date=end_date,
        )

    quality = validate_data_quality(frame)
    if not quality.is_valid:
        errors.append(f"Datos invalidos: {quality.message}")
    if request.price_column not in frame.columns:
        errors.append(f"Falta la columna de precio seleccionada: {request.price_column}.")

    minimum_bars = minimum_backtest_bars(request.interval)
    if rows < minimum_bars:
        errors.append(
            f"Periodo demasiado corto: {rows} barras. Para {request.interval} usa al menos {minimum_bars}."
        )
    elif rows < int(minimum_bars * 1.5):
        warnings.append("Periodo valido pero justo; las metricas todavia pueden ser inestables.")

    if request.commission_bps == 0 and request.slippage_bps == 0:
        warnings.append("Comision y slippage estan en cero; eso suele sobreestimar resultados.")

    if errors:
        return BacktestPreflight(
            errors=tuple(errors),
            warnings=tuple(warnings),
            rows=rows,
            start_date=start_date,
            end_date=end_date,
        )

    try:
        signal_frame = generate_strategy_signals(
            frame,
            strategy_key=request.strategy_key,
            parameters=request.strategy_parameters,
            price_column=request.price_column,
        )
        summary = signal_summary(signal_frame)
    except Exception as exc:
        errors.append(f"No pude generar senales: {exc}")
        return BacktestPreflight(
            errors=tuple(errors),
            warnings=tuple(warnings),
            rows=rows,
            start_date=start_date,
            end_date=end_date,
        )

    entries = int(summary["entries"])
    exits = int(summary["exits"])
    exposure_ratio = float(summary["exposure_ratio"])
    if request.strategy_key != "buy_and_hold":
        if entries < MIN_NON_BH_ENTRIES:
            errors.append("La estrategia no genera entradas en este periodo. Cambia parametros o periodo.")
        elif entries < LOW_SIGNAL_SAMPLE_ENTRIES:
            warnings.append("Muy pocas entradas; usa el resultado solo como inspeccion preliminar.")
        if exposure_ratio < 0.01:
            warnings.append("Exposicion casi nula; el resultado puede depender de ruido o de cash inmovil.")
        if exposure_ratio > 0.98:
            warnings.append("Exposicion casi permanente; compara especialmente contra buy and hold.")

    return BacktestPreflight(
        errors=tuple(errors),
        warnings=tuple(warnings),
        rows=rows,
        start_date=start_date,
        end_date=end_date,
        entries=entries,
        exits=exits,
        exposure_ratio=exposure_ratio,
    )


def validate_backtest_request(request: BacktestRequest) -> list[str]:
    if not request.symbol.strip():
        raise ValueError("Selecciona un activo.")
    if request.initial_capital <= 0:
        raise ValueError("El capital inicial debe ser mayor a cero.")
    if request.commission_bps < 0:
        raise ValueError("La comision no puede ser negativa.")
    if request.slippage_bps < 0:
        raise ValueError("El slippage no puede ser negativo.")
    warnings = validate_strategy_parameters(request.strategy_key, request.strategy_parameters)
    warnings.extend(validate_risk_settings(request.risk))
    if request.start and request.end and pd.Timestamp(request.start) > pd.Timestamp(request.end):
        raise ValueError("La fecha inicial debe ser anterior a la fecha final.")
    return warnings


def minimum_backtest_bars(interval: str) -> int:
    return MIN_BACKTEST_BARS_BY_INTERVAL.get(interval.lower(), 120)


def metric_cards(metrics: dict[str, float | int]) -> list[tuple[str, str]]:
    return [
        ("Equity final", _format_currency(metrics.get("final_equity"))),
        ("Retorno total", _format_percent(metrics.get("total_return"))),
        ("CAGR", _format_percent(metrics.get("cagr"))),
        ("Sharpe aprox.", _format_number(metrics.get("sharpe_ratio"))),
        ("Max drawdown", _format_percent(metrics.get("max_drawdown"))),
        ("Trades", str(int(metrics.get("number_of_trades", 0)))),
    ]


def build_result_warnings(
    result: BacktestResult,
    parameter_count: int = 0,
    symbol_count: int = 1,
) -> list[str]:
    metrics = result.metrics
    warnings: list[str] = []
    trades = int(metrics.get("number_of_trades", 0))
    max_drawdown = float(metrics.get("max_drawdown", 0))
    sharpe = float(metrics.get("sharpe_ratio", 0))
    excess_return = float(metrics.get("excess_return_vs_benchmark", 0))
    total_return = float(metrics.get("total_return", 0))

    if len(result.equity_curve) < 252:
        warnings.append("Periodo corto: menos de un ano aproximado de barras diarias.")
    if trades < 10:
        warnings.append("Pocos trades: evita conclusiones fuertes sobre una muestra chica.")
    if max_drawdown < -0.25:
        warnings.append("Drawdown alto: revisa si el riesgo es tolerable antes de mirar retorno.")
    if sharpe > 3:
        warnings.append("Sharpe muy alto: revisar posible overfitting, bug de datos o periodo excepcional.")
    if excess_return < 0:
        warnings.append("Perdio contra buy and hold en retorno total durante este periodo.")
    if total_return > 1.0 and trades < 5:
        warnings.append("Retorno muy alto con pocos trades: resultado especialmente sospechoso.")
    if symbol_count <= 1:
        warnings.append("Probado en un solo activo; falta validacion multi-activo.")
    if parameter_count > 4:
        warnings.append("Muchos parametros aumentan el riesgo de sobreajuste.")
    return warnings


def metrics_frame(metrics: dict[str, float | int]) -> pd.DataFrame:
    labels = {
        "initial_capital": "Capital inicial",
        "final_equity": "Equity final",
        "total_return": "Retorno total",
        "cagr": "CAGR",
        "sharpe_ratio": "Sharpe aprox.",
        "max_drawdown": "Max drawdown",
        "win_rate": "Win rate",
        "number_of_trades": "Numero de trades",
        "total_commissions": "Comisiones totales",
        "benchmark_total_return": "Retorno benchmark",
        "benchmark_max_drawdown": "Drawdown benchmark",
        "excess_return_vs_benchmark": "Exceso vs benchmark",
    }
    rows = []
    for key, label in labels.items():
        value = metrics.get(key)
        rows.append({"metric": key, "label": label, "value": value, "formatted": _format_metric(key, value)})
    return pd.DataFrame(rows)


def trade_details_frame(trades: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "trade",
        "entrada",
        "salida",
        "precio_entrada",
        "precio_salida",
        "cantidad",
        "capital_entrada",
        "valor_salida",
        "pnl",
        "roi_pct",
        "barras",
        "motivo_salida",
        "comisiones",
    ]
    if trades.empty:
        return pd.DataFrame(columns=columns)

    required = {
        "entry_date",
        "exit_date",
        "entry_price",
        "exit_price",
        "shares",
        "entry_notional",
        "exit_notional",
        "pnl",
        "return_pct",
        "bars_held",
        "exit_reason",
    }
    missing = sorted(required - set(trades.columns))
    if missing:
        raise ValueError(f"Faltan columnas de trades: {', '.join(missing)}")

    frame = trades.copy()
    result = pd.DataFrame(
        {
            "trade": range(1, len(frame) + 1),
            "entrada": pd.to_datetime(frame["entry_date"], errors="coerce").dt.strftime("%Y-%m-%d"),
            "salida": pd.to_datetime(frame["exit_date"], errors="coerce").dt.strftime("%Y-%m-%d"),
            "precio_entrada": pd.to_numeric(frame["entry_price"], errors="coerce"),
            "precio_salida": pd.to_numeric(frame["exit_price"], errors="coerce"),
            "cantidad": pd.to_numeric(frame["shares"], errors="coerce"),
            "capital_entrada": pd.to_numeric(frame["entry_notional"], errors="coerce"),
            "valor_salida": pd.to_numeric(frame["exit_notional"], errors="coerce"),
            "pnl": pd.to_numeric(frame["pnl"], errors="coerce"),
            "roi_pct": pd.to_numeric(frame["return_pct"], errors="coerce") * 100,
            "barras": pd.to_numeric(frame["bars_held"], errors="coerce").astype("Int64"),
            "motivo_salida": frame["exit_reason"].astype(str),
        }
    )
    entry_commission = pd.to_numeric(frame.get("entry_commission", 0.0), errors="coerce").fillna(0.0)
    exit_commission = pd.to_numeric(frame.get("exit_commission", 0.0), errors="coerce").fillna(0.0)
    result["comisiones"] = entry_commission + exit_commission
    return result[columns]


def save_backtest_experiment(
    request: BacktestRequest,
    result: BacktestResult,
    signal_frame: pd.DataFrame,
    strategy_name: str,
) -> tuple[Path, Path]:
    run_id = _run_id()
    experiment_dir = _experiment_dir(request.experiments_root, request.experiment_name, run_id)
    experiment_dir.mkdir(parents=True, exist_ok=False)
    symbol_dir = experiment_dir / safe_filename_part(request.symbol)
    symbol_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = experiment_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    config = _experiment_config(request, run_id)
    metadata = collect_environment_metadata()
    summary = pd.DataFrame([_summary_row(request.symbol, strategy_name, result)])

    _write_json(experiment_dir / "config.json", config)
    _write_json(experiment_dir / "metadata.json", metadata)
    if request.notes.strip():
        (experiment_dir / "notes.md").write_text(request.notes.strip() + "\n", encoding="utf-8")

    summary.to_csv(experiment_dir / "summary.csv", index=False)
    signal_frame.to_csv(symbol_dir / "signals.csv", index=False)
    result.equity_curve.to_csv(symbol_dir / "equity.csv", index=False)
    result.trades.to_csv(symbol_dir / "trades.csv", index=False)
    result.orders.to_csv(symbol_dir / "orders.csv", index=False)
    _write_json(symbol_dir / "metrics.json", _json_safe(result.metrics))

    artifacts = generate_backtest_report(
        result=result,
        output_dir=symbol_dir,
        symbol=request.symbol,
        strategy_name=strategy_name,
    )
    _write_json(
        experiment_dir / EXPERIMENT_METADATA_FILENAME,
        _experiment_metadata(
            request=request,
            run_id=run_id,
            environment_metadata=metadata,
            config=config,
            output_files={
                "config": experiment_dir / "config.json",
                "metadata": experiment_dir / "metadata.json",
                "summary": experiment_dir / "summary.csv",
                "signals": symbol_dir / "signals.csv",
                "equity": symbol_dir / "equity.csv",
                "trades": symbol_dir / "trades.csv",
                "orders": symbol_dir / "orders.csv",
                "metrics": symbol_dir / "metrics.json",
                "report": artifacts.report_path,
            },
        ),
    )
    return experiment_dir, artifacts.report_path


def _backtest_config(request: BacktestRequest) -> BacktestConfig:
    return BacktestConfig(
        initial_capital=float(request.initial_capital),
        commission_bps=float(request.commission_bps),
        slippage_bps=float(request.slippage_bps),
        price_column=request.price_column,
        signal_column="signal",
        position_fraction=float(request.risk.position_fraction),
        stop_loss_pct=request.risk.stop_loss_pct,
        take_profit_pct=request.risk.take_profit_pct,
        max_total_exposure=float(request.risk.max_total_exposure),
        max_drawdown_pct=request.risk.max_drawdown_pct,
        max_trades_per_day=request.risk.max_trades_per_day,
        volatility_target_pct=request.risk.volatility_target_pct,
        volatility_window=int(request.risk.volatility_window),
    )


def _experiment_config(request: BacktestRequest, run_id: str) -> dict[str, Any]:
    return {
        "experiment_name": request.experiment_name,
        "run_id": run_id,
        "symbols": [request.symbol],
        "data_dir": str(request.data_dir),
        "interval": request.interval,
        "start": request.start,
        "end": request.end,
        "price_column": request.price_column,
        "output_root": str(request.experiments_root),
        "strategy": {
            "name": request.strategy_key,
            "parameters": request.strategy_parameters,
        },
        "backtest": {
            "initial_capital": request.initial_capital,
            "commission_bps": request.commission_bps,
            "slippage_bps": request.slippage_bps,
            "position_fraction": request.risk.position_fraction,
            "max_total_exposure": request.risk.max_total_exposure,
            "max_drawdown_pct": request.risk.max_drawdown_pct,
            "max_trades_per_day": request.risk.max_trades_per_day,
            "stop_loss_pct": request.risk.stop_loss_pct,
            "take_profit_pct": request.risk.take_profit_pct,
            "volatility_target_pct": request.risk.volatility_target_pct,
            "volatility_window": request.risk.volatility_window,
        },
        "ui_notes": request.notes,
    }


def _experiment_metadata(
    *,
    request: BacktestRequest,
    run_id: str,
    environment_metadata: dict[str, Any],
    config: dict[str, Any],
    output_files: dict[str, Path],
) -> dict[str, Any]:
    backtest = config["backtest"]
    return {
        "schema_version": 1,
        "metadata_available": True,
        "experiment_name": request.experiment_name,
        "run_id": run_id,
        "created_at_utc": environment_metadata.get("created_at_utc"),
        "project": {
            "package_version": environment_metadata.get("package_version"),
            "git_commit": environment_metadata.get("git_commit"),
            "git_dirty": environment_metadata.get("git_dirty"),
            "python_version": environment_metadata.get("python_version"),
            "platform": environment_metadata.get("platform"),
            "pandas_version": environment_metadata.get("pandas_version"),
        },
        "data": {
            "data_dir": str(request.data_dir),
            "symbols": [request.symbol],
            "interval": request.interval,
            "start": request.start,
            "end": request.end,
            "price_column": request.price_column,
        },
        "strategy": {
            "name": request.strategy_key,
            "parameters": request.strategy_parameters,
        },
        "costs": {
            "commission_bps": request.commission_bps,
            "slippage_bps": request.slippage_bps,
        },
        "risk": {
            "position_fraction": backtest.get("position_fraction"),
            "max_total_exposure": backtest.get("max_total_exposure"),
            "max_drawdown_pct": backtest.get("max_drawdown_pct"),
            "max_trades_per_day": backtest.get("max_trades_per_day"),
            "stop_loss_pct": backtest.get("stop_loss_pct"),
            "take_profit_pct": backtest.get("take_profit_pct"),
            "volatility_target_pct": backtest.get("volatility_target_pct"),
            "volatility_window": backtest.get("volatility_window"),
        },
        "config": config,
        "outputs": {key: str(path) for key, path in output_files.items()},
    }


def _summary_row(symbol: str, strategy_name: str, result: BacktestResult) -> dict[str, Any]:
    metrics = result.metrics
    return {
        "symbol": symbol,
        "strategy": strategy_name,
        "start_date": result.equity_curve["date"].iloc[0].strftime("%Y-%m-%d"),
        "end_date": result.equity_curve["date"].iloc[-1].strftime("%Y-%m-%d"),
        "initial_capital": metrics["initial_capital"],
        "final_equity": metrics["final_equity"],
        "total_return": metrics["total_return"],
        "cagr": metrics["cagr"],
        "sharpe_ratio": metrics["sharpe_ratio"],
        "max_drawdown": metrics["max_drawdown"],
        "number_of_trades": metrics["number_of_trades"],
        "win_rate": metrics["win_rate"],
        "total_commissions": metrics["total_commissions"],
        "benchmark_total_return": metrics["benchmark_total_return"],
        "excess_return_vs_benchmark": metrics["excess_return_vs_benchmark"],
    }


def _experiment_dir(root: Path | str, experiment_name: str, run_id: str) -> Path:
    safe_name = safe_filename_part(experiment_name or "ui_backtest")
    return Path(root) / f"{run_id}_{safe_name}"


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _boundary_date(frame: pd.DataFrame, first: bool) -> str:
    if frame.empty or "date" not in frame:
        return "n/a"
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    if dates.empty:
        return "n/a"
    return dates.iloc[0 if first else -1].strftime("%Y-%m-%d")


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _format_metric(key: str, value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    if key in {"total_return", "cagr", "max_drawdown", "win_rate", "benchmark_total_return", "benchmark_max_drawdown", "excess_return_vs_benchmark"}:
        return _format_percent(value)
    if key in {"initial_capital", "final_equity", "total_commissions"}:
        return _format_currency(value)
    if key == "number_of_trades":
        return str(int(value))
    return _format_number(value)


def _format_percent(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2%}"


def _format_currency(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):,.2f}"


def _format_number(value: float | int | None) -> str:
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):.2f}"
