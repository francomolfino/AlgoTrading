from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.backtest_adapter import BacktestPreflight
from algotrading.ui.adapters.portfolio_adapter import PortfolioPreflight


def render_backtest_preflight(preflight: BacktestPreflight) -> None:
    st.subheader("Validacion previa")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Barras", preflight.rows)
    c2.metric("Inicio", preflight.start_date)
    c3.metric("Fin", preflight.end_date)
    c4.metric("Entradas", preflight.entries)
    if preflight.errors:
        for error in preflight.errors:
            st.error(error)
    if preflight.warnings:
        for warning in preflight.warnings:
            st.warning(warning)
    if preflight.can_run:
        st.success("Validacion previa aprobada. Esto no garantiza calidad, solo evita errores obvios.")


def render_portfolio_preflight(preflight: PortfolioPreflight) -> None:
    st.subheader("Validacion previa")
    c1, c2, c3 = st.columns(3)
    c1.metric("Fechas comunes", preflight.aligned_rows)
    c2.metric("Inicio comun", preflight.start_date)
    c3.metric("Fin comun", preflight.end_date)
    if preflight.rows_by_symbol:
        st.dataframe(
            pd.DataFrame(
                [{"activo": symbol, "filas": rows} for symbol, rows in preflight.rows_by_symbol.items()]
            ),
            width="stretch",
            hide_index=True,
        )
    if preflight.errors:
        for error in preflight.errors:
            st.error(error)
    if preflight.warnings:
        for warning in preflight.warnings:
            st.warning(warning)
    if preflight.can_run:
        st.success("Portfolio validado: pesos, datos y fechas comunes pasan controles basicos.")
