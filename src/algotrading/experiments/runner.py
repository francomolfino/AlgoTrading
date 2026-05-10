from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any

import pandas as pd

from algotrading.backtesting import BacktestConfig, BacktestResult, run_backtest
from algotrading.data.storage import build_data_path, load_ohlcv, safe_filename_part
from algotrading.reports import generate_backtest_report
from algotrading.ui.adapters.data_quality_adapter import (
    advanced_quality_to_dict,
    build_advanced_data_quality_report,
)
from algotrading.strategies.breakout import generate_breakout_signals
from algotrading.strategies.buy_and_hold import generate_buy_and_hold_signals
from algotrading.strategies.moving_average import generate_sma_crossover_signals
from algotrading.strategies.registry import StrategySpec
from algotrading.strategies.rsi import generate_rsi_signals
from algotrading.strategies.trend_filter import generate_trend_filter_signals
from algotrading.visualization.plots import (
    plot_equity_comparison,
    plot_equity_curve_with_drawdown,
)


@dataclass(frozen=True)
class ExperimentRunResult:
    experiment_dir: Path
    summary: pd.DataFrame
    config: dict[str, Any]
    metadata: dict[str, Any]


def load_experiment_config(path: Path | str) -> dict[str, Any]:
    """Carga una config JSON versionable para un experimento."""
    config_path = Path(path)
    if config_path.suffix.lower() != ".json":
        raise ValueError("Por ahora los experimentos usan configs JSON.")
    with config_path.open("r", encoding="utf-8") as file:
        config = json.load(file)
    if not isinstance(config, dict):
        raise ValueError("La config del experimento debe ser un objeto JSON.")
    return normalize_experiment_config(config)


def run_experiment_config(
    config_path: Path | str,
    output_root: Path | str | None = None,
) -> ExperimentRunResult:
    config = load_experiment_config(config_path)
    if output_root is not None:
        config["output_root"] = str(output_root)
    return run_experiment(config)


def run_experiment(config: Mapping[str, Any]) -> ExperimentRunResult:
    """Ejecuta una estrategia sobre uno o varios activos y guarda outputs auditables."""
    normalized = normalize_experiment_config(dict(config))
    output_root = Path(normalized["output_root"])
    experiment_dir = _experiment_dir(output_root, normalized)
    experiment_dir.mkdir(parents=True, exist_ok=False)
    figures_dir = experiment_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    metadata = collect_environment_metadata()
    _write_json(experiment_dir / "config.json", normalized)
    _write_json(experiment_dir / "metadata.json", metadata)

    rows: list[dict[str, Any]] = []
    equity_curves: dict[str, pd.DataFrame] = {}
    first_quality_report: dict[str, Any] | None = None
    strategy_spec = build_strategy_spec(
        normalized["strategy"],
        price_column=normalized["price_column"],
    )
    backtest_config = _backtest_config(normalized)

    for symbol in normalized["symbols"]:
        frame = _load_symbol_frame(normalized, symbol)
        frame = _filter_dates(frame, start=normalized.get("start"), end=normalized.get("end"))
        if first_quality_report is None:
            first_quality_report = advanced_quality_to_dict(
                build_advanced_data_quality_report(
                    frame,
                    symbol=symbol,
                    interval=normalized["interval"],
                )
            )
        signal_frame = strategy_spec.function(
            frame,
            signal_column=backtest_config.signal_column,
            **strategy_spec.parameters,
        )
        result = run_backtest(signal_frame, config=backtest_config)
        symbol_dir = experiment_dir / safe_filename_part(symbol)
        symbol_dir.mkdir(parents=True, exist_ok=True)
        _save_backtest_outputs(
            result=result,
            symbol=symbol,
            strategy_name=strategy_spec.name,
            symbol_dir=symbol_dir,
            figures_dir=figures_dir,
        )
        rows.append(_summary_row(symbol, strategy_spec.name, result))
        equity_curves[symbol] = result.equity_curve

    summary = pd.DataFrame(rows)
    summary_path = experiment_dir / "summary.csv"
    summary.to_csv(summary_path, index=False)
    if first_quality_report is not None:
        _write_json(experiment_dir / "data_quality.json", first_quality_report)

    if len(equity_curves) > 1:
        figure = plot_equity_comparison(
            equity_curves,
            title=f"{normalized['experiment_name']} - equity por activo",
        )
        figure.savefig(figures_dir / "equity_comparison.png", dpi=140, bbox_inches="tight")

    _write_json(
        experiment_dir / "experiment_metadata.json",
        _experiment_metadata(
            config=normalized,
            metadata=metadata,
            experiment_dir=experiment_dir,
            summary_path=summary_path,
        ),
    )

    return ExperimentRunResult(
        experiment_dir=experiment_dir,
        summary=summary,
        config=normalized,
        metadata=metadata,
    )


def normalize_experiment_config(config: dict[str, Any]) -> dict[str, Any]:
    required = ["experiment_name", "symbols", "strategy"]
    missing = [key for key in required if key not in config]
    if missing:
        raise ValueError(f"Faltan campos requeridos: {', '.join(missing)}")

    symbols = config["symbols"]
    if not isinstance(symbols, list) or not symbols:
        raise ValueError("symbols debe ser una lista no vacia.")
    if not all(isinstance(symbol, str) and symbol.strip() for symbol in symbols):
        raise ValueError("Todos los symbols deben ser strings no vacios.")

    strategy = config["strategy"]
    if not isinstance(strategy, dict):
        raise ValueError("strategy debe ser un objeto.")
    if "name" not in strategy:
        raise ValueError("strategy.name es requerido.")

    normalized = dict(config)
    normalized["symbols"] = [symbol.strip() for symbol in symbols]
    normalized["data_dir"] = str(normalized.get("data_dir", "data/raw"))
    normalized["interval"] = str(normalized.get("interval", "1d"))
    normalized["price_column"] = str(normalized.get("price_column", "adj_close"))
    normalized["output_root"] = str(normalized.get("output_root", "experiments"))
    normalized["run_id"] = str(normalized.get("run_id") or _default_run_id())
    normalized["research_preset"] = str(normalized.get("research_preset", "sanity_check"))
    normalized["strategy"] = {
        "name": str(strategy["name"]),
        "parameters": dict(strategy.get("parameters", {})),
    }
    normalized["backtest"] = dict(normalized.get("backtest", {}))
    normalized["start"] = normalized.get("start")
    normalized["end"] = normalized.get("end")
    return normalized


def build_strategy_spec(strategy_config: Mapping[str, Any], price_column: str) -> StrategySpec:
    name = str(strategy_config["name"])
    parameters = dict(strategy_config.get("parameters", {}))

    if name == "buy_and_hold":
        return StrategySpec(name="buy_and_hold", function=generate_buy_and_hold_signals, parameters={})
    if name == "sma_cross":
        fast = int(parameters.get("fast_window", 50))
        slow = int(parameters.get("slow_window", 200))
        return StrategySpec(
            name=f"sma_cross_{fast}_{slow}",
            function=generate_sma_crossover_signals,
            parameters={
                "fast_window": fast,
                "slow_window": slow,
                "price_column": price_column,
            },
        )
    if name == "rsi":
        window = int(parameters.get("window", 14))
        oversold = float(parameters.get("oversold", 30))
        overbought = float(parameters.get("overbought", 70))
        return StrategySpec(
            name=f"rsi_{window}_{int(oversold)}_{int(overbought)}",
            function=generate_rsi_signals,
            parameters={
                "window": window,
                "oversold": oversold,
                "overbought": overbought,
                "price_column": price_column,
            },
        )
    if name == "breakout":
        entry_window = int(parameters.get("entry_window", 55))
        exit_window = int(parameters.get("exit_window", 20))
        return StrategySpec(
            name=f"breakout_{entry_window}_{exit_window}",
            function=generate_breakout_signals,
            parameters={
                "entry_window": entry_window,
                "exit_window": exit_window,
                "price_column": price_column,
            },
        )
    if name == "trend_filter":
        fast = int(parameters.get("fast_window", 20))
        slow = int(parameters.get("slow_window", 100))
        trend = int(parameters.get("trend_window", 200))
        return StrategySpec(
            name=f"trend_filter_{fast}_{slow}_{trend}",
            function=generate_trend_filter_signals,
            parameters={
                "fast_window": fast,
                "slow_window": slow,
                "trend_window": trend,
                "price_column": price_column,
            },
        )
    raise ValueError(f"Estrategia no soportada para experimentos: {name}")


def collect_environment_metadata() -> dict[str, Any]:
    return {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "python_version": sys.version.split()[0],
        "platform": platform.platform(),
        "pandas_version": pd.__version__,
        "package_version": _package_version(),
        "git_commit": _git_value(["rev-parse", "--short", "HEAD"]),
        "git_dirty": _git_dirty(),
    }


def _backtest_config(config: Mapping[str, Any]) -> BacktestConfig:
    backtest = dict(config.get("backtest", {}))
    allowed = {
        "initial_capital",
        "commission_bps",
        "slippage_bps",
        "periods_per_year",
        "close_open_position",
        "allow_missing_signals",
        "position_fraction",
        "stop_loss_pct",
        "take_profit_pct",
        "max_total_exposure",
        "max_drawdown_pct",
        "max_trades_per_day",
        "volatility_target_pct",
        "volatility_window",
    }
    unknown = sorted(set(backtest) - allowed)
    if unknown:
        raise ValueError(f"Campos backtest no soportados: {', '.join(unknown)}")

    return BacktestConfig(
        initial_capital=float(backtest.get("initial_capital", 10_000.0)),
        commission_bps=float(backtest.get("commission_bps", 1.0)),
        slippage_bps=float(backtest.get("slippage_bps", 2.0)),
        price_column=str(config["price_column"]),
        signal_column="signal",
        periods_per_year=int(backtest.get("periods_per_year", 252)),
        close_open_position=bool(backtest.get("close_open_position", True)),
        allow_missing_signals=bool(backtest.get("allow_missing_signals", False)),
        position_fraction=float(backtest.get("position_fraction", 1.0)),
        stop_loss_pct=_optional_float(backtest.get("stop_loss_pct")),
        take_profit_pct=_optional_float(backtest.get("take_profit_pct")),
        max_total_exposure=float(backtest.get("max_total_exposure", 1.0)),
        max_drawdown_pct=_optional_float(backtest.get("max_drawdown_pct")),
        max_trades_per_day=_optional_int(backtest.get("max_trades_per_day")),
        volatility_target_pct=_optional_float(backtest.get("volatility_target_pct")),
        volatility_window=int(backtest.get("volatility_window", 20)),
    )


def _load_symbol_frame(config: Mapping[str, Any], symbol: str) -> pd.DataFrame:
    data_files = config.get("data_files")
    if isinstance(data_files, dict) and symbol in data_files:
        return load_ohlcv(data_files[symbol])

    data_dir = Path(str(config["data_dir"]))
    interval = str(config["interval"])
    csv_path = build_data_path(data_dir, symbol, interval, "csv")
    parquet_path = build_data_path(data_dir, symbol, interval, "parquet")
    if csv_path.exists():
        return load_ohlcv(csv_path)
    if parquet_path.exists():
        return load_ohlcv(parquet_path)
    raise FileNotFoundError(f"No encontre datos para {symbol}. Esperaba {csv_path} o {parquet_path}.")


def _filter_dates(frame: pd.DataFrame, start: str | None, end: str | None) -> pd.DataFrame:
    data = frame.copy()
    dates = pd.to_datetime(data["date"], errors="coerce")
    if start:
        data = data.loc[dates >= pd.Timestamp(start)]
        dates = pd.to_datetime(data["date"], errors="coerce")
    if end:
        data = data.loc[dates <= pd.Timestamp(end)]
    data = data.reset_index(drop=True)
    if len(data) < 2:
        raise ValueError("El periodo filtrado necesita al menos dos filas.")
    return data


def _save_backtest_outputs(
    result: BacktestResult,
    symbol: str,
    strategy_name: str,
    symbol_dir: Path,
    figures_dir: Path,
) -> None:
    result.equity_curve.to_csv(symbol_dir / "equity.csv", index=False)
    result.trades.to_csv(symbol_dir / "trades.csv", index=False)
    result.orders.to_csv(symbol_dir / "orders.csv", index=False)
    _write_json(symbol_dir / "metrics.json", _json_safe_metrics(result.metrics))
    generate_backtest_report(
        result=result,
        output_dir=symbol_dir,
        symbol=symbol,
        strategy_name=strategy_name,
    )

    figure = plot_equity_curve_with_drawdown(
        result.equity_curve,
        title=f"{symbol} - {strategy_name}",
    )
    figure.savefig(figures_dir / f"{safe_filename_part(symbol)}_equity.png", dpi=140, bbox_inches="tight")


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


def _experiment_metadata(
    *,
    config: Mapping[str, Any],
    metadata: Mapping[str, Any],
    experiment_dir: Path,
    summary_path: Path,
) -> dict[str, Any]:
    backtest = dict(config.get("backtest", {}))
    return {
        "schema_version": 1,
        "metadata_available": True,
        "experiment_name": config.get("experiment_name"),
        "run_id": config.get("run_id"),
        "created_at_utc": metadata.get("created_at_utc"),
        "project": {
            "package_version": metadata.get("package_version"),
            "git_commit": metadata.get("git_commit"),
            "git_dirty": metadata.get("git_dirty"),
            "python_version": metadata.get("python_version"),
            "platform": metadata.get("platform"),
            "pandas_version": metadata.get("pandas_version"),
        },
        "data": {
            "data_dir": config.get("data_dir"),
            "symbols": config.get("symbols", []),
            "interval": config.get("interval"),
            "start": config.get("start"),
            "end": config.get("end"),
            "price_column": config.get("price_column"),
        },
        "strategy": dict(config.get("strategy", {})),
        "research": {
            "preset": config.get("research_preset", "sanity_check"),
        },
        "costs": {
            "commission_bps": backtest.get("commission_bps", 1.0),
            "slippage_bps": backtest.get("slippage_bps", 2.0),
        },
        "risk": {
            key: backtest.get(key)
            for key in (
                "position_fraction",
                "max_total_exposure",
                "max_drawdown_pct",
                "max_trades_per_day",
                "stop_loss_pct",
                "take_profit_pct",
                "volatility_target_pct",
                "volatility_window",
            )
        },
        "config": dict(config),
        "outputs": _experiment_output_files(config, experiment_dir, summary_path),
    }


def _experiment_output_files(
    config: Mapping[str, Any],
    experiment_dir: Path,
    summary_path: Path,
) -> dict[str, str]:
    outputs = {
        "config": str(experiment_dir / "config.json"),
        "metadata": str(experiment_dir / "metadata.json"),
        "summary": str(summary_path),
        "data_quality": str(experiment_dir / "data_quality.json"),
        "figures": str(experiment_dir / "figures"),
    }
    for symbol in config.get("symbols", []):
        symbol_dir = experiment_dir / safe_filename_part(str(symbol))
        prefix = safe_filename_part(str(symbol))
        outputs[f"{prefix}_equity"] = str(symbol_dir / "equity.csv")
        outputs[f"{prefix}_trades"] = str(symbol_dir / "trades.csv")
        outputs[f"{prefix}_orders"] = str(symbol_dir / "orders.csv")
        outputs[f"{prefix}_metrics"] = str(symbol_dir / "metrics.json")
        outputs[f"{prefix}_report"] = str(symbol_dir / "report.md")
    return outputs


def _experiment_dir(output_root: Path, config: Mapping[str, Any]) -> Path:
    name = safe_filename_part(str(config["experiment_name"]))
    run_id = safe_filename_part(str(config["run_id"]))
    return output_root / f"{run_id}_{name}"


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _json_safe_metrics(metrics: Mapping[str, float | int]) -> dict[str, float | int | None]:
    safe: dict[str, float | int | None] = {}
    for key, value in metrics.items():
        if isinstance(value, float) and math.isnan(value):
            safe[key] = None
        else:
            safe[key] = value
    return safe


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _package_version() -> str:
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        return "unknown"
    for line in pyproject.read_text(encoding="utf-8").splitlines():
        if line.startswith("version = "):
            return line.split("=", maxsplit=1)[1].strip().strip('"')
    return "unknown"


def _git_value(args: list[str]) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _git_dirty() -> bool | None:
    try:
        completed = subprocess.run(
            ["git", "diff", "--quiet"],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.returncode != 0
