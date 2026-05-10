from __future__ import annotations

from algotrading.ui.pages._shared import *


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
    st.dataframe(
        display_frame,
        width="stretch",
        hide_index=True,
        column_config={
            "evidence_score": st.column_config.NumberColumn("Evidence", format="%.1f"),
            "total_return": st.column_config.NumberColumn("Retorno", format="%.2%%"),
            "sharpe_ratio": st.column_config.NumberColumn("Sharpe", format="%.2f"),
            "max_drawdown": st.column_config.NumberColumn("Max DD", format="%.2%%"),
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
    a1, a2, a3, a4 = st.columns(4)
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
    for column in ["has_robustness", "has_stress", "has_journal", "favorite"]:
        if column in display:
            display[column] = display[column].map(lambda value: "si" if bool(value) else "no")
    return display
