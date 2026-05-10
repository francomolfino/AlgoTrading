from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.experiment_adapter import load_experiment_details
from algotrading.ui.components.common import (
    render_empty_state as _render_empty_state,
    render_page_header as _render_page_header,
    show_error as _show_error,
)
from algotrading.ui.components.research_results import (
    render_backtest_result as _render_backtest_result,
    render_experiment_details as _render_experiment_details,
)
from algotrading.ui.components.selectors import experiment_selector as _experiment_selector
from algotrading.ui.texts import EMPTY_STATES


def render_results_dashboard() -> None:
    _render_page_header(
        "Results Dashboard",
        "Centro de lectura critica: primero diagnostico, despues curvas y tablas.",
        area="Research",
    )
    source = st.radio("Fuente", ["Ultimo backtest", "Experimento guardado"], horizontal=True)
    if source == "Ultimo backtest":
        if "latest_backtest" not in st.session_state:
            empty = EMPTY_STATES["no_latest_backtest"]
            _render_empty_state(
                empty["title"],
                missing=empty["missing"],
                why_it_matters=empty["why"],
                next_step=empty["next"],
            )
            return
        _render_backtest_result(st.session_state.latest_backtest)
        return

    record = _experiment_selector("results_experiment")
    if record is None:
        empty = EMPTY_STATES["no_experiments"]
        _render_empty_state(
            empty["title"],
            missing=empty["missing"],
            why_it_matters=empty["why"],
            next_step=empty["next"],
        )
        return
    try:
        details = load_experiment_details(record.path)
    except Exception as exc:
        _show_error(exc)
        return
    _render_experiment_details(details)
