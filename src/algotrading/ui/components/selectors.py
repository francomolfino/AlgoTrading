from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.data_adapter import list_data_assets
from algotrading.ui.adapters.experiment_adapter import ExperimentRecord, list_experiments
from algotrading.ui.adapters.strategy_adapter import STRATEGIES
from algotrading.ui.texts import TOOLTIPS


def asset_selector(key: str):
    assets = list_data_assets(st.session_state.data_dir, st.session_state.interval)
    if not assets:
        return None
    return st.selectbox(
        "Activo local",
        options=assets,
        format_func=lambda asset: f"{asset.symbol_hint} ({asset.interval}, {asset.rows} filas)",
        help=TOOLTIPS["ticker"],
        key=key,
    )


def experiment_selector(key: str) -> ExperimentRecord | None:
    records = list_experiments(st.session_state.experiments_dir)
    if not records:
        return None
    return st.selectbox(
        "Experimento",
        records,
        format_func=lambda record: f"{record.name} - {record.strategy} - {', '.join(record.symbols)}",
        key=key,
    )


def strategy_selector(key: str) -> str:
    return st.selectbox(
        "Estrategia",
        list(STRATEGIES),
        format_func=lambda strategy_key: STRATEGIES[strategy_key].label,
        key=key,
    )


def asset_index(assets, symbol: str | None) -> int:
    if symbol is None:
        return 0
    for index, asset in enumerate(assets):
        if asset.symbol_hint == symbol:
            return index
    return 0


def strategy_index(strategy_keys: list[str], strategy_key: str) -> int:
    try:
        return strategy_keys.index(strategy_key)
    except ValueError:
        return 0
