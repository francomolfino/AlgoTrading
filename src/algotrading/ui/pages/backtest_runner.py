from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.backtest_adapter import (
    BacktestRequest,
    preflight_backtest_request,
    run_backtest_request,
)
from algotrading.ui.adapters.strategy_adapter import STRATEGIES, get_strategy_config
from algotrading.ui.components.common import render_bullets as _render_bullets, show_error as _show_error
from algotrading.ui.components.preflight import render_backtest_preflight as _render_backtest_preflight
from algotrading.ui.components.research_results import render_backtest_result as _render_backtest_result
from algotrading.ui.components.risk_controls import render_risk_settings as _render_risk_settings
from algotrading.ui.components.selectors import asset_selector as _asset_selector
from algotrading.ui.components.strategy_controls import (
    render_strategy_parameters as _render_strategy_parameters,
    render_strategy_research_metadata as _render_strategy_research_metadata,
)
from algotrading.ui.texts import TOOLTIPS


def render_backtest_runner() -> None:
    st.title("Backtest Runner")
    st.warning("Backtest educativo. No modela liquidez real, impuestos ni ejecucion parcial.")
    with st.expander("Checklist antes de correr", expanded=False):
        _render_bullets(
            [
                "La estrategia ya fue revisada visualmente en Strategy Lab.",
                "Los datos fueron validados en Data Manager.",
                "Comision y slippage no estan en cero salvo que sea intencional.",
                "Vas a comparar el resultado contra benchmark.",
                "No vas a elegir parametros solo por el mejor retorno.",
            ]
        )
    asset = _asset_selector("backtest_asset")
    if asset is None:
        st.info("Primero carga datos en Data Manager.")
        return

    st.subheader("Estrategia")
    strategy_key = st.selectbox(
        "Estrategia",
        list(STRATEGIES),
        format_func=lambda key: STRATEGIES[key].label,
        help="Estrategia long-only disponible en el framework.",
        key="backtest_strategy",
    )
    strategy_config = get_strategy_config(strategy_key)
    st.caption(strategy_config.description)
    _render_strategy_research_metadata(strategy_key)
    parameters = _render_strategy_parameters(strategy_key, "backtest")

    with st.form("backtest_form"):
        st.subheader("Ejecucion")
        price_column = st.selectbox(
            "Precio",
            ["adj_close", "close"],
            index=0,
            help=TOOLTIPS["adjusted_close"],
        )
        st.caption("Benchmark automatico: buy and hold del mismo activo en el mismo periodo.")

        st.subheader("Capital y costos")
        c1, c2, c3 = st.columns(3)
        initial_capital = c1.number_input("Capital inicial", min_value=100.0, value=10_000.0, step=500.0, help=TOOLTIPS["capital"])
        commission_bps = c2.number_input("Comision bps", min_value=0.0, value=1.0, step=0.5, help=TOOLTIPS["commission"])
        slippage_bps = c3.number_input("Slippage bps", min_value=0.0, value=2.0, step=0.5, help=TOOLTIPS["slippage"])
        zero_cost_ack = st.checkbox(
            "Confirmo que quiero correr con comision y slippage en cero",
            value=False,
            disabled=not (commission_bps == 0 and slippage_bps == 0),
            help="Costos cero son utiles para aislar logica, pero suelen inflar resultados.",
        )

        st.subheader("Periodo")
        d1, d2, d3 = st.columns(3)
        use_start = d1.checkbox("Filtrar inicio", value=False)
        start = d1.date_input("Inicio", value=pd.Timestamp("2018-01-01"), disabled=not use_start)
        use_end = d2.checkbox("Filtrar fin", value=False)
        end = d2.date_input("Fin", value=pd.Timestamp.today(), disabled=not use_end)
        save_experiment = d3.checkbox("Guardar experimento", value=True)

        risk = _render_risk_settings("backtest_risk")

        experiment_name = st.text_input(
            "Nombre del experimento",
            value=f"ui_{asset.symbol_hint}_{strategy_key}",
            key=f"backtest_experiment_name_{asset.symbol_hint}_{strategy_key}",
        )
        notes = st.text_area("Notas", value="", help="Hipotesis o contexto del experimento.")
        submitted = st.form_submit_button("Correr backtest")

    if submitted:
        request = BacktestRequest(
            symbol=asset.symbol_hint,
            strategy_key=strategy_key,
            strategy_parameters=parameters,
            data_dir=st.session_state.data_dir,
            interval=asset.interval,
            start=str(start) if use_start else None,
            end=str(end) if use_end else None,
            price_column=price_column,
            initial_capital=float(initial_capital),
            commission_bps=float(commission_bps),
            slippage_bps=float(slippage_bps),
            risk=risk,
            experiment_name=experiment_name,
            notes=notes,
            save_experiment=save_experiment,
            experiments_root=st.session_state.experiments_dir,
        )
        try:
            if commission_bps == 0 and slippage_bps == 0 and not zero_cost_ack:
                st.error("Costos en cero bloqueados. Confirma explicitamente que es intencional.")
                return
            preflight = preflight_backtest_request(request)
            _render_backtest_preflight(preflight)
            if not preflight.can_run:
                st.error("No ejecuto el backtest porque hay errores bloqueantes.")
                return
            with st.spinner("Ejecutando backtest..."):
                artifacts = run_backtest_request(request)
            st.session_state.latest_backtest = artifacts
            st.success("Backtest finalizado.")
            _render_backtest_result(artifacts)
        except Exception as exc:
            _show_error(exc)
