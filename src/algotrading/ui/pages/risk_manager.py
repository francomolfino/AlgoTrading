from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.backtest_adapter import BacktestRequest, run_backtest_request
from algotrading.ui.adapters.risk_adapter import RiskSettings
from algotrading.ui.charts import render_line_comparison_chart
from algotrading.ui.components.common import show_error as _show_error
from algotrading.ui.components.equity_comparison import combined_equity_frame as _combined_equity_frame
from algotrading.ui.components.risk_controls import render_risk_settings as _render_risk_settings
from algotrading.ui.components.selectors import asset_selector as _asset_selector, strategy_selector as _strategy_selector
from algotrading.ui.components.strategy_controls import render_strategy_parameters as _render_strategy_parameters


def render_risk_manager_lab() -> None:
    st.title("Risk Manager")
    st.caption("Compara un backtest base contra el mismo setup con reglas de riesgo.")
    st.warning("Reducir riesgo puede bajar retorno. El objetivo es sobrevivencia y control, no mejorar magicamente la estrategia.")
    asset = _asset_selector("risk_asset")
    if asset is None:
        st.info("Primero carga datos.")
        return
    strategy_key = _strategy_selector("risk_strategy")
    parameters = _render_strategy_parameters(strategy_key, "risk_compare")
    risk = _render_risk_settings("risk_manager_lab")
    if st.button("Comparar con/sin riesgo", type="primary"):
        try:
            base = BacktestRequest(
                symbol=asset.symbol_hint,
                strategy_key=strategy_key,
                strategy_parameters=parameters,
                data_dir=st.session_state.data_dir,
                interval=asset.interval,
                risk=RiskSettings(),
                save_experiment=False,
            )
            controlled = BacktestRequest(
                symbol=asset.symbol_hint,
                strategy_key=strategy_key,
                strategy_parameters=parameters,
                data_dir=st.session_state.data_dir,
                interval=asset.interval,
                risk=risk,
                save_experiment=False,
            )
            with st.spinner("Corriendo comparacion..."):
                base_result = run_backtest_request(base)
                controlled_result = run_backtest_request(controlled)
            st.session_state.latest_risk_compare = (base_result, controlled_result)
        except Exception as exc:
            _show_error(exc)
            return
    comparison = st.session_state.get("latest_risk_compare")
    if comparison is None:
        return
    base_result, controlled_result = comparison
    metrics = pd.DataFrame(
        [
            {"setup": "sin riesgo", **base_result.result.metrics},
            {"setup": "con riesgo", **controlled_result.result.metrics},
        ]
    )
    st.dataframe(metrics, width="stretch", hide_index=True)
    curves = _combined_equity_frame(
        {
            "sin riesgo": base_result.result.equity_curve,
            "con riesgo": controlled_result.result.equity_curve,
        }
    )
    render_line_comparison_chart(curves, title="Comparacion con/sin riesgo", height=420)
    blocked = controlled_result.result.equity_curve["blocked_reason"].astype(str).ne("").sum()
    st.metric("Barras con orden bloqueada", int(blocked))
