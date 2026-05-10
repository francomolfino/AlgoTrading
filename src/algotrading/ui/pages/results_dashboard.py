from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.experiment_adapter import load_experiment_details
from algotrading.ui.components.common import show_error as _show_error
from algotrading.ui.components.research_results import (
    render_backtest_result as _render_backtest_result,
    render_experiment_details as _render_experiment_details,
)
from algotrading.ui.components.selectors import experiment_selector as _experiment_selector


def render_results_dashboard() -> None:
    st.title("Results Dashboard")
    source = st.radio("Fuente", ["Ultimo backtest", "Experimento guardado"], horizontal=True)
    if source == "Ultimo backtest":
        if "latest_backtest" not in st.session_state:
            st.info("Todavia no hay un ultimo backtest en esta sesion. Corre uno o cambia a experimento guardado.")
            return
        _render_backtest_result(st.session_state.latest_backtest)
        return

    record = _experiment_selector("results_experiment")
    if record is None:
        st.info("No hay experimentos guardados para mostrar.")
        return
    try:
        details = load_experiment_details(record.path)
    except Exception as exc:
        _show_error(exc)
        return
    _render_experiment_details(details)
