from __future__ import annotations

from algotrading.ui.pages._shared import *


def render_robustness_lab() -> None:
    st.title("Robustness Lab")
    st.caption("Train/test, walk-forward y diagnostico critico contra buy and hold.")
    st.info("Robustez no busca el mejor numero: busca detectar fragilidad, dependencia de periodo y posible overfitting.")

    records = list_experiments(st.session_state.experiments_dir)
    source = st.radio(
        "Fuente de configuracion",
        ["Desde experimento guardado", "Manual"],
        index=0 if records else 1,
        horizontal=True,
        help="Usa un experimento guardado para que Results Dashboard pueda reconocer la robustez corrida sobre la misma configuracion.",
    )
    selected_record = None
    data_dir = st.session_state.data_dir
    interval = st.session_state.interval
    start = None
    end = None
    price_column = "adj_close"
    initial_capital_default = 10_000.0
    commission_bps = 1.0
    slippage_bps = 2.0

    if source == "Desde experimento guardado":
        selected_record = _experiment_selector("robustness_source_experiment")
        if selected_record is None:
            st.info("Primero corre y guarda un backtest. Luego podes validar ese experimento aca.")
            return
        details = load_experiment_details(selected_record.path)
        defaults = _experiment_request_defaults(details)
        data_dir = defaults["data_dir"]
        interval = defaults["interval"]
        start = defaults["start"]
        end = defaults["end"]
        price_column = defaults["price_column"]
        strategy_key = defaults["strategy_key"]
        parameters = defaults["strategy_parameters"]
        initial_capital_default = defaults["initial_capital"]
        commission_bps = defaults["commission_bps"]
        slippage_bps = defaults["slippage_bps"]
        if strategy_key not in STRATEGIES:
            st.error(f"La estrategia guardada `{strategy_key}` no esta disponible en el registry actual.")
            return
        _render_experiment_config_summary(selected_record, defaults)
        _render_strategy_research_metadata(strategy_key)
        assets = list_data_assets(data_dir, interval)
        default_symbols = set(defaults["symbols"] or ((defaults["symbol"],) if defaults["symbol"] else ()))
        default_assets = [asset for asset in assets if asset.symbol_hint in default_symbols] or assets[:1]
        selected_assets = st.multiselect(
            "Activos para validar",
            assets,
            default=default_assets,
            format_func=lambda asset: asset.symbol_hint,
            help="El activo original viene seleccionado. Agregar activos permite revisar si la idea depende de un unico caso.",
            key="robustness_experiment_assets",
        )
    else:
        assets = list_data_assets(data_dir, interval)
        if len(assets) < 1:
            st.info("Primero carga datos en Data Manager.")
            return
        selected_assets = st.multiselect(
            "Activos",
            assets,
            default=assets[:1],
            format_func=lambda asset: asset.symbol_hint,
            help="Probar varios activos reduce autoengano de un caso aislado.",
            key="robustness_manual_assets",
        )
        strategy_key = _strategy_selector("robustness_strategy")
        parameters = _render_strategy_parameters(strategy_key, "robustness")

    c1, c2, c3 = st.columns(3)
    train_ratio = c1.slider("Train ratio", 0.1, 0.9, 0.7, 0.05, help=TOOLTIPS["in_sample"])
    run_wf = c2.checkbox("Walk-forward", value=False, help=TOOLTIPS["walk_forward"])
    run_regimes = c3.checkbox("Regimenes", value=True, help="Evalua anos contiguos clasificados como bull/bear y high/low vol.")
    wf1, wf2, wf3, wf4 = st.columns(4)
    robustness_key = selected_record.run_id if selected_record else "manual"
    initial_capital = wf1.number_input(
        "Capital inicial",
        min_value=100.0,
        value=float(initial_capital_default),
        step=500.0,
        key=f"robustness_initial_capital_{robustness_key}",
    )
    wf_train = wf1.number_input("WF train rows", min_value=2, value=756, step=21, disabled=not run_wf)
    wf_test = wf2.number_input("WF test rows", min_value=2, value=252, step=21, disabled=not run_wf)
    wf_step = wf3.number_input("WF step rows", min_value=1, value=252, step=21, disabled=not run_wf)
    regime_min_rows = wf4.number_input("Min filas/regimen", min_value=2, value=60, step=10, disabled=not run_regimes)

    if st.button("Correr robustez", type="primary"):
        if not selected_assets:
            st.error("Selecciona al menos un activo.")
            return
        try:
            request = RobustnessRequest(
                symbols=tuple(asset.symbol_hint for asset in selected_assets),
                strategy_key=strategy_key,
                strategy_parameters=parameters,
                data_dir=data_dir,
                interval=interval,
                start=start,
                end=end,
                price_column=price_column,
                initial_capital=float(initial_capital),
                commission_bps=float(commission_bps),
                slippage_bps=float(slippage_bps),
                train_ratio=float(train_ratio),
                run_walk_forward=run_wf,
                run_regime_analysis=run_regimes,
                wf_train_rows=int(wf_train),
                wf_test_rows=int(wf_test),
                wf_step_rows=int(wf_step),
                regime_min_rows=int(regime_min_rows),
            )
            with st.spinner("Evaluando robustez..."):
                result = run_robustness_request(request)
            st.session_state.latest_robustness = result
            st.session_state.latest_robustness_request = request
            st.session_state.latest_robustness_experiment = str(selected_record.path) if selected_record else ""
            if selected_record:
                save_robustness_for_experiment(selected_record.path, request, result)
        except Exception as exc:
            _show_error(exc)
            return

    result = st.session_state.get("latest_robustness")
    if result is None:
        return
    linked_experiment = st.session_state.get("latest_robustness_experiment")
    if linked_experiment:
        st.caption(f"Robustez asociada a experimento: `{linked_experiment}`")
        summary = build_research_summary(linked_experiment)
        st.info(
            f"Evidence Score actualizado: **{summary.evidence_score.score:.0f}/100**. "
            f"Estado sugerido: **{suggested_journal_status(summary)}**. "
            f"Proxima accion: {summary.recommended_next_action}"
        )
    st.subheader("Comentario critico")
    st.warning(robustness_comment(result.diagnostics))
    st.subheader("Diagnostico")
    st.dataframe(result.diagnostics, width="stretch", hide_index=True)
    st.subheader("Train/Test")
    st.dataframe(result.train_test, width="stretch", hide_index=True)
    if not result.walk_forward.empty:
        st.subheader("Walk-forward")
        st.dataframe(result.walk_forward, width="stretch", hide_index=True)
    if not result.regimes.empty:
        st.subheader("Regimenes de mercado")
        st.warning(regime_comment(result.regimes))
        st.dataframe(result.regimes, width="stretch", hide_index=True)
    _render_linked_journal_status_action(linked_experiment, "robustness")
