from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.paper_adapter import (
    PaperTradingRequest,
    build_paper_replay_frame,
    replay_display_columns,
    replay_snapshot,
    run_paper_trading_request,
    supported_paper_strategies,
)
from algotrading.ui.adapters.strategy_adapter import get_strategy_config
from algotrading.ui.components.common import show_error as _show_error
from algotrading.ui.components.result_views import render_equity_and_drawdown as _render_equity_and_drawdown
from algotrading.ui.components.risk_controls import render_risk_settings as _render_risk_settings
from algotrading.ui.components.selectors import asset_selector as _asset_selector
from algotrading.ui.components.strategy_controls import render_strategy_parameters as _render_strategy_parameters
from algotrading.ui.texts import PAPER_SIMULATION_WARNING


def render_paper_trading_simulator() -> None:
    st.title("Paper Trading Simulator")
    st.error(PAPER_SIMULATION_WARNING)
    asset = _asset_selector("paper_asset")
    if asset is None:
        st.info("Primero carga datos.")
        return
    strategies = supported_paper_strategies()
    strategy_key = st.selectbox("Estrategia", list(strategies), format_func=lambda key: strategies[key])
    config = get_strategy_config(strategy_key)
    st.caption(config.description)
    st.caption(config.risk_note)
    parameters = _render_strategy_parameters(strategy_key, "paper")
    c1, c2, c3 = st.columns(3)
    initial_cash = c1.number_input("Capital simulado", min_value=100.0, value=10_000.0, step=500.0)
    commission_bps = c2.number_input("Comision bps", min_value=0.0, value=1.0, step=0.5)
    slippage_bps = c3.number_input("Slippage bps", min_value=0.0, value=2.0, step=0.5)
    mode = st.radio(
        "Modo de simulacion",
        ["fills", "dry_run"],
        index=0,
        format_func=lambda value: "Simular fills en FakeBroker (recomendado)" if value == "fills" else "Dry-run: crear ordenes sin ejecutarlas",
        horizontal=True,
        help="Con fills simulados el broker fake compra/vende y la equity puede cambiar. En dry-run no hay fills: sirve para auditar ordenes, pero el retorno suele quedar en 0%.",
    )
    dry_run = mode == "dry_run"
    if dry_run:
        st.info("Dry-run no llena ordenes. Es normal ver 0 fills y retorno 0% porque no hay posicion real simulada.")
    else:
        st.warning("Simula fills solo en FakeBroker local. No hay broker real, API keys ni dinero real.")
    risk = _render_risk_settings("paper_risk")
    if st.button("Ejecutar simulacion", type="primary"):
        try:
            request = PaperTradingRequest(
                symbol=asset.symbol_hint,
                strategy_key=strategy_key,
                strategy_parameters=parameters,
                data_dir=st.session_state.data_dir,
                interval=asset.interval,
                initial_cash=float(initial_cash),
                commission_bps=float(commission_bps),
                slippage_bps=float(slippage_bps),
                max_position_fraction=risk.position_fraction,
                max_total_exposure=risk.max_total_exposure,
                max_drawdown_pct=risk.max_drawdown_pct,
                max_trades_per_day=risk.max_trades_per_day,
                dry_run=dry_run,
            )
            with st.spinner("Simulando paper trading..."):
                result = run_paper_trading_request(request)
            st.session_state.latest_paper = result
        except Exception as exc:
            _show_error(exc)
            return
    result = st.session_state.get("latest_paper")
    if result is None:
        return
    cols = st.columns(5)
    cols[0].metric("Equity final", f"{result.summary['final_equity']:,.2f}")
    cols[1].metric("Retorno", f"{result.summary['total_return']:.2%}")
    cols[2].metric("Ordenes", result.summary["orders"])
    cols[3].metric("Fills", result.summary["fills"])
    cols[4].metric("Errores", result.summary["errors"])
    if result.summary["dry_run"]:
        st.info("Resultado en dry-run: las ordenes se cancelan intencionalmente y no afectan la equity.")
    elif result.summary["fills"] == 0:
        st.warning("No hubo fills simulados. Revisa senales, risk manager, min trade value o periodo elegido.")
    _render_equity_and_drawdown(result.account_history)
    tabs = st.tabs(["Replay", "Ordenes", "Eventos", "Fills", "Errores", "Cuenta"])
    with tabs[0]:
        replay = build_paper_replay_frame(result)
        if replay.empty:
            st.info("No hay barras para replay.")
        else:
            position = st.slider("Barra", 1, len(replay), len(replay), help="Recorre la simulacion barra por barra.")
            snapshot = replay_snapshot(replay, position - 1)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Fecha", str(snapshot.get("date", ""))[:10])
            c2.metric("Equity", f"{float(snapshot.get('equity', 0.0)):,.2f}")
            c3.metric("Cash", f"{float(snapshot.get('cash', 0.0)):,.2f}")
            c4.metric("Posicion", f"{float(snapshot.get('position_quantity', 0.0)):,.6g}")
            st.subheader("Explicacion de la barra")
            st.markdown(f"**Decision:** {snapshot.get('decision', 'sin decision')}")
            st.caption(snapshot.get("timing_explanation", ""))
            st.info(snapshot.get("signal_explanation", "Sin detalle de senal."))
            c_signal, c_risk = st.columns(2)
            c_signal.write(f"**Risk manager**  \n{snapshot.get('risk_explanation', 'Sin detalle de riesgo.')}")
            c_risk.write(f"**Broker fake**  \n{snapshot.get('broker_explanation', 'Sin detalle de broker.')}")
            st.write(f"**Cuenta:** {snapshot.get('account_explanation', 'Sin detalle de cuenta.')}")
            st.write(f"**Resumen:** {snapshot.get('step_summary', 'Sin resumen.')}")
            with st.expander("Detalle tecnico de la barra"):
                st.write(f"Senal/peso aplicado: `{snapshot.get('executed_target_weight', 'n/a')}`")
                st.write(f"Senal/peso proximo: `{snapshot.get('next_target_weight', 'n/a')}`")
                st.write(f"Orden: `{snapshot.get('order') or 'sin orden'}`")
                st.write(f"Evento broker: `{snapshot.get('order_status') or 'sin evento'}`")
                st.write(f"Fill: `{snapshot.get('fill') or 'sin fill'}`")
            if snapshot.get("risk_event") or snapshot.get("blocked_reason"):
                st.warning(f"Riesgo: {snapshot.get('risk_event') or snapshot.get('blocked_reason')}")
            st.dataframe(replay[replay_display_columns(replay)], width="stretch", hide_index=True)
    tabs[1].dataframe(result.orders, width="stretch", hide_index=True)
    tabs[2].dataframe(result.order_events, width="stretch", hide_index=True)
    tabs[3].dataframe(result.fills, width="stretch", hide_index=True)
    tabs[4].dataframe(result.errors, width="stretch", hide_index=True)
    tabs[5].dataframe(result.account_history, width="stretch", hide_index=True)
