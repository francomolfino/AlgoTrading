from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.experiment_adapter import (
    ExperimentRecord,
    compare_experiment_records,
    delete_experiment_dir,
    diff_experiment_configs,
    filter_records,
    list_experiments,
    load_equity_curves,
    sort_records,
)
from algotrading.ui.adapters.journal_adapter import (
    RESEARCH_NOTE_STATUSES,
    ResearchNotes,
    load_research_notes,
    parse_tags,
    save_research_notes,
    tags_to_text,
)
from algotrading.ui.adapters.research_adapter import (
    compare_experiment_fairness,
    research_records_cache_signature,
    research_records_frame_from_paths,
)
from algotrading.ui.charts import render_line_comparison_chart
from algotrading.ui.components.common import show_error as _show_error
from algotrading.ui.components.equity_comparison import (
    combined_equity_frame as _combined_equity_frame,
    comparison_has_mismatch as _comparison_has_mismatch,
)
from algotrading.ui.components.navigation import go_to_page as _go_to_page


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
    frame = _cached_research_records_frame(research_records_cache_signature(filtered))
    display_frame = _explorer_display_frame(frame)
    st.caption("Lectura rapida: usa los checks para ver si el experimento ya tiene robustez, stress y journal conectados.")
    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "evidence_score": st.column_config.NumberColumn("Evidence", format="%.1f"),
            "data_quality_score": st.column_config.NumberColumn("Data Quality", format="%.1f"),
            "total_return": st.column_config.NumberColumn("Retorno", format="%.2%%"),
            "sharpe_ratio": st.column_config.NumberColumn("Sharpe", format="%.2f"),
            "max_drawdown": st.column_config.NumberColumn("Max DD", format="%.2%%"),
            "checks": st.column_config.TextColumn("Checks research"),
            "favorite_badge": st.column_config.TextColumn("Fav"),
        },
    )
    if not filtered:
        st.info("No hay experimentos para esos filtros.")
        return

    quick_record = st.selectbox(
        "Abrir rapido",
        filtered,
        format_func=lambda record: f"{record.name} - {record.strategy} - {', '.join(record.symbols)}",
        key="experiment_quick_open",
    )
    _render_quick_research_badges(quick_record, frame)
    a1, a2, a3, a4, a5 = st.columns(5)
    if a1.button("Resultados", width="stretch"):
        st.session_state.results_experiment = quick_record
        _go_to_page("Results Dashboard")
    if a2.button("Robustez", width="stretch"):
        st.session_state.robustness_source_experiment = quick_record
        _go_to_page("Robustness Lab")
    if a3.button("Stress", width="stretch"):
        st.session_state.stress_source_mode = "Desde experimento guardado"
        st.session_state.stress_source_experiment = quick_record
        _go_to_page("Stress Tests")
    if a4.button("Journal/notas", width="stretch"):
        st.session_state.journal_experiment_select = quick_record
        st.session_state.expand_research_journal = True
        st.rerun()
    if a5.button("Reportes", width="stretch"):
        st.session_state.reports_experiment = quick_record
        _go_to_page("Reports / Export")

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
        fairness_issues = compare_experiment_fairness(selected_records)
        if fairness_issues:
            st.subheader("Advertencias de comparacion")
            for issue in fairness_issues:
                st.warning(f"{issue.category}: {issue.message}")
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
    with st.expander("Journal de research", expanded=bool(st.session_state.pop("expand_research_journal", False))):
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


@st.cache_data(show_spinner=False)
def _cached_research_records_frame(signature: tuple[tuple[str, float], ...]):
    return research_records_frame_from_paths(tuple(path for path, _fingerprint in signature))


def _explorer_display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    if display.empty:
        return display
    display["checks"] = display.apply(_research_checks_label, axis=1)
    if "favorite" in display:
        display["favorite_badge"] = display["favorite"].map(lambda value: "favorito" if bool(value) else "")
    else:
        display["favorite_badge"] = ""
    preferred = [
        "name",
        "pipeline_state",
        "journal_status",
        "research_preset",
        "evidence_score",
        "data_quality_score",
        "data_quality_severity",
        "checks",
        "favorite_badge",
        "tags",
        "strategy",
        "symbols",
        "total_return",
        "sharpe_ratio",
        "max_drawdown",
        "created_at",
        "path",
    ]
    return display[[column for column in preferred if column in display]]


def _render_quick_research_badges(record: ExperimentRecord, frame: pd.DataFrame) -> None:
    row = _frame_row_for_record(record, frame)
    if row is None:
        st.info("No pude cargar el resumen de research para este experimento.")
        return
    st.subheader("Resumen rapido")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Pipeline", str(row.get("pipeline_state", "n/a")))
    score = row.get("evidence_score")
    c2.metric("Evidence", "n/a" if pd.isna(score) else f"{float(score):.0f}/100")
    _status_badge(c3, "Robustez", bool(row.get("has_robustness")))
    _status_badge(c4, "Stress", bool(row.get("has_stress")))
    _status_badge(c5, "Journal", bool(row.get("has_journal")))
    tags = str(row.get("tags", "") or "").strip()
    if tags:
        st.caption(f"Tags: {tags}")
    preset = str(row.get("research_preset", "") or "").strip()
    dq_score = row.get("data_quality_score")
    dq_text = "n/a" if pd.isna(dq_score) else f"{float(dq_score):.0f}/100"
    st.caption(f"Preset: {preset or 'n/a'} | Data Quality: {dq_text}")


def _frame_row_for_record(record: ExperimentRecord, frame: pd.DataFrame):
    if frame.empty or "path" not in frame:
        return None
    matches = frame[frame["path"].astype(str) == str(record.path)]
    if matches.empty:
        return None
    return matches.iloc[0]


def _status_badge(column, label: str, ok: bool) -> None:
    with column:
        st.caption(label)
        if ok:
            st.success("conectado")
        else:
            st.warning("pendiente")


def _research_checks_label(row: pd.Series) -> str:
    robustness = "R:ok" if bool(row.get("has_robustness")) else "R:pend"
    stress = "S:ok" if bool(row.get("has_stress")) else "S:pend"
    journal = "J:ok" if bool(row.get("has_journal")) else "J:pend"
    return f"{robustness} | {stress} | {journal}"
    return display
