from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.backtest_adapter import preflight_backtest_request, run_backtest_request
from algotrading.ui.adapters.data_adapter import (
    list_data_assets,
    load_data_file,
    load_symbol_data,
    quality_report_frame,
    validate_data_quality,
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
from algotrading.ui.adapters.preset_adapter import get_research_preset, normalize_preset_key, preset_keys, preset_label
from algotrading.ui.adapters.research_adapter import build_research_summary, save_robustness_for_experiment
from algotrading.ui.adapters.robustness_adapter import robustness_comment, run_robustness_request
from algotrading.ui.adapters.strategy_adapter import (
    STRATEGIES,
    generate_strategy_signals,
    get_strategy_config,
    signal_summary,
    validate_strategy_parameters,
)
from algotrading.ui.charts import render_price_volume_chart
from algotrading.ui.components.common import show_error as _show_error
from algotrading.ui.components.data_quality import render_data_quality_reading as _render_data_quality_reading
from algotrading.ui.components.guided_state import get_guided_draft as _get_guided_draft, set_guided_draft as _set_guided_draft
from algotrading.ui.components.navigation import go_to_page as _go_to_page
from algotrading.ui.components.preflight import render_backtest_preflight as _render_backtest_preflight
from algotrading.ui.components.research_presets import render_preset_summary as _render_preset_summary
from algotrading.ui.components.research_results import (
    matching_robustness as _matching_robustness,
    matching_stress_test as _matching_stress_test,
    render_backtest_result as _render_backtest_result,
)
from algotrading.ui.components.risk_controls import render_risk_settings as _render_risk_settings
from algotrading.ui.components.selectors import asset_index as _asset_index, strategy_index as _strategy_index
from algotrading.ui.components.signal_insights import render_signal_reading as _render_signal_reading
from algotrading.ui.components.strategy_controls import (
    render_strategy_parameters as _render_strategy_parameters,
    render_strategy_research_metadata as _render_strategy_research_metadata,
)
from algotrading.ui.texts import TOOLTIPS


def render_guided_workflow() -> None:
    st.title("Nuevo experimento guiado")
    st.warning("Modo research educativo. No opera dinero real ni valida rentabilidad futura.")
    st.write("Este flujo te lleva de datos a conclusion sin saltarte controles basicos.")

    draft = _get_guided_draft()
    preset_options = preset_keys()
    selected_preset = st.selectbox(
        "Preset de research",
        preset_options,
        index=preset_options.index(normalize_preset_key(draft.research_preset)),
        format_func=preset_label,
        help="Define que checks y metricas son prioritarios para este experimento. No es una recomendacion de inversion.",
        key="guided_research_preset_select",
    )
    if selected_preset != normalize_preset_key(draft.research_preset):
        _set_guided_draft(update_experiment_draft(draft, research_preset=selected_preset))
        st.rerun()
    _render_preset_summary(get_research_preset(selected_preset))

    pending_step = st.session_state.pop("pending_guided_step", None)
    if pending_step is not None:
        draft = update_experiment_draft(draft, step=pending_step)
        st.session_state.experiment_draft = draft
        st.session_state.guided_step_widget_version = st.session_state.get("guided_step_widget_version", 0) + 1
    c1, c2 = st.columns([3, 1])
    step_widget_version = st.session_state.get("guided_step_widget_version", 0)
    selected_step = c1.radio(
        "Paso",
        list(range(1, len(GUIDED_WORKFLOW_STEPS) + 1)),
        index=draft.step - 1,
        format_func=guided_step_label,
        horizontal=True,
        key=f"guided_step_selector_{step_widget_version}",
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
    chart_scope = st.selectbox(
        "Rango visible del grafico",
        ["Todo el historial", "Ultimas 500 barras", "Ultimas 1000 barras"],
        index=1,
        help="Solo cambia la vista del grafico. La validacion y el backtest usan el dataset completo o el periodo que configures despues.",
        key="guided_data_chart_scope",
    )
    chart_frame = _guided_chart_frame(frame, chart_scope)
    render_price_volume_chart(
        chart_frame,
        title=f"{asset.symbol_hint} - {chart_scope.lower()}",
        price_column=price_column,
        height=430,
        show_legend=False,
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


def _guided_chart_frame(frame: pd.DataFrame, scope: str) -> pd.DataFrame:
    if scope == "Ultimas 500 barras":
        return frame.tail(500)
    if scope == "Ultimas 1000 barras":
        return frame.tail(1000)
    return frame


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
    if draft.backtest_artifacts.experiment_dir is not None:
        summary = build_research_summary(draft.backtest_artifacts.experiment_dir)
        st.info(f"Pipeline actual: **{summary.pipeline_state}**. Proxima accion: {summary.recommended_next_action}")
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
            if draft.backtest_artifacts.experiment_dir is not None:
                save_robustness_for_experiment(draft.backtest_artifacts.experiment_dir, request, result)
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
