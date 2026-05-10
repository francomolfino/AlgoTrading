from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.experiment_adapter import list_experiments, load_experiment_details
from algotrading.ui.adapters.research_adapter import (
    build_research_summary,
    save_stress_for_experiment,
    suggested_journal_status,
)
from algotrading.ui.adapters.stress_adapter import StressTestRequest, run_stress_test_request
from algotrading.ui.adapters.strategy_adapter import STRATEGIES
from algotrading.ui.components.common import (
    render_empty_state as _render_empty_state,
    render_page_header as _render_page_header,
    show_error as _show_error,
)
from algotrading.ui.components.experiment_config import (
    experiment_request_defaults as _experiment_request_defaults,
    render_experiment_config_summary as _render_experiment_config_summary,
)
from algotrading.ui.components.journal_actions import render_linked_journal_status_action as _render_linked_journal_status_action
from algotrading.ui.components.selectors import asset_selector as _asset_selector, experiment_selector as _experiment_selector, strategy_selector as _strategy_selector
from algotrading.ui.components.stress_views import render_stress_result as _render_stress_result
from algotrading.ui.components.strategy_controls import (
    render_strategy_parameters as _render_strategy_parameters,
    render_strategy_research_metadata as _render_strategy_research_metadata,
)
from algotrading.ui.texts import EMPTY_STATES, TOOLTIPS


def render_stress_tests() -> None:
    _render_page_header(
        "Stress Tests",
        "Pruebas adversas para ver si un resultado depende de supuestos optimistas o pocos eventos.",
        area="Research",
        warning="Stress testing sigue siendo research. No valida rentabilidad futura ni habilita trading real.",
    )

    records = list_experiments(st.session_state.experiments_dir)
    source = st.radio(
        "Fuente de configuracion",
        ["Desde experimento guardado", "Manual"],
        index=0 if records else 1,
        horizontal=True,
        help="Para validar un backtest concreto, carga el experimento guardado y evita reconstruir parametros a mano.",
        key="stress_source_mode",
    )
    selected_record = None
    data_dir = st.session_state.data_dir
    interval = st.session_state.interval
    start_default = None
    end_default = None
    price_column_default = "adj_close"
    initial_capital_default = 10_000.0
    commission_default = 1.0
    slippage_default = 2.0

    if source == "Desde experimento guardado":
        selected_record = _experiment_selector("stress_source_experiment")
        if selected_record is None:
            empty = EMPTY_STATES["no_experiments"]
            _render_empty_state(
                empty["title"],
                missing=empty["missing"],
                why_it_matters=empty["why"],
                next_step="Guarda un backtest y volve a Stress Tests para aplicar escenarios adversos al experimento.",
            )
            return
        details = load_experiment_details(selected_record.path)
        defaults = _experiment_request_defaults(details)
        data_dir = defaults["data_dir"]
        interval = defaults["interval"]
        symbol = defaults["symbol"] or (defaults["symbols"][0] if defaults["symbols"] else None)
        start_default = defaults["start"]
        end_default = defaults["end"]
        price_column_default = defaults["price_column"]
        strategy_key = defaults["strategy_key"]
        parameters = defaults["strategy_parameters"]
        initial_capital_default = defaults["initial_capital"]
        commission_default = defaults["commission_bps"]
        slippage_default = defaults["slippage_bps"]
        if not symbol:
            st.error("El experimento no tiene activo asociado.")
            return
        if strategy_key not in STRATEGIES:
            st.error(f"La estrategia guardada `{strategy_key}` no esta disponible en el registry actual.")
            return
        _render_experiment_config_summary(selected_record, defaults)
        _render_strategy_research_metadata(strategy_key)
    else:
        asset = _asset_selector("stress_asset")
        if asset is None:
            empty = EMPTY_STATES["no_data"]
            _render_empty_state(
                empty["title"],
                missing=empty["missing"],
                why_it_matters=empty["why"],
                next_step=empty["next"],
            )
            return
        symbol = asset.symbol_hint
        interval = asset.interval
        strategy_key = _strategy_selector("stress_strategy")
        _render_strategy_research_metadata(strategy_key)
        parameters = _render_strategy_parameters(strategy_key, "stress")

    stress_key = selected_record.run_id if selected_record else f"manual_{symbol}_{strategy_key}"
    with st.form("stress_form"):
        st.subheader("Supuestos base")
        c1, c2, c3, c4 = st.columns(4)
        initial_capital = c1.number_input(
            "Capital inicial",
            min_value=100.0,
            value=float(initial_capital_default),
            step=500.0,
            help=TOOLTIPS["capital"],
            key=f"stress_initial_capital_{stress_key}",
        )
        commission_bps = c2.number_input(
            "Comision bps",
            min_value=0.0,
            value=float(commission_default),
            step=0.5,
            help=TOOLTIPS["commission"],
            key=f"stress_commission_{stress_key}",
        )
        slippage_bps = c3.number_input(
            "Slippage bps",
            min_value=0.0,
            value=float(slippage_default),
            step=0.5,
            help=TOOLTIPS["slippage"],
            key=f"stress_slippage_{stress_key}",
        )
        remove_best_trades = c4.number_input(
            "Quitar mejores trades",
            min_value=0,
            value=3,
            step=1,
            help="Shock post-hoc: resta los mejores PnL para medir dependencia de pocos trades.",
            key=f"stress_remove_best_{stress_key}",
        )

        d1, d2, d3 = st.columns(3)
        price_options = ["adj_close", "close"]
        price_index = 0 if price_column_default not in price_options else price_options.index(price_column_default)
        price_column = d1.selectbox("Precio", price_options, index=price_index, help=TOOLTIPS["adjusted_close"], key=f"stress_price_{stress_key}")
        use_start = d2.checkbox("Filtrar inicio", value=start_default is not None, key=f"stress_use_start_{stress_key}")
        start = d2.date_input("Inicio", value=pd.Timestamp(start_default or "2018-01-01"), disabled=not use_start, key=f"stress_start_{stress_key}")
        use_end = d3.checkbox("Filtrar fin", value=end_default is not None, key=f"stress_use_end_{stress_key}")
        end = d3.date_input("Fin", value=pd.Timestamp(end_default or pd.Timestamp.today()), disabled=not use_end, key=f"stress_end_{stress_key}")
        submitted = st.form_submit_button("Correr stress tests")

    if submitted:
        request = StressTestRequest(
            symbol=symbol,
            strategy_key=strategy_key,
            strategy_parameters=parameters,
            data_dir=data_dir,
            interval=interval,
            start=str(start) if use_start else None,
            end=str(end) if use_end else None,
            price_column=price_column,
            initial_capital=float(initial_capital),
            commission_bps=float(commission_bps),
            slippage_bps=float(slippage_bps),
            remove_best_trades=int(remove_best_trades),
        )
        try:
            with st.spinner("Corriendo escenarios adversos..."):
                result = run_stress_test_request(request)
            st.session_state.latest_stress_test = result
            st.session_state.latest_stress_experiment = str(selected_record.path) if selected_record else ""
            if selected_record:
                save_stress_for_experiment(selected_record.path, result)
        except Exception as exc:
            _show_error(exc)
            return

    result = st.session_state.get("latest_stress_test")
    if result is None:
        _render_empty_state(
            "Sin stress test corrido",
            missing="No hay resultado de stress en esta sesion.",
            why_it_matters="Sin stress no sabemos si el backtest depende de costos bajos, delay ideal o pocos eventos.",
            next_step="Selecciona un experimento guardado y ejecuta los escenarios adversos.",
        )
        return
    linked_experiment = st.session_state.get("latest_stress_experiment")
    if linked_experiment:
        st.caption(f"Stress test asociado a experimento: `{linked_experiment}`")
        summary = build_research_summary(linked_experiment)
        st.info(
            f"Evidence Score actualizado: **{summary.evidence_score.score:.0f}/100**. "
            f"Estado sugerido: **{suggested_journal_status(summary)}**. "
            f"Proxima accion: {summary.recommended_next_action}"
        )
    _render_stress_result(result)
    _render_linked_journal_status_action(linked_experiment, "stress")
