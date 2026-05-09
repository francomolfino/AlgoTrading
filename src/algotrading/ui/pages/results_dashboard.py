from __future__ import annotations

from algotrading.ui.pages._shared import *


def render_results_dashboard() -> None:
    st.title("Results Dashboard")
    source = st.radio("Fuente", ["Ultimo backtest", "Experimento guardado"], horizontal=True)
    if source == "Ultimo backtest" and "latest_backtest" in st.session_state:
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
