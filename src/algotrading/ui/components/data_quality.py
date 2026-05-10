from __future__ import annotations

import streamlit as st


def render_data_quality_reading(report) -> None:
    if not report.is_valid:
        st.error("No uses estos datos para backtest hasta corregir la validacion.")
        return
    if report.rows < 252:
        st.warning("Hay menos de un ano aproximado de barras diarias; cualquier metrica sera fragil.")
    elif report.gap_count or report.null_counts or report.suspicious_rows:
        st.warning("Los datos pasan validacion basica, pero tienen puntos a revisar antes de confiar.")
    else:
        st.success("Datos aptos para exploracion basica. Igual revisa fuente, splits y periodo.")
