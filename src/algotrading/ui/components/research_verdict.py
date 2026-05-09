from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.verdict_adapter import ResearchVerdict


def render_research_verdict(verdict: ResearchVerdict) -> None:
    st.subheader("Research Verdict")
    with st.container(border=True):
        c1, c2, c3 = st.columns([1.1, 1.2, 0.8])
        c1.metric("Confiabilidad", verdict.reliability, help="Calidad preliminar de la evidencia, no recomendacion de inversion.")
        c2.metric("Benchmark", verdict.benchmark_status, help="Compara contra buy and hold/benchmark cuando esta disponible.")
        c3.metric("Flags", len(verdict.flags), help="Cantidad de alertas metodologicas detectadas.")

        st.write(verdict.summary)
        if verdict.flags:
            for flag in verdict.flags:
                st.warning(flag)
        else:
            st.success("Sin flags automaticos fuertes. Igual hace robustez antes de confiar.")

        st.info(f"Proxima accion recomendada: {verdict.next_action}")

        with st.expander("Ver diagnostico usado"):
            st.dataframe(
                pd.DataFrame(
                    [{"criterio": name, "valor": value} for name, value in verdict.diagnostics]
                ),
                width="stretch",
                hide_index=True,
            )
