from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.data_adapter import list_data_assets
from algotrading.ui.adapters.portfolio_adapter import (
    PortfolioRequest,
    preflight_portfolio_request,
    run_portfolio_request,
)
from algotrading.ui.components.common import show_error as _show_error
from algotrading.ui.components.preflight import render_portfolio_preflight as _render_portfolio_preflight
from algotrading.ui.components.result_views import render_equity_and_drawdown as _render_equity_and_drawdown
from algotrading.ui.texts import TOOLTIPS


def render_portfolio_lab() -> None:
    st.title("Portfolio Lab")
    st.info("Correlaciones y pesos historicos no son estables. Usalos para entender dependencia entre activos, no para predecir diversificacion futura.")
    assets = list_data_assets(st.session_state.data_dir, st.session_state.interval)
    if len(assets) < 2:
        st.info("Necesitas al menos dos activos con datos locales.")
        return
    selected_assets = st.multiselect(
        "Activos",
        assets,
        default=assets[: min(4, len(assets))],
        format_func=lambda asset: asset.symbol_hint,
    )
    mode = st.radio("Pesos", ["equal_weight", "manual"], format_func=lambda value: "Equal-weight" if value == "equal_weight" else "Manual", horizontal=True)
    manual_weights = None
    if mode == "manual" and selected_assets:
        st.caption("Los pesos deben sumar 100%.")
        manual_weights = {}
        cols = st.columns(min(4, len(selected_assets)))
        default_weight = 1.0 / len(selected_assets)
        for index, asset in enumerate(selected_assets):
            value = cols[index % len(cols)].number_input(
                f"{asset.symbol_hint} %",
                min_value=0.0,
                max_value=100.0,
                value=round(default_weight * 100, 2),
                step=1.0,
            )
            manual_weights[asset.symbol_hint] = float(value) / 100
        st.write(f"Suma: {sum(manual_weights.values()):.2%}")

    c1, c2, c3 = st.columns(3)
    initial_capital = c1.number_input("Capital inicial", min_value=100.0, value=10_000.0, step=500.0, help=TOOLTIPS["capital"])
    commission_bps = c2.number_input("Comision bps", min_value=0.0, value=1.0, step=0.5, help=TOOLTIPS["commission"])
    slippage_bps = c3.number_input("Slippage bps", min_value=0.0, value=2.0, step=0.5, help=TOOLTIPS["slippage"])
    rebalance = st.selectbox("Rebalanceo", ["daily", "weekly", "monthly", "none"], index=2, help=TOOLTIPS["rebalance"])

    input_errors: list[str] = []
    if len(selected_assets) < 2:
        input_errors.append("Selecciona al menos dos activos.")
    if mode == "manual":
        total_weight = sum((manual_weights or {}).values())
        max_weight = max((manual_weights or {"": 0.0}).values())
        if abs(total_weight - 1.0) > 1e-6:
            input_errors.append("Los pesos manuales deben sumar exactamente 100%.")
        if max_weight > 0.8:
            input_errors.append("Un activo supera 80% del portfolio. Reduce concentracion antes de correr.")
        elif max_weight > 0.6:
            st.warning("Concentracion alta: un activo supera 60% del portfolio.")
    for error in input_errors:
        st.error(error)

    request = PortfolioRequest(
        symbols=tuple(asset.symbol_hint for asset in selected_assets),
        data_dir=st.session_state.data_dir,
        interval=st.session_state.interval,
        initial_capital=float(initial_capital),
        commission_bps=float(commission_bps),
        slippage_bps=float(slippage_bps),
        rebalance_frequency=rebalance,
        weighting_mode=mode,
        manual_weights=manual_weights,
    )

    if st.button("Correr portfolio", type="primary", disabled=bool(input_errors)):
        try:
            preflight = preflight_portfolio_request(request)
            _render_portfolio_preflight(preflight)
            if not preflight.can_run:
                st.error("No ejecuto el portfolio porque hay errores bloqueantes.")
                return
            with st.spinner("Calculando portfolio..."):
                result = run_portfolio_request(request)
            st.session_state.latest_portfolio = result
        except Exception as exc:
            _show_error(exc)
            return

    result = st.session_state.get("latest_portfolio")
    if result is None:
        return
    for warning in result.warnings:
        st.warning(warning)
    st.subheader("Equity y drawdown")
    _render_equity_and_drawdown(result.portfolio_equity)
    st.subheader("Metricas")
    st.dataframe(result.summary, width="stretch", hide_index=True)
    st.subheader("Correlaciones")
    st.dataframe(result.correlations, width="stretch")
    st.subheader("Ordenes de rebalanceo")
    st.dataframe(result.portfolio_orders, width="stretch", hide_index=True)
