from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.journal_adapter import ResearchNotes, load_research_notes, save_research_notes
from algotrading.ui.adapters.research_adapter import build_research_summary, suggested_journal_status


def render_linked_journal_status_action(experiment_path: str | None, key_prefix: str) -> None:
    if not experiment_path:
        return
    try:
        summary = build_research_summary(experiment_path)
        suggested = suggested_journal_status(summary)
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


def _show_error(exc: Exception) -> None:
    st.error(str(exc))
    if st.session_state.get("debug", False):
        st.exception(exc)
