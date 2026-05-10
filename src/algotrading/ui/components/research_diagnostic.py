from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.journal_adapter import (
    RESEARCH_NOTE_STATUSES,
    ResearchNotes,
    parse_tags,
    save_research_notes,
    tags_to_text,
)
from algotrading.ui.adapters.research_adapter import ResearchSummary, suggested_journal_status
from algotrading.ui.components.evidence_score import render_evidence_score
from algotrading.ui.components.research_pipeline import render_research_pipeline
from algotrading.ui.components.research_presets import render_preset_summary
from algotrading.ui.components.research_verdict import render_research_verdict


def render_research_diagnostic(summary: ResearchSummary) -> None:
    st.subheader("Diagnostico de Research")
    st.info(f"Preset: **{summary.research_preset.label}**. {summary.research_preset.description}")
    render_research_verdict(summary.verdict)
    render_evidence_score(summary.evidence_score)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Pipeline", summary.pipeline_state)
    c2.metric("Estado journal", summary.journal_state or "Sin estado")
    c3.metric("Robustez", "corrida" if summary.has_robustness else "no corrida")
    c4.metric("Stress", summary.stress_summary["conclusion"] if summary.stress_summary else "no corrido")
    c5.metric("Favorito", "si" if summary.journal_favorite else "no")
    c6.metric(
        "Data Quality",
        f"{summary.data_quality.score:.0f}/100" if summary.data_quality else "n/a",
        summary.data_quality.severity if summary.data_quality else "no disponible",
    )

    render_preset_summary(summary.research_preset, expanded=False)
    render_research_pipeline(summary)

    if summary.journal_tags:
        st.caption("Tags: " + ", ".join(summary.journal_tags))
    if summary.robustness_summary:
        st.info(f"Robustez asociada: {summary.robustness_summary['comment']}")
    if summary.stress_summary:
        worst_delta = summary.stress_summary.get("worst_delta_return_vs_base")
        suffix = f" Peor delta retorno: {worst_delta:.2%}." if worst_delta is not None else ""
        st.info(f"Stress asociado: {summary.stress_summary['conclusion']}.{suffix}")
    if summary.critical_flags:
        with st.expander("Flags criticos", expanded=True):
            for flag in summary.critical_flags:
                st.warning(flag)
    st.success(f"Proxima accion sugerida: {summary.recommended_next_action}")
    _render_research_journal_editor(summary)


def _render_research_journal_editor(summary: ResearchSummary) -> None:
    with st.expander("Journal del experimento", expanded=False):
        st.caption("Las sugerencias no sobrescriben tus notas. Guardar aca solo actualiza research_notes.json.")
        suggested_status = suggested_journal_status(summary)
        st.info(f"Estado sugerido por evidencia disponible: **{suggested_status}**")
        with st.form(f"results_journal_form_{summary.experiment_path.name}"):
            c1, c2 = st.columns([2, 1])
            current_status = summary.journal_state or RESEARCH_NOTE_STATUSES[0]
            if current_status not in RESEARCH_NOTE_STATUSES:
                current_status = RESEARCH_NOTE_STATUSES[0]
            status = c1.selectbox(
                "Estado",
                RESEARCH_NOTE_STATUSES,
                index=RESEARCH_NOTE_STATUSES.index(current_status),
                help="Estado editorial del experimento. No cambia las metricas.",
            )
            favorite = c2.checkbox("Favorito", value=summary.journal_favorite)
            tags_text = st.text_input("Tags", value=tags_to_text(summary.journal_tags))
            hypothesis = st.text_area("Hipotesis", value=summary.journal_hypothesis, height=80)
            conclusion = st.text_area("Conclusion", value=summary.journal_conclusion, height=90)
            next_test = st.text_area(
                "Proximo test",
                value=summary.journal_next_test or summary.recommended_next_action,
                height=80,
            )
            submitted = st.form_submit_button("Guardar journal")
        if submitted:
            path = save_research_notes(
                summary.experiment_path,
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
