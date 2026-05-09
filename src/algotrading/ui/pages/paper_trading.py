from __future__ import annotations

from algotrading.ui.pages._shared import *


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
    tabs = st.tabs(["Ordenes", "Eventos", "Fills", "Errores", "Cuenta"])
    tabs[0].dataframe(result.orders, width="stretch", hide_index=True)
    tabs[1].dataframe(result.order_events, width="stretch", hide_index=True)
    tabs[2].dataframe(result.fills, width="stretch", hide_index=True)
    tabs[3].dataframe(result.errors, width="stretch", hide_index=True)
    tabs[4].dataframe(result.account_history, width="stretch", hide_index=True)
