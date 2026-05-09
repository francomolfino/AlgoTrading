from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.evidence_adapter import EvidenceScore, components_frame


def render_evidence_score(score: EvidenceScore) -> None:
    st.subheader("Evidence Score")
    with st.container(border=True):
        c1, c2 = st.columns([0.9, 2.1])
        c1.metric(
            "Score",
            f"{score.score:.0f}/100",
            help="Calidad de evidencia, no rentabilidad esperada ni recomendacion de inversion.",
        )
        c1.progress(int(score.score))
        c2.markdown(f"**{score.label}**")
        c2.write(score.explanation)
        c2.caption("Este score penaliza falta de robustez, poca muestra, ausencia de costos y exceso de parametros.")

        with st.expander("Ver desglose del score"):
            st.dataframe(components_frame(score), width="stretch", hide_index=True)
