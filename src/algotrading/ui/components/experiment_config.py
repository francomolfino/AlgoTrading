from __future__ import annotations

from pathlib import Path

import streamlit as st

from algotrading.ui.adapters.experiment_adapter import ExperimentDetails, ExperimentRecord


def experiment_request_defaults(details: ExperimentDetails) -> dict:
    config = details.config if isinstance(details.config, dict) else {}
    strategy_config = config.get("strategy", {})
    backtest_config = config.get("backtest", {})
    if not isinstance(strategy_config, dict):
        strategy_config = {}
    if not isinstance(backtest_config, dict):
        backtest_config = {}

    symbols = tuple(str(symbol) for symbol in (config.get("symbols") or []) if str(symbol))
    strategy_parameters = strategy_config.get("parameters", {})
    if not isinstance(strategy_parameters, dict):
        strategy_parameters = {}
    data_dir = config.get("data_dir") or _session_value("data_dir", "data/raw")
    interval = config.get("interval") or _session_value("interval", "1d")

    return {
        "symbol": details.symbol,
        "symbols": symbols,
        "data_dir": Path(str(data_dir)),
        "interval": str(interval),
        "start": _optional_config_text(config.get("start")),
        "end": _optional_config_text(config.get("end")),
        "price_column": str(config.get("price_column", "adj_close")),
        "strategy_key": str(strategy_config.get("name", "")),
        "strategy_parameters": strategy_parameters,
        "initial_capital": _config_float(backtest_config, "initial_capital", 10_000.0),
        "commission_bps": _config_float(backtest_config, "commission_bps", 1.0),
        "slippage_bps": _config_float(backtest_config, "slippage_bps", 2.0),
    }


def render_experiment_config_summary(record: ExperimentRecord, defaults: dict) -> None:
    st.caption(
        "Configuracion cargada desde experimento: "
        f"`{record.name}` | activo `{defaults['symbol']}` | "
        f"estrategia `{defaults['strategy_key']}` | timeframe `{defaults['interval']}`"
    )
    with st.expander("Ver parametros cargados", expanded=False):
        st.json(
            {
                "path": str(record.path),
                "symbols": defaults["symbols"],
                "data_dir": str(defaults["data_dir"]),
                "start": defaults["start"],
                "end": defaults["end"],
                "price_column": defaults["price_column"],
                "strategy_parameters": defaults["strategy_parameters"],
                "initial_capital": defaults["initial_capital"],
                "commission_bps": defaults["commission_bps"],
                "slippage_bps": defaults["slippage_bps"],
            }
        )


def _config_float(config: dict, key: str, default: float) -> float:
    try:
        return float(config.get(key, default))
    except (TypeError, ValueError):
        return default


def _optional_config_text(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _session_value(key: str, default: object) -> object:
    try:
        return getattr(st.session_state, key)
    except AttributeError:
        return default
