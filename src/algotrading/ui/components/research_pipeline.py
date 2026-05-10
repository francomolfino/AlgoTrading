from __future__ import annotations

import pandas as pd
import streamlit as st


def render_research_pipeline(summary) -> None:
    steps = tuple(summary.pipeline_steps)
    if not steps:
        st.info("Pipeline no disponible para este experimento.")
        return

    completed = sum(1 for step in steps if step.completed)
    st.progress(
        completed / len(steps),
        text=f"{summary.pipeline_state} - {completed}/{len(steps)} pasos completos",
    )

    columns = st.columns(len(steps))
    for column, step in zip(columns, steps):
        with column:
            st.caption(step.name)
            if step.completed:
                st.success("completo")
            else:
                st.info("pendiente")

    with st.expander("Detalle del pipeline", expanded=False):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "paso": step.name,
                        "estado": "completo" if step.completed else "pendiente",
                        "fuente": step.source,
                    }
                    for step in steps
                ]
            ),
            width="stretch",
            hide_index=True,
        )
