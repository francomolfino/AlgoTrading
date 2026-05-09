from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.backtest_adapter import (
    BacktestRequest,
    BacktestRunArtifacts,
    BacktestPreflight,
    build_result_warnings,
    metric_cards,
    metrics_frame,
    preflight_backtest_request,
    run_backtest_request,
    trade_details_frame,
)
from algotrading.ui.adapters.data_adapter import (
    data_summary,
    download_and_save,
    list_data_assets,
    load_data_file,
    load_symbol_data,
    parse_symbols,
    quality_report_frame,
    validate_data_quality,
)
from algotrading.ui.adapters.experiment_adapter import (
    ExperimentDetails,
    ExperimentRecord,
    compare_experiment_records,
    critical_reading,
    delete_experiment_dir,
    diff_experiment_configs,
    details_metrics_frame,
    filter_records,
    list_experiments,
    load_equity_curves,
    load_experiment_details,
    records_frame,
    sort_records,
)
from algotrading.ui.adapters.guided_adapter import (
    GUIDED_WORKFLOW_STEPS,
    ExperimentDraft,
    build_draft_backtest_request,
    build_draft_robustness_request,
    guided_step_label,
    new_experiment_draft,
    recommend_journal_status,
    update_experiment_draft,
)
from algotrading.ui.adapters.journal_adapter import (
    RESEARCH_NOTE_STATUSES,
    ResearchNotes,
    load_research_notes,
    parse_tags,
    save_research_notes,
    tags_to_text,
)
from algotrading.ui.adapters.paper_adapter import (
    PaperTradingRequest,
    run_paper_trading_request,
    supported_paper_strategies,
)
from algotrading.ui.adapters.portfolio_adapter import (
    PortfolioPreflight,
    PortfolioRequest,
    preflight_portfolio_request,
    run_portfolio_request,
)
from algotrading.ui.adapters.reports_adapter import build_experiment_zip, collect_experiment_report_files
from algotrading.ui.adapters.risk_adapter import RiskSettings
from algotrading.ui.adapters.robustness_adapter import (
    RobustnessRequest,
    regime_comment,
    robustness_comment,
    run_robustness_request,
)
from algotrading.ui.adapters.settings_adapter import UISettings, load_ui_settings, save_ui_settings
from algotrading.ui.adapters.stress_adapter import (
    StressTestResult,
    StressTestRequest,
    equity_curves_frame,
    run_stress_test_request,
)
from algotrading.ui.adapters.strategy_adapter import (
    STRATEGIES,
    default_parameters,
    generate_strategy_signals,
    get_strategy_config,
    signal_events_frame,
    signal_summary,
    strategy_metadata_frame,
    validate_strategy_parameters,
)
from algotrading.ui.charts import (
    render_equity_drawdown_chart,
    render_line_comparison_chart,
    render_price_volume_chart,
)
from algotrading.ui.adapters.evidence_adapter import (
    build_evidence_score_from_details,
    build_evidence_score_from_result,
)
from algotrading.ui.components.evidence_score import render_evidence_score
from algotrading.ui.components.navigation import go_to_page as _go_to_page, nav_button as _nav_button
from algotrading.ui.components.research_verdict import render_research_verdict
from algotrading.ui.adapters.verdict_adapter import (
    build_research_verdict_from_details,
    build_research_verdict_from_result,
)
from algotrading.ui.texts import (
    EDUCATIONAL_WARNING,
    METRIC_EXPLANATIONS,
    PAPER_SIMULATION_WARNING,
    RESEARCH_FLOW_STEPS,
    RESULT_READING_ORDER,
    TOOLTIPS,
)


def render_home() -> None:
    st.title("AlgoTrading Lab")
    st.warning(EDUCATIONAL_WARNING)
    st.write(
        "Interfaz local para investigar estrategias simples, validar datos, correr backtests "
        "y revisar resultados con una lectura critica."
    )

    data_assets = list_data_assets(st.session_state.data_dir, st.session_state.interval)
    experiments = list_experiments(st.session_state.experiments_dir)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Datos locales", len(data_assets))
    col2.metric("Experimentos", len(experiments))
    col3.metric("Timeframe", st.session_state.interval)
    col4.metric("Modo", "simulacion")
    _render_next_step(data_assets, experiments)

    st.subheader("Accesos rapidos")
    cols = st.columns(6)
    _nav_button(cols[0], "Nuevo guiado", "Nuevo experimento guiado")
    _nav_button(cols[1], "Descargar datos", "Data Manager")
    _nav_button(cols[2], "Correr backtest", "Backtest Runner")
    _nav_button(cols[3], "Ver resultados", "Results Dashboard")
    _nav_button(cols[4], "Comparar", "Experiment Explorer")
    _nav_button(cols[5], "Paper simulado", "Paper Trading Simulator")

    st.subheader("Flujo recomendado")
    _render_bullets(RESEARCH_FLOW_STEPS)

    st.subheader("Ultimos experimentos")
    if experiments:
        st.dataframe(records_frame(experiments[:5]), width="stretch", hide_index=True)
    else:
        st.info("Todavia no hay experimentos guardados.")


def render_guided_workflow() -> None:
    st.title("Nuevo experimento guiado")
    st.warning("Modo research educativo. No opera dinero real ni valida rentabilidad futura.")
    st.write("Este flujo te lleva de datos a conclusion sin saltarte controles basicos.")

    draft = _get_guided_draft()
    pending_step = st.session_state.pop("pending_guided_step", None)
    if pending_step is not None:
        st.session_state.guided_step_selector = pending_step
    c1, c2 = st.columns([3, 1])
    selected_step = c1.radio(
        "Paso",
        list(range(1, len(GUIDED_WORKFLOW_STEPS) + 1)),
        index=draft.step - 1,
        format_func=guided_step_label,
        horizontal=True,
        key="guided_step_selector",
    )
    if selected_step != draft.step:
        _set_guided_draft(update_experiment_draft(draft, step=selected_step))
        st.rerun()
    if c2.button("Reiniciar draft", width="stretch"):
        _set_guided_draft(new_experiment_draft(st.session_state.interval))
        st.rerun()

    st.progress(draft.step / len(GUIDED_WORKFLOW_STEPS), text=guided_step_label(draft.step))
    renderers = {
        1: _render_guided_data_step,
        2: _render_guided_strategy_step,
        3: _render_guided_backtest_config_step,
        4: _render_guided_execute_step,
        5: _render_guided_review_step,
        6: _render_guided_robustness_step,
        7: _render_guided_journal_step,
    }
    renderers[draft.step](draft)


def _render_guided_data_step(draft: ExperimentDraft) -> None:
    st.subheader("1. Seleccionar/validar datos")
    assets = list_data_assets(st.session_state.data_dir, st.session_state.interval)
    if not assets:
        st.info("No encontre datos locales para el timeframe actual. Descarga datos antes de crear el experimento.")
        if st.button("Ir a Data Manager"):
            _go_to_page("Data Manager")
        return

    asset = st.selectbox(
        "Activo local",
        assets,
        index=_asset_index(assets, draft.symbol),
        format_func=lambda item: f"{item.symbol_hint} ({item.interval}, {item.rows} filas)",
        help=TOOLTIPS["ticker"],
        key="guided_asset_select",
    )
    try:
        frame = load_data_file(asset.path)
        report = validate_data_quality(frame)
    except Exception as exc:
        _show_error(exc)
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas", report.rows)
    c2.metric("Inicio", report.start_date)
    c3.metric("Fin", report.end_date)
    c4.metric("Estado", "ok" if report.is_valid else "revisar")
    st.dataframe(quality_report_frame(report), width="stretch", hide_index=True)
    _render_data_quality_reading(report)

    price_column = "adj_close" if "adj_close" in frame else "close"
    render_price_volume_chart(
        frame.tail(500),
        title=f"{asset.symbol_hint} - ultimas barras disponibles",
        price_column=price_column,
        height=430,
    )
    if st.button("Usar estos datos y continuar", type="primary", disabled=not report.is_valid):
        _set_guided_draft(
            update_experiment_draft(
                draft,
                symbol=asset.symbol_hint,
                interval=asset.interval,
                price_column=price_column,
                experiment_name=f"guided_{asset.symbol_hint}_{draft.strategy_key}",
                backtest_request=None,
                backtest_artifacts=None,
                robustness_request=None,
                robustness_result=None,
                step=2,
            )
        )
        st.rerun()


def _render_guided_strategy_step(draft: ExperimentDraft) -> None:
    st.subheader("2. Elegir estrategia")
    strategy_keys = list(STRATEGIES)
    strategy_key = st.selectbox(
        "Estrategia",
        strategy_keys,
        index=_strategy_index(strategy_keys, draft.strategy_key),
        format_func=lambda key: STRATEGIES[key].label,
        key="guided_strategy_select",
    )
    config = get_strategy_config(strategy_key)
    st.write(config.description)
    st.caption(config.risk_note)
    _render_strategy_research_metadata(strategy_key)
    parameters = _render_strategy_parameters(strategy_key, "guided_strategy")

    if draft.symbol:
        try:
            frame, _ = load_symbol_data(st.session_state.data_dir, draft.symbol, draft.interval)
            warnings = validate_strategy_parameters(strategy_key, parameters, frame_length=len(frame))
            for warning in warnings:
                st.warning(warning)
            signal_frame = generate_strategy_signals(frame, strategy_key, parameters, price_column=draft.price_column)
            summary = signal_summary(signal_frame)
            cols = st.columns(4)
            cols[0].metric("Entradas", summary["entries"])
            cols[1].metric("Salidas", summary["exits"])
            cols[2].metric("Barras long", summary["bars_in_market"])
            cols[3].metric("Exposicion", f"{summary['exposure_ratio']:.1%}")
            _render_signal_reading(strategy_key, summary, len(signal_frame))
        except Exception as exc:
            _show_error(exc)
            return

    if st.button("Usar estrategia y continuar", type="primary"):
        try:
            validate_strategy_parameters(strategy_key, parameters)
        except Exception as exc:
            _show_error(exc)
            return
        _set_guided_draft(
            update_experiment_draft(
                draft,
                strategy_key=strategy_key,
                strategy_parameters=parameters,
                experiment_name=f"guided_{draft.symbol or 'asset'}_{strategy_key}",
                backtest_request=None,
                backtest_artifacts=None,
                robustness_request=None,
                robustness_result=None,
                step=3,
            )
        )
        st.rerun()


def _render_guided_backtest_config_step(draft: ExperimentDraft) -> None:
    st.subheader("3. Configurar backtest")
    if not draft.symbol:
        st.warning("Primero selecciona datos.")
        if st.button("Volver a datos"):
            _set_guided_draft(update_experiment_draft(draft, step=1))
            st.rerun()
        return

    with st.form("guided_backtest_config_form"):
        c1, c2, c3 = st.columns(3)
        price_column = c1.selectbox(
            "Precio",
            ["adj_close", "close"],
            index=0 if draft.price_column == "adj_close" else 1,
            help=TOOLTIPS["adjusted_close"],
        )
        initial_capital = c2.number_input("Capital inicial", min_value=100.0, value=float(draft.initial_capital), step=500.0, help=TOOLTIPS["capital"])
        experiment_name = c3.text_input("Nombre experimento", value=draft.experiment_name)

        c4, c5 = st.columns(2)
        commission_bps = c4.number_input("Comision bps", min_value=0.0, value=float(draft.commission_bps), step=0.5, help=TOOLTIPS["commission"])
        slippage_bps = c5.number_input("Slippage bps", min_value=0.0, value=float(draft.slippage_bps), step=0.5, help=TOOLTIPS["slippage"])

        d1, d2 = st.columns(2)
        use_start = d1.checkbox("Filtrar inicio", value=draft.start is not None)
        start = d1.date_input("Inicio", value=pd.Timestamp(draft.start or "2018-01-01"), disabled=not use_start)
        use_end = d2.checkbox("Filtrar fin", value=draft.end is not None)
        end = d2.date_input("Fin", value=pd.Timestamp(draft.end or pd.Timestamp.today()), disabled=not use_end)
        risk = _render_risk_settings("guided_risk")
        notes = st.text_area("Notas iniciales", value=draft.notes, help="Hipotesis o contexto antes de mirar resultados.")
        submitted = st.form_submit_button("Validar y continuar")

    if submitted:
        configured = update_experiment_draft(
            draft,
            price_column=price_column,
            initial_capital=float(initial_capital),
            commission_bps=float(commission_bps),
            slippage_bps=float(slippage_bps),
            start=str(start) if use_start else None,
            end=str(end) if use_end else None,
            risk=risk,
            experiment_name=experiment_name,
            notes=notes,
        )
        try:
            request = build_draft_backtest_request(
                configured,
                data_dir=st.session_state.data_dir,
                experiments_root=st.session_state.experiments_dir,
            )
            preflight = preflight_backtest_request(request)
            _render_backtest_preflight(preflight)
            if not preflight.can_run:
                st.error("Corregi los errores bloqueantes antes de ejecutar.")
                return
            _set_guided_draft(update_experiment_draft(configured, backtest_request=request, step=4))
            st.rerun()
        except Exception as exc:
            _show_error(exc)


def _render_guided_execute_step(draft: ExperimentDraft) -> None:
    st.subheader("4. Ejecutar")
    if draft.backtest_request is None:
        st.warning("Primero valida la configuracion del backtest.")
        if st.button("Volver a configuracion"):
            _set_guided_draft(update_experiment_draft(draft, step=3))
            st.rerun()
        return

    st.write(f"Activo: `{draft.backtest_request.symbol}`")
    st.write(f"Estrategia: `{STRATEGIES[draft.backtest_request.strategy_key].label}`")
    st.write(f"Experimento: `{draft.backtest_request.experiment_name}`")
    st.caption("El experimento guiado se guarda siempre para poder adjuntar journal al final.")
    if st.button("Ejecutar backtest", type="primary"):
        try:
            with st.spinner("Ejecutando backtest guiado..."):
                artifacts = run_backtest_request(draft.backtest_request)
            st.session_state.latest_backtest = artifacts
            _set_guided_draft(update_experiment_draft(draft, backtest_artifacts=artifacts, step=5))
            st.rerun()
        except Exception as exc:
            _show_error(exc)


def _render_guided_review_step(draft: ExperimentDraft) -> None:
    st.subheader("5. Revisar resultados")
    if draft.backtest_artifacts is None:
        st.warning("Todavia no hay resultado para revisar.")
        if st.button("Volver a ejecutar"):
            _set_guided_draft(update_experiment_draft(draft, step=4))
            st.rerun()
        return

    _render_backtest_result(draft.backtest_artifacts)
    c1, c2 = st.columns(2)
    if c1.button("Continuar a robustez", type="primary", width="stretch"):
        _set_guided_draft(update_experiment_draft(draft, step=6))
        st.rerun()
    if c2.button("Saltar a notas", width="stretch"):
        _set_guided_draft(update_experiment_draft(draft, step=7))
        st.rerun()


def _render_guided_robustness_step(draft: ExperimentDraft) -> None:
    st.subheader("6. Correr robustez")
    if draft.backtest_artifacts is None:
        st.warning("Corre el backtest antes de evaluar robustez.")
        return

    assets = list_data_assets(st.session_state.data_dir, draft.interval)
    default_assets = [asset for asset in assets if asset.symbol_hint == draft.symbol] or assets[:1]
    selected_assets = st.multiselect(
        "Activos para robustez",
        assets,
        default=default_assets,
        format_func=lambda asset: asset.symbol_hint,
        help="Inclui mas activos si existen datos locales compatibles.",
    )
    with st.form("guided_robustness_form"):
        c1, c2, c3 = st.columns(3)
        train_ratio = c1.slider("Train ratio", 0.1, 0.9, 0.7, 0.05, help=TOOLTIPS["in_sample"])
        run_wf = c2.checkbox("Walk-forward", value=True, help=TOOLTIPS["walk_forward"])
        run_regimes = c3.checkbox("Regimenes", value=True, help="Evalua anos contiguos bull/bear y high/low vol.")
        r1, r2, r3, r4 = st.columns(4)
        wf_train = r1.number_input("WF train rows", min_value=2, value=756, step=21, disabled=not run_wf)
        wf_test = r2.number_input("WF test rows", min_value=2, value=252, step=21, disabled=not run_wf)
        wf_step = r3.number_input("WF step rows", min_value=1, value=252, step=21, disabled=not run_wf)
        regime_min = r4.number_input("Min filas/regimen", min_value=2, value=60, step=10, disabled=not run_regimes)
        submitted = st.form_submit_button("Correr robustez")

    if submitted:
        try:
            request = build_draft_robustness_request(
                draft,
                symbols=tuple(asset.symbol_hint for asset in selected_assets),
                data_dir=st.session_state.data_dir,
                train_ratio=float(train_ratio),
                run_walk_forward=run_wf,
                run_regime_analysis=run_regimes,
                wf_train_rows=int(wf_train),
                wf_test_rows=int(wf_test),
                wf_step_rows=int(wf_step),
                regime_min_rows=int(regime_min),
            )
            with st.spinner("Corriendo robustez guiada..."):
                result = run_robustness_request(request)
            st.session_state.latest_robustness = result
            st.session_state.latest_robustness_request = request
            st.session_state.latest_robustness_experiment = str(draft.backtest_artifacts.experiment_dir or "")
            suggested_status = recommend_journal_status(
                robustness_result=result,
                fallback=draft.journal_status,
            )
            _set_guided_draft(
                update_experiment_draft(
                    draft,
                    robustness_request=request,
                    robustness_result=result,
                    journal_status=suggested_status,
                    step=7,
                )
            )
            st.rerun()
        except Exception as exc:
            _show_error(exc)

    if draft.robustness_result is not None:
        st.warning(robustness_comment(draft.robustness_result.diagnostics))
        st.dataframe(draft.robustness_result.diagnostics, width="stretch", hide_index=True)


def _render_guided_journal_step(draft: ExperimentDraft) -> None:
    st.subheader("7. Guardar notas/conclusion")
    artifacts = draft.backtest_artifacts
    if artifacts is None or artifacts.experiment_dir is None:
        st.warning("No hay experimento guardado para adjuntar notas.")
        return

    saved_notes = load_research_notes(artifacts.experiment_dir)
    matched_robustness = draft.robustness_result or _matching_robustness(
        draft.strategy_key,
        draft.strategy_parameters,
        draft.symbol,
    )
    matched_stress = _matching_stress_test(
        draft.strategy_key,
        draft.strategy_parameters,
        draft.symbol,
        interval=draft.interval,
        start=draft.start,
        end=draft.end,
    )
    suggested_status = recommend_journal_status(
        robustness_result=matched_robustness,
        stress_result=matched_stress,
        fallback=draft.journal_status if draft.journal_status in RESEARCH_NOTE_STATUSES else "Needs Review",
    )
    current_status = saved_notes.status
    if saved_notes.status in {"Draft", "Needs Review"} and suggested_status in RESEARCH_NOTE_STATUSES:
        current_status = suggested_status
    elif draft.journal_status in RESEARCH_NOTE_STATUSES and saved_notes.status == "Draft":
        current_status = draft.journal_status
    st.info(
        f"Estado sugerido por la evidencia disponible: **{suggested_status}**. "
        "Es una ayuda editorial: revisa metricas, benchmark y notas antes de guardar."
    )
    with st.form("guided_journal_form"):
        c1, c2 = st.columns([2, 1])
        status = c1.selectbox(
            "Estado",
            RESEARCH_NOTE_STATUSES,
            index=RESEARCH_NOTE_STATUSES.index(current_status),
            help="Estado editorial del experimento. No cambia metricas.",
        )
        favorite = c2.checkbox("Favorito", value=draft.favorite or saved_notes.favorite)
        tags_text = st.text_input("Tags", value=tags_to_text(draft.tags or saved_notes.tags))
        hypothesis = st.text_area("Hipotesis", value=draft.hypothesis or saved_notes.hypothesis, height=90)
        conclusion = st.text_area("Conclusion", value=draft.conclusion or saved_notes.conclusion, height=100)
        next_test = st.text_area("Proximo test", value=draft.next_test or saved_notes.next_test, height=80)
        submitted = st.form_submit_button("Guardar notas y finalizar")

    if submitted:
        try:
            notes = ResearchNotes(
                status=status,
                hypothesis=hypothesis,
                conclusion=conclusion,
                next_test=next_test,
                tags=parse_tags(tags_text),
                favorite=favorite,
            )
            path = save_research_notes(artifacts.experiment_dir, notes)
            _set_guided_draft(
                update_experiment_draft(
                    draft,
                    journal_status=status,
                    hypothesis=hypothesis,
                    conclusion=conclusion,
                    next_test=next_test,
                    tags=parse_tags(tags_text),
                    favorite=favorite,
                    journal_saved_path=path,
                )
            )
            st.success(f"Notas guardadas en `{path}`")
        except Exception as exc:
            _show_error(exc)

    if draft.journal_saved_path:
        st.success(f"Workflow completo. Journal: `{draft.journal_saved_path}`")
    c1, c2 = st.columns(2)
    if c1.button("Abrir Experiment Explorer", width="stretch"):
        _go_to_page("Experiment Explorer")
    if c2.button("Crear otro experimento", width="stretch"):
        _set_guided_draft(new_experiment_draft(st.session_state.interval))
        st.rerun()


def render_data_manager() -> None:
    st.title("Data Manager")
    st.caption("Descarga, recarga y valida datos historicos locales.")
    download_tab, explore_tab = st.tabs(["Descargar datos", "Explorar datos"])

    with download_tab:
        with st.form("download_data_form"):
            symbols_raw = st.text_input("Tickers", value="SPY QQQ", help=TOOLTIPS["ticker"])
            col1, col2, col3 = st.columns(3)
            start = col1.date_input("Fecha inicial", value=pd.Timestamp("2018-01-01"), help=TOOLTIPS["date_range"])
            end_enabled = col2.checkbox("Usar fecha final", value=False)
            end = col2.date_input("Fecha final", value=pd.Timestamp.today(), disabled=not end_enabled)
            interval = col3.selectbox("Timeframe", ["1d", "1wk", "1mo"], index=0, help=TOOLTIPS["timeframe"])
            file_format = st.selectbox("Formato", ["csv", "parquet"], index=0)
            submitted = st.form_submit_button("Descargar y guardar")

        if submitted:
            symbols = parse_symbols(symbols_raw)
            if not symbols:
                st.error("Ingresa al menos un ticker.")
            else:
                with st.spinner("Descargando datos historicos..."):
                    for symbol in symbols:
                        try:
                            frame, path = download_and_save(
                                symbol=symbol,
                                start=str(start),
                                end=str(end) if end_enabled else None,
                                interval=interval,
                                data_dir=st.session_state.data_dir,
                                file_format=file_format,
                            )
                            st.success(f"{symbol}: {len(frame)} filas guardadas en {path}")
                        except Exception as exc:
                            _show_error(exc)

    with explore_tab:
        asset = _asset_selector("data_manager_asset")
        if asset is None:
            st.info("No encontre datos locales. Descarga un activo primero.")
            return
        try:
            frame = load_data_file(asset.path)
            report = validate_data_quality(frame)
        except Exception as exc:
            _show_error(exc)
            return

        st.write(f"Archivo: `{asset.path}`")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Filas", report.rows)
        m2.metric("Inicio", report.start_date)
        m3.metric("Fin", report.end_date)
        m4.metric("Estado", "ok" if report.is_valid else "revisar")
        st.dataframe(quality_report_frame(report), width="stretch", hide_index=True)
        _render_data_quality_reading(report)
        if report.null_counts:
            st.warning(f"Valores faltantes detectados: {report.null_counts}", icon="!")
        if report.gap_count:
            st.warning("Hay gaps grandes de fechas. Puede ser normal en ETFs, pero revisalo.", icon="!")

        price_column = "adj_close" if "adj_close" in frame else "close"
        render_price_volume_chart(
            frame,
            title=f"{asset.symbol_hint} - precio y volumen",
            price_column=price_column,
            height=520,
        )
        st.subheader("Resumen estadistico")
        st.dataframe(data_summary(frame), width="stretch", hide_index=True)
        st.subheader("Vista previa")
        st.dataframe(frame.tail(50), width="stretch", hide_index=True)


def render_strategy_lab() -> None:
    st.title("Strategy Lab")
    st.info("Esta pantalla muestra intenciones de senal, no rentabilidad. El backtester aplica delay para evitar lookahead.")
    asset = _asset_selector("strategy_asset")
    if asset is None:
        st.info("Primero carga datos en Data Manager.")
        return

    strategy_key = _strategy_selector("strategy_lab_strategy")
    config = get_strategy_config(strategy_key)
    st.write(config.description)
    st.caption(config.risk_note)
    _render_strategy_research_metadata(strategy_key)
    parameters = _render_strategy_parameters(strategy_key, "strategy_lab")

    try:
        frame = load_data_file(asset.path)
        warnings = validate_strategy_parameters(strategy_key, parameters, frame_length=len(frame))
        for warning in warnings:
            st.warning(warning)
        signal_frame = generate_strategy_signals(frame, strategy_key, parameters)
        summary = signal_summary(signal_frame)
    except Exception as exc:
        _show_error(exc)
        return

    cols = st.columns(4)
    cols[0].metric("Entradas", summary["entries"])
    cols[1].metric("Salidas", summary["exits"])
    cols[2].metric("Barras long", summary["bars_in_market"])
    cols[3].metric("Exposicion senal", f"{summary['exposure_ratio']:.1%}")
    _render_signal_reading(strategy_key, summary, len(signal_frame))
    render_price_volume_chart(
        signal_frame,
        title=f"{asset.symbol_hint} - senales {STRATEGIES[strategy_key].label}",
        price_column="adj_close" if "adj_close" in signal_frame else "close",
        overlay_columns=_price_overlay_columns(signal_frame),
        signal_column="signal",
        height=560,
    )
    _render_signal_tables(signal_frame)


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


def render_experiment_explorer() -> None:
    st.title("Experiment Explorer")
    records = list_experiments(st.session_state.experiments_dir)
    if not records:
        st.info("Todavia no hay experimentos guardados.")
        return

    f1, f2, f3, f4 = st.columns(4)
    strategy_filter = f1.text_input("Filtrar estrategia", value="")
    symbol_filter = f2.text_input("Filtrar activo", value="")
    status_filter = f3.selectbox("Estado research", ["Todos", *RESEARCH_NOTE_STATUSES])
    sort_by = f4.selectbox("Ordenar por", ["fecha", "retorno", "sharpe", "drawdown", "nombre", "estado", "favoritos"])
    favorites_only = st.checkbox("Mostrar solo favoritos", value=False)

    filtered = filter_records(
        records,
        strategy_filter or None,
        symbol_filter or None,
        status=None if status_filter == "Todos" else status_filter,
        favorites_only=favorites_only,
    )
    filtered = sort_records(filtered, sort_by)
    frame = records_frame(filtered)
    st.dataframe(frame, width="stretch", hide_index=True)
    if not filtered:
        st.info("No hay experimentos para esos filtros.")
        return

    _render_experiment_journal(filtered)

    selected_paths = st.multiselect(
        "Comparar experimentos",
        options=[str(record.path) for record in filtered],
        format_func=lambda path: Path(path).name,
    )
    selected_records = [record for record in filtered if str(record.path) in selected_paths]
    if selected_records:
        comparison = compare_experiment_records(selected_records)
        st.subheader("Tabla comparativa")
        st.dataframe(comparison, width="stretch", hide_index=True)
        curves = load_equity_curves(selected_records)
        if curves:
            st.subheader("Equity curves")
            render_line_comparison_chart(
                _combined_equity_frame(curves),
                title="Comparacion de equity curves",
                height=430,
            )
        if _comparison_has_mismatch(comparison):
            st.warning("Estas comparando activos o periodos distintos. El ranking puede ser enganoso.")
        if len(selected_records) >= 2:
            with st.expander("Diferencias de configuracion", expanded=False):
                only_changed = st.checkbox("Mostrar solo campos distintos", value=True)
                try:
                    diff = diff_experiment_configs(selected_records, only_changed=only_changed)
                    st.dataframe(diff, width="stretch", hide_index=True)
                except Exception as exc:
                    _show_error(exc)

    csv = frame.to_csv(index=False).encode("utf-8")
    st.download_button("Exportar listado CSV", data=csv, file_name="experiments_summary.csv", mime="text/csv")

    with st.expander("Eliminar experimento", expanded=False):
        st.warning("Borrado local irreversible. Usalo solo para limpiar runs descartables.")
        delete_record = st.selectbox(
            "Experimento a eliminar",
            filtered,
            format_func=lambda record: record.path.name,
            key="delete_experiment_select",
        )
        confirmation = st.text_input(
            "Confirmacion",
            help="Escribi exactamente el nombre de la carpeta del experimento.",
            placeholder=delete_record.path.name if delete_record else "",
        )
        confirm_checkbox = st.checkbox("Entiendo que esto borra archivos locales")
        if st.button("Eliminar experimento", disabled=not confirm_checkbox):
            try:
                deleted = delete_experiment_dir(
                    delete_record.path,
                    experiments_root=st.session_state.experiments_dir,
                    confirmation=confirmation,
                )
                st.success(f"Experimento eliminado: {deleted}")
                st.rerun()
            except Exception as exc:
                _show_error(exc)


def _render_experiment_journal(records: list[ExperimentRecord]) -> None:
    with st.expander("Journal de research", expanded=False):
        st.caption("Usalo para separar hipotesis, conclusion y proximo test de las metricas del backtest.")
        record = st.selectbox(
            "Experimento",
            records,
            format_func=lambda item: f"{item.name} - {item.strategy} - {', '.join(item.symbols)}",
            key="journal_experiment_select",
        )
        notes = load_research_notes(record.path)
        if notes.updated_at_utc:
            st.caption(f"Ultima actualizacion: {notes.updated_at_utc}")

        with st.form(f"journal_form_{record.path.name}"):
            c1, c2 = st.columns([2, 1])
            status = c1.selectbox(
                "Estado",
                RESEARCH_NOTE_STATUSES,
                index=RESEARCH_NOTE_STATUSES.index(notes.status),
                help="Estado editorial del experimento. No cambia las metricas.",
            )
            favorite = c2.checkbox("Favorito", value=notes.favorite, help="Marca experimentos que queres revisar rapido.")
            tags_text = st.text_input(
                "Tags",
                value=tags_to_text(notes.tags),
                help="Separalos por coma. Ejemplo: trend, btc, revisar.",
            )
            hypothesis = st.text_area(
                "Hipotesis",
                value=notes.hypothesis,
                height=90,
                help="Que idea estas intentando probar antes de mirar resultados.",
            )
            conclusion = st.text_area(
                "Conclusion",
                value=notes.conclusion,
                height=90,
                help="Que aprendiste despues de revisar metricas, benchmark y robustez.",
            )
            next_test = st.text_area(
                "Proximo test",
                value=notes.next_test,
                height=80,
                help="Siguiente prueba concreta: otro activo, periodo, walk-forward, stress test, etc.",
            )
            submitted = st.form_submit_button("Guardar journal")

        if submitted:
            try:
                path = save_research_notes(
                    record.path,
                    ResearchNotes(
                        status=status,
                        hypothesis=hypothesis,
                        conclusion=conclusion,
                        next_test=next_test,
                        tags=parse_tags(tags_text),
                        favorite=favorite,
                    ),
                )
                st.success(f"Journal guardado en `{path}`")
                st.rerun()
            except Exception as exc:
                _show_error(exc)


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
        except Exception as exc:
            _show_error(exc)
            return

    result = st.session_state.get("latest_robustness")
    if result is None:
        return
    linked_experiment = st.session_state.get("latest_robustness_experiment")
    if linked_experiment:
        st.caption(f"Robustez asociada a experimento: `{linked_experiment}`")
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


def render_stress_tests() -> None:
    st.title("Stress Tests")
    st.caption("Pruebas adversas para ver si un resultado depende de supuestos optimistas o pocos eventos.")
    st.warning("Stress testing sigue siendo research. No valida rentabilidad futura ni habilita trading real.")

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
            st.info("Primero corre y guarda un backtest. Luego podes aplicar stress tests sobre ese experimento.")
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
            st.info("Primero carga datos en Data Manager.")
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
        except Exception as exc:
            _show_error(exc)
            return

    result = st.session_state.get("latest_stress_test")
    if result is None:
        st.info("Configura una estrategia y corre el primer stress test.")
        return
    linked_experiment = st.session_state.get("latest_stress_experiment")
    if linked_experiment:
        st.caption(f"Stress test asociado a experimento: `{linked_experiment}`")
    _render_stress_result(result)
    _render_linked_journal_status_action(linked_experiment, "stress")


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


def render_reports_export() -> None:
    st.title("Reports / Export")
    record = _experiment_selector("reports_experiment")
    if record is None:
        st.info("No hay experimentos guardados.")
        return
    files = collect_experiment_report_files(record.path)
    st.write(f"Carpeta: `{record.path}`")
    try:
        st.download_button(
            "Descargar experimento completo ZIP",
            data=build_experiment_zip(record.path),
            file_name=f"{record.path.name}.zip",
            mime="application/zip",
        )
    except Exception as exc:
        _show_error(exc)
    if not files:
        st.warning("No encontre archivos exportables.")
        return
    for report_file in files:
        col1, col2 = st.columns([3, 1])
        col1.write(f"`{report_file.label}`")
        col2.download_button(
            "Descargar",
            data=report_file.path.read_bytes(),
            file_name=report_file.path.name,
            mime=report_file.mime,
            key=f"download_{report_file.path}",
        )


def render_settings() -> None:
    st.title("Settings")
    current = UISettings(
        data_dir=st.session_state.data_dir,
        experiments_dir=st.session_state.experiments_dir,
        interval=st.session_state.interval,
        debug=st.session_state.debug,
    )
    with st.form("settings_form"):
        data_dir = st.text_input("Carpeta de datos", value=current.data_dir)
        experiments_dir = st.text_input("Carpeta de experimentos", value=current.experiments_dir)
        default_tickers = st.text_input("Tickers default", value=current.default_tickers)
        initial_capital = st.number_input("Capital default", min_value=100.0, value=current.initial_capital, step=500.0)
        commission_bps = st.number_input("Comision default bps", min_value=0.0, value=current.commission_bps, step=0.5)
        slippage_bps = st.number_input("Slippage default bps", min_value=0.0, value=current.slippage_bps, step=0.5)
        interval = st.selectbox("Timeframe default", ["1d", "1wk", "1mo"], index=["1d", "1wk", "1mo"].index(current.interval))
        debug = st.checkbox("Modo debug", value=current.debug)
        submitted = st.form_submit_button("Guardar settings")
    if submitted:
        settings = UISettings(
            data_dir=data_dir,
            experiments_dir=experiments_dir,
            default_tickers=default_tickers,
            initial_capital=float(initial_capital),
            commission_bps=float(commission_bps),
            slippage_bps=float(slippage_bps),
            interval=interval,
            debug=debug,
        )
        try:
            path = save_ui_settings(settings)
            st.session_state.data_dir = settings.data_dir
            st.session_state.experiments_dir = settings.experiments_dir
            st.session_state.interval = settings.interval
            st.session_state.debug = settings.debug
            st.success(f"Settings guardados en {path}")
        except Exception as exc:
            _show_error(exc)


def render_placeholder(page: str) -> None:
    st.title(page)
    st.info(
        "Pantalla pendiente para la segunda iteracion. La base ya quedo preparada "
        "con adapters y navegacion segura."
    )
    if page == "Paper Trading Simulator":
        st.warning("Modo simulacion. No se envian ordenes reales.")


def _render_backtest_result(artifacts: BacktestRunArtifacts) -> None:
    result = artifacts.result
    st.subheader(f"Resultado: {artifacts.request.symbol} - {artifacts.strategy_name}")
    render_research_verdict(
        build_research_verdict_from_result(
            result,
            parameter_count=len(artifacts.request.strategy_parameters),
            symbol_count=1,
        )
    )
    render_evidence_score(
        build_evidence_score_from_result(
            result,
            parameter_count=len(artifacts.request.strategy_parameters),
            symbol_count=1,
            strategy_key=artifacts.request.strategy_key,
            symbol=artifacts.request.symbol,
            robustness_result=_matching_robustness(
                artifacts.request.strategy_key,
                artifacts.request.strategy_parameters,
                artifacts.request.symbol,
            ),
            stress_result=_matching_stress_test(
                artifacts.request.strategy_key,
                artifacts.request.strategy_parameters,
                artifacts.request.symbol,
                interval=artifacts.request.interval,
                start=artifacts.request.start,
                end=artifacts.request.end,
            ),
        )
    )
    _render_result_reading_order()
    cols = st.columns(6)
    for column, (label, value) in zip(cols, metric_cards(result.metrics)):
        column.metric(label, value)
    _render_equity_and_drawdown(result.equity_curve)
    st.subheader("Metricas")
    st.dataframe(metrics_frame(result.metrics), width="stretch", hide_index=True)
    _render_metric_guide()
    _render_critical_reading_from_result(artifacts)
    if artifacts.experiment_dir:
        st.success(f"Experimento guardado en `{artifacts.experiment_dir}`")
    if artifacts.report_path and artifacts.report_path.exists():
        st.write(f"Reporte: `{artifacts.report_path}`")
        st.download_button(
            "Descargar reporte Markdown",
            data=artifacts.report_path.read_text(encoding="utf-8"),
            file_name="report.md",
            mime="text/markdown",
        )
    st.subheader("Trades")
    _render_trade_details(result.trades)


def _render_experiment_details(details: ExperimentDetails) -> None:
    st.subheader(f"{details.path.name}")
    if details.notes:
        st.info(details.notes)
    c1, c2, c3 = st.columns(3)
    c1.write(f"Activo: `{details.symbol}`")
    c2.write(f"Ejecucion: `{details.metadata.get('created_at_utc', 'n/a')}`")
    c3.write(f"Path: `{details.path}`")

    if not details.metrics:
        st.warning("No encontre metrics.json en este experimento.")
        return
    render_research_verdict(build_research_verdict_from_details(details))
    strategy_config = details.config.get("strategy", {})
    strategy_parameters = strategy_config.get("parameters", {})
    render_evidence_score(
        build_evidence_score_from_details(
            details,
            robustness_result=_matching_robustness(
                str(strategy_config.get("name", "")),
                strategy_parameters if isinstance(strategy_parameters, dict) else {},
                details.symbol,
            ),
            stress_result=_matching_stress_test(
                str(strategy_config.get("name", "")),
                strategy_parameters if isinstance(strategy_parameters, dict) else {},
                details.symbol,
                interval=details.config.get("interval"),
                start=details.config.get("start"),
                end=details.config.get("end"),
            ),
        )
    )
    _render_result_reading_order()
    cols = st.columns(6)
    for column, (label, value) in zip(cols, metric_cards(details.metrics)):
        column.metric(label, value)
    if not details.equity.empty:
        _render_equity_and_drawdown(details.equity)
    st.subheader("Lectura critica")
    for warning in critical_reading(details):
        st.warning(warning)
    st.subheader("Metricas")
    metrics_table = details.metrics_table if not details.metrics_table.empty else details_metrics_frame(details)
    st.dataframe(metrics_table, width="stretch", hide_index=True)
    _render_metric_guide()

    tabs = st.tabs(["Trades", "Retornos mensuales", "Mejores/peores periodos", "Config"])
    with tabs[0]:
        _render_trade_details(details.trades)
    with tabs[1]:
        st.dataframe(details.monthly_returns, width="stretch", hide_index=True)
    with tabs[2]:
        st.dataframe(details.period_extremes, width="stretch", hide_index=True)
    with tabs[3]:
        st.json(details.config)


def _render_equity_and_drawdown(equity: pd.DataFrame) -> None:
    if equity.empty:
        st.warning("No hay equity curve para mostrar.")
        return
    data = equity.copy()
    data["date"] = pd.to_datetime(data["date"])
    render_equity_drawdown_chart(data, title="Equity y drawdown", height=560)


def _render_trade_details(trades: pd.DataFrame) -> None:
    if trades.empty:
        st.info("No hay trades cerrados para mostrar.")
        return
    try:
        display = trade_details_frame(trades)
    except Exception as exc:
        st.warning("No pude construir la vista amigable de trades. Muestro tabla cruda.")
        _show_error(exc)
        st.dataframe(trades, width="stretch", hide_index=True)
        return

    wins = int((display["pnl"] > 0).sum())
    losses = int((display["pnl"] <= 0).sum())
    avg_roi = float(display["roi_pct"].mean()) if len(display) else 0.0
    total_pnl = float(display["pnl"].sum()) if len(display) else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trades cerrados", len(display))
    c2.metric("Ganadores / perdedores", f"{wins} / {losses}")
    c3.metric("ROI promedio", f"{avg_roi:.2f}%")
    c4.metric("PnL total", f"{total_pnl:,.2f}")

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "trade": st.column_config.NumberColumn("Trade", format="%d"),
            "entrada": st.column_config.TextColumn("Entrada"),
            "salida": st.column_config.TextColumn("Salida"),
            "precio_entrada": st.column_config.NumberColumn("Precio entrada", format="%.4f"),
            "precio_salida": st.column_config.NumberColumn("Precio salida", format="%.4f"),
            "cantidad": st.column_config.NumberColumn("Cantidad comprada", format="%.6f"),
            "capital_entrada": st.column_config.NumberColumn("Capital entrada", format="%.2f"),
            "valor_salida": st.column_config.NumberColumn("Valor salida", format="%.2f"),
            "pnl": st.column_config.NumberColumn("PnL", format="%.2f"),
            "roi_pct": st.column_config.NumberColumn("ROI", format="%.2f%%"),
            "barras": st.column_config.NumberColumn("Barras", format="%d"),
            "motivo_salida": st.column_config.TextColumn("Motivo salida"),
            "comisiones": st.column_config.NumberColumn("Comisiones", format="%.2f"),
        },
    )
    with st.expander("Ver tabla cruda de trades", expanded=False):
        st.dataframe(trades, width="stretch", hide_index=True)


def _render_signal_tables(signal_frame: pd.DataFrame) -> None:
    st.subheader("Tablas de senales")
    st.caption("La vista mas util suele ser cambios de senal: entradas y salidas. Las ultimas filas solas pueden enganar.")
    price_column = "adj_close" if "adj_close" in signal_frame else "close"
    events = signal_events_frame(signal_frame, price_column=price_column)
    tabs = st.tabs(["Cambios de senal", "Primeras filas", "Ultimas filas", "Dataset completo"])
    with tabs[0]:
        if events.empty:
            st.info("No hubo cambios de senal en el periodo seleccionado.")
        else:
            st.dataframe(
                events,
                width="stretch",
                hide_index=True,
                column_config={
                    "price": st.column_config.NumberColumn("Precio", format="%.4f"),
                    "signal": st.column_config.NumberColumn("Signal", format="%d"),
                    "previous_signal": st.column_config.NumberColumn("Signal previa", format="%d"),
                },
            )
    with tabs[1]:
        st.dataframe(signal_frame.head(80), width="stretch", hide_index=True)
    with tabs[2]:
        st.dataframe(signal_frame.tail(80), width="stretch", hide_index=True)
    with tabs[3]:
        st.warning("Mostrar todo el dataset puede ser pesado si descargaste muchos datos intradia.")
        st.dataframe(signal_frame, width="stretch", hide_index=True)


def _render_stress_result(result: StressTestResult) -> None:
    st.subheader("Conclusion critica")
    if result.conclusion == "Robusta":
        st.success(result.conclusion)
    elif result.conclusion == "Fragil":
        st.warning(result.conclusion)
    else:
        st.error(result.conclusion)
    for flag in result.flags:
        st.warning(flag)

    st.subheader("Base vs stress")
    st.dataframe(
        result.comparison,
        width="stretch",
        hide_index=True,
        column_config={
            "final_equity": st.column_config.NumberColumn("Final equity", format="$%.2f"),
            "total_return": st.column_config.NumberColumn("Retorno", format="%.2%%"),
            "delta_return_vs_base": st.column_config.NumberColumn("Delta retorno", format="%.2%%"),
            "cagr": st.column_config.NumberColumn("CAGR", format="%.2%%"),
            "sharpe_ratio": st.column_config.NumberColumn("Sharpe", format="%.2f"),
            "max_drawdown": st.column_config.NumberColumn("Max drawdown", format="%.2%%"),
            "delta_drawdown_vs_base": st.column_config.NumberColumn("Delta drawdown", format="%.2%%"),
            "total_commissions": st.column_config.NumberColumn("Comisiones", format="$%.2f"),
        },
    )

    curves = equity_curves_frame(result.scenarios)
    if not curves.empty:
        st.subheader("Equity curves stress")
        render_line_comparison_chart(curves, title="Base vs escenarios de stress", height=460)

    with st.expander("Notas metodologicas de escenarios", expanded=False):
        st.markdown("- **backtest:** se vuelve a ejecutar la estrategia cambiando supuestos.")
        st.markdown("- **post-hoc:** se altera la curva base para medir dependencia de eventos extremos.")
        for scenario in result.scenarios:
            st.markdown(f"- **{scenario.name}:** {scenario.note}")


def _render_next_step(data_assets, experiments) -> None:
    if not data_assets:
        st.warning("Siguiente paso: descarga o carga datos en Data Manager.")
    elif not experiments:
        st.info("Siguiente paso: revisa senales en Strategy Lab y corre un primer backtest guardado.")
    else:
        st.success("Ya hay datos y experimentos. Siguiente paso: comparar resultados y correr robustez.")


def _render_bullets(items: list[str]) -> None:
    for item in items:
        st.markdown(f"- {item}")


def _render_strategy_research_metadata(strategy_key: str) -> None:
    config = get_strategy_config(strategy_key)
    c1, c2, c3 = st.columns(3)
    c1.metric("Categoria", config.category, help="Familia conceptual de la estrategia.")
    c2.metric("Complejidad", config.complexity_level, help="Complejidad operativa/metodologica, no dificultad de codigo.")
    c3.metric("Parametros", len(config.parameters), help="Mas parametros suelen aumentar riesgo de sobreajuste.")
    with st.expander("Contexto research de la estrategia", expanded=False):
        st.markdown(f"**Regimen esperado:** {config.expected_market_regime}")
        st.markdown("**Modos de falla:**")
        _render_bullets(list(config.failure_modes))
        st.markdown("**Tests recomendados:**")
        _render_bullets(list(config.recommended_tests))
        st.dataframe(strategy_metadata_frame(strategy_key), width="stretch", hide_index=True)


def _experiment_request_defaults(details: ExperimentDetails) -> dict:
    config = details.config if isinstance(details.config, dict) else {}
    strategy_config = config.get("strategy", {})
    backtest_config = config.get("backtest", {})
    if not isinstance(strategy_config, dict):
        strategy_config = {}
    if not isinstance(backtest_config, dict):
        backtest_config = {}

    symbols = tuple(str(symbol) for symbol in (config.get("symbols") or []) if str(symbol))
    strategy_parameters = strategy_config.get("parameters", {})
    if not isinstance(strategy_parameters, dict):
        strategy_parameters = {}

    return {
        "symbol": details.symbol,
        "symbols": symbols,
        "data_dir": Path(str(config.get("data_dir", st.session_state.data_dir))),
        "interval": str(config.get("interval", st.session_state.interval)),
        "start": _optional_config_text(config.get("start")),
        "end": _optional_config_text(config.get("end")),
        "price_column": str(config.get("price_column", "adj_close")),
        "strategy_key": str(strategy_config.get("name", "")),
        "strategy_parameters": strategy_parameters,
        "initial_capital": _config_float(backtest_config, "initial_capital", 10_000.0),
        "commission_bps": _config_float(backtest_config, "commission_bps", 1.0),
        "slippage_bps": _config_float(backtest_config, "slippage_bps", 2.0),
    }


def _render_experiment_config_summary(record: ExperimentRecord, defaults: dict) -> None:
    st.caption(
        "Configuracion cargada desde experimento: "
        f"`{record.name}` | activo `{defaults['symbol']}` | "
        f"estrategia `{defaults['strategy_key']}` | timeframe `{defaults['interval']}`"
    )
    with st.expander("Ver parametros cargados", expanded=False):
        st.json(
            {
                "path": str(record.path),
                "symbols": defaults["symbols"],
                "data_dir": str(defaults["data_dir"]),
                "start": defaults["start"],
                "end": defaults["end"],
                "price_column": defaults["price_column"],
                "strategy_parameters": defaults["strategy_parameters"],
                "initial_capital": defaults["initial_capital"],
                "commission_bps": defaults["commission_bps"],
                "slippage_bps": defaults["slippage_bps"],
            }
        )


def _render_linked_journal_status_action(experiment_path: str | None, key_prefix: str) -> None:
    if not experiment_path:
        return
    try:
        details = load_experiment_details(experiment_path)
        defaults = _experiment_request_defaults(details)
        robustness = _matching_robustness(
            defaults["strategy_key"],
            defaults["strategy_parameters"],
            defaults["symbol"],
        )
        stress = _matching_stress_test(
            defaults["strategy_key"],
            defaults["strategy_parameters"],
            defaults["symbol"],
            interval=defaults["interval"],
            start=defaults["start"],
            end=defaults["end"],
        )
        suggested = recommend_journal_status(
            robustness_result=robustness,
            stress_result=stress,
            fallback="Needs Review",
        )
        notes = load_research_notes(experiment_path)
    except Exception as exc:
        _show_error(exc)
        return

    st.divider()
    st.subheader("Estado del journal")
    st.caption(
        "El estado no cambia automaticamente porque es una conclusion editorial. "
        "La app puede sugerirlo usando robustez y stress tests conectados al experimento."
    )
    c1, c2 = st.columns(2)
    c1.metric("Estado actual", notes.status)
    c2.metric("Estado sugerido", suggested)
    if notes.status == suggested:
        st.success("El journal ya refleja la evidencia disponible.")
        return
    if notes.status not in {"Draft", "Needs Review"}:
        st.info("No sobrescribo un estado curado manualmente. Cambialo desde Experiment Journal si queres.")
        return
    if st.button("Aplicar estado sugerido al journal", key=f"{key_prefix}_apply_suggested_status"):
        path = save_research_notes(
            experiment_path,
            ResearchNotes(
                status=suggested,
                hypothesis=notes.hypothesis,
                conclusion=notes.conclusion,
                next_test=notes.next_test,
                tags=notes.tags,
                favorite=notes.favorite,
            ),
        )
        st.success(f"Estado actualizado en `{path}`")
        st.rerun()


def _config_float(config: dict, key: str, default: float) -> float:
    try:
        return float(config.get(key, default))
    except (TypeError, ValueError):
        return default


def _optional_config_text(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _render_data_quality_reading(report) -> None:
    if not report.is_valid:
        st.error("No uses estos datos para backtest hasta corregir la validacion.")
        return
    if report.rows < 252:
        st.warning("Hay menos de un ano aproximado de barras diarias; cualquier metrica sera fragil.")
    elif report.gap_count or report.null_counts or report.suspicious_rows:
        st.warning("Los datos pasan validacion basica, pero tienen puntos a revisar antes de confiar.")
    else:
        st.success("Datos aptos para exploracion basica. Igual revisa fuente, splits y periodo.")


def _render_backtest_preflight(preflight: BacktestPreflight) -> None:
    st.subheader("Validacion previa")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Barras", preflight.rows)
    c2.metric("Inicio", preflight.start_date)
    c3.metric("Fin", preflight.end_date)
    c4.metric("Entradas", preflight.entries)
    if preflight.errors:
        for error in preflight.errors:
            st.error(error)
    if preflight.warnings:
        for warning in preflight.warnings:
            st.warning(warning)
    if preflight.can_run:
        st.success("Validacion previa aprobada. Esto no garantiza calidad, solo evita errores obvios.")


def _render_portfolio_preflight(preflight: PortfolioPreflight) -> None:
    st.subheader("Validacion previa")
    c1, c2, c3 = st.columns(3)
    c1.metric("Fechas comunes", preflight.aligned_rows)
    c2.metric("Inicio comun", preflight.start_date)
    c3.metric("Fin comun", preflight.end_date)
    if preflight.rows_by_symbol:
        st.dataframe(
            pd.DataFrame(
                [{"activo": symbol, "filas": rows} for symbol, rows in preflight.rows_by_symbol.items()]
            ),
            width="stretch",
            hide_index=True,
        )
    if preflight.errors:
        for error in preflight.errors:
            st.error(error)
    if preflight.warnings:
        for warning in preflight.warnings:
            st.warning(warning)
    if preflight.can_run:
        st.success("Portfolio validado: pesos, datos y fechas comunes pasan controles basicos.")


def _render_signal_reading(strategy_key: str, summary: dict[str, int | float], rows: int) -> None:
    entries = int(summary["entries"])
    exposure = float(summary["exposure_ratio"])
    if entries == 0:
        st.warning("Esta configuracion no genera entradas en el periodo. El backtest no va a decir mucho.")
    elif entries < 5 and strategy_key != "buy_and_hold":
        st.warning("Pocas entradas: la muestra de trades probablemente sera debil.")
    if exposure > 0.95 and strategy_key != "buy_and_hold":
        st.warning("La senal esta casi siempre long; tal vez se parece demasiado a buy and hold.")
    if rows < 252:
        st.warning("Poco historial para evaluar senales con confianza.")


def _render_metric_guide() -> None:
    with st.expander("Como leer estas metricas", expanded=False):
        for metric, explanation in METRIC_EXPLANATIONS.items():
            st.markdown(f"- **{metric}:** {explanation}")


def _render_result_reading_order() -> None:
    with st.expander("Orden recomendado de lectura", expanded=False):
        _render_bullets(RESULT_READING_ORDER)


def _render_critical_reading_from_result(artifacts: BacktestRunArtifacts) -> None:
    warnings = build_result_warnings(
        artifacts.result,
        parameter_count=len(artifacts.request.strategy_parameters),
        symbol_count=1,
    )
    st.subheader("Lectura critica")
    for warning in warnings or ["No hay alertas obvias, pero esto sigue siendo solo research."]:
        st.warning(warning)


def _price_overlay_columns(frame: pd.DataFrame) -> tuple[str, ...]:
    prefixes = ("sma_", "rolling_high_", "rolling_low_")
    columns = [
        column
        for column in frame.columns
        if column.startswith(prefixes) and pd.api.types.is_numeric_dtype(frame[column])
    ]
    return tuple(columns[:5])


def _asset_selector(key: str):
    assets = list_data_assets(st.session_state.data_dir, st.session_state.interval)
    if not assets:
        return None
    return st.selectbox(
        "Activo local",
        options=assets,
        format_func=lambda asset: f"{asset.symbol_hint} ({asset.interval}, {asset.rows} filas)",
        help=TOOLTIPS["ticker"],
        key=key,
    )


def _experiment_selector(key: str) -> ExperimentRecord | None:
    records = list_experiments(st.session_state.experiments_dir)
    if not records:
        return None
    return st.selectbox(
        "Experimento",
        records,
        format_func=lambda record: f"{record.name} - {record.strategy} - {', '.join(record.symbols)}",
        key=key,
    )


def _strategy_selector(key: str) -> str:
    return st.selectbox(
        "Estrategia",
        list(STRATEGIES),
        format_func=lambda strategy_key: STRATEGIES[strategy_key].label,
        key=key,
    )


def _render_strategy_parameters(strategy_key: str, key_prefix: str) -> dict[str, int | float]:
    config = get_strategy_config(strategy_key)
    parameters = default_parameters(strategy_key)
    if not config.parameters:
        st.info("Esta estrategia no tiene parametros configurables.")
        return parameters

    cols = st.columns(min(3, len(config.parameters)))
    for index, parameter in enumerate(config.parameters):
        column = cols[index % len(cols)]
        if parameter.kind == "int":
            parameters[parameter.name] = int(
                column.number_input(
                    parameter.label,
                    min_value=int(parameter.minimum),
                    max_value=int(parameter.maximum),
                    value=int(parameter.default),
                    step=int(parameter.step),
                    help=parameter.help,
                    key=f"{key_prefix}_{strategy_key}_{parameter.name}",
                )
            )
        else:
            parameters[parameter.name] = float(
                column.number_input(
                    parameter.label,
                    min_value=float(parameter.minimum),
                    max_value=float(parameter.maximum),
                    value=float(parameter.default),
                    step=float(parameter.step),
                    help=parameter.help,
                    key=f"{key_prefix}_{strategy_key}_{parameter.name}",
                )
            )
    return parameters


def _render_risk_settings(key_prefix: str) -> RiskSettings:
    with st.expander("Risk management", expanded=False):
        c1, c2, c3 = st.columns(3)
        position_fraction = c1.slider("Position sizing", 0.01, 1.0, 1.0, 0.01, help=TOOLTIPS["position_sizing"], key=f"{key_prefix}_position")
        max_total_exposure = c2.slider("Exposicion maxima", 0.01, 1.0, 1.0, 0.01, help=TOOLTIPS["exposure"], key=f"{key_prefix}_exposure")
        use_max_dd = c3.checkbox("Corte por drawdown", value=False, help=TOOLTIPS["drawdown"], key=f"{key_prefix}_use_dd")
        max_drawdown_pct = c3.slider("Max drawdown permitido", 0.01, 0.80, 0.20, 0.01, disabled=not use_max_dd, key=f"{key_prefix}_dd")

        c4, c5, c6 = st.columns(3)
        use_stop = c4.checkbox("Stop loss", value=False, help=TOOLTIPS["stop_loss"], key=f"{key_prefix}_use_stop")
        stop_loss_pct = c4.slider("Stop loss %", 0.01, 0.80, 0.10, 0.01, disabled=not use_stop, key=f"{key_prefix}_stop")
        use_take = c5.checkbox("Take profit", value=False, help=TOOLTIPS["take_profit"], key=f"{key_prefix}_use_take")
        take_profit_pct = c5.slider("Take profit %", 0.01, 2.0, 0.25, 0.01, disabled=not use_take, key=f"{key_prefix}_take")
        use_trade_limit = c6.checkbox("Limite trades/dia", value=False, key=f"{key_prefix}_use_trade_limit")
        max_trades_per_day = c6.number_input("Max trades/dia", min_value=0, value=2, step=1, disabled=not use_trade_limit, key=f"{key_prefix}_trades")

        use_vol = st.checkbox("Volatility targeting", value=False, help="Reduce exposicion si la volatilidad realizada supera el objetivo.", key=f"{key_prefix}_use_vol")
        v1, v2 = st.columns(2)
        volatility_target_pct = v1.slider("Vol objetivo anual", 0.01, 1.0, 0.15, 0.01, disabled=not use_vol, key=f"{key_prefix}_vol")
        volatility_window = v2.number_input("Ventana volatilidad", min_value=2, value=20, step=1, disabled=not use_vol, key=f"{key_prefix}_vol_window")

    return RiskSettings(
        position_fraction=float(position_fraction),
        max_total_exposure=float(max_total_exposure),
        max_drawdown_pct=float(max_drawdown_pct) if use_max_dd else None,
        max_trades_per_day=int(max_trades_per_day) if use_trade_limit else None,
        stop_loss_pct=float(stop_loss_pct) if use_stop else None,
        take_profit_pct=float(take_profit_pct) if use_take else None,
        volatility_target_pct=float(volatility_target_pct) if use_vol else None,
        volatility_window=int(volatility_window),
    )


def _combined_equity_frame(curves: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for label, curve in curves.items():
        data = curve[["date", "equity"]].copy()
        data["date"] = pd.to_datetime(data["date"])
        data = data.set_index("date").rename(columns={"equity": label})
        frames.append(data)
    return pd.concat(frames, axis=1).sort_index()


def _comparison_has_mismatch(comparison: pd.DataFrame) -> bool:
    if comparison.empty:
        return False
    period_cols = [column for column in ["start_date", "end_date", "symbol"] if column in comparison]
    return any(comparison[column].nunique() > 1 for column in period_cols)


def _matching_robustness(
    strategy_key: str | None,
    strategy_parameters: dict[str, int | float],
    symbol: str | None,
):
    result = st.session_state.get("latest_robustness")
    request = st.session_state.get("latest_robustness_request")
    if result is None or request is None:
        return None
    if strategy_key and request.strategy_key != strategy_key:
        return None
    if dict(request.strategy_parameters) != dict(strategy_parameters):
        return None
    if symbol and symbol not in request.symbols:
        return None
    return result


def _matching_stress_test(
    strategy_key: str | None,
    strategy_parameters: dict[str, int | float],
    symbol: str | None,
    *,
    interval: str | None = None,
    start: str | None = None,
    end: str | None = None,
):
    result = st.session_state.get("latest_stress_test")
    request = getattr(result, "request", None)
    if result is None or request is None:
        return None
    if strategy_key and request.strategy_key != strategy_key:
        return None
    if dict(request.strategy_parameters) != dict(strategy_parameters):
        return None
    if symbol and request.symbol != symbol:
        return None
    if interval is not None and request.interval != interval:
        return None
    if not _same_optional_date(request.start, start) or not _same_optional_date(request.end, end):
        return None
    return result


def _same_optional_date(left: object, right: object) -> bool:
    return str(left or "") == str(right or "")


def _get_guided_draft() -> ExperimentDraft:
    draft = st.session_state.get("experiment_draft")
    if not isinstance(draft, ExperimentDraft):
        draft = new_experiment_draft(st.session_state.get("interval", "1d"))
        st.session_state.experiment_draft = draft
    return draft


def _set_guided_draft(draft: ExperimentDraft) -> None:
    st.session_state.experiment_draft = draft
    st.session_state.pending_guided_step = draft.step


def _asset_index(assets, symbol: str | None) -> int:
    if symbol is None:
        return 0
    for index, asset in enumerate(assets):
        if asset.symbol_hint == symbol:
            return index
    return 0


def _strategy_index(strategy_keys: list[str], strategy_key: str) -> int:
    try:
        return strategy_keys.index(strategy_key)
    except ValueError:
        return 0


def _show_error(exc: Exception) -> None:
    st.error(str(exc))
    if st.session_state.get("debug", False):
        st.exception(exc)
