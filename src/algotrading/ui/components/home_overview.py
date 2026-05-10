from __future__ import annotations

import streamlit as st


def render_next_step(data_assets, experiments) -> None:
    if not data_assets:
        st.warning("Siguiente paso: descarga o carga datos en Data Manager.")
    elif not experiments:
        st.info("Siguiente paso: revisa senales en Strategy Lab y corre un primer backtest guardado.")
    else:
        st.success("Ya hay datos y experimentos. Siguiente paso: comparar resultados y correr robustez.")
