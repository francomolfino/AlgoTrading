from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.strategy_adapter import signal_events_frame


def render_signal_tables(signal_frame: pd.DataFrame) -> None:
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
