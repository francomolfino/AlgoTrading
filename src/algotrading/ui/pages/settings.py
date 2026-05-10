from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.settings_adapter import UISettings, save_ui_settings
from algotrading.ui.components.common import show_error as _show_error


def render_settings() -> None:
    st.title("Settings")
    current = UISettings(
        data_dir=st.session_state.data_dir,
        experiments_dir=st.session_state.experiments_dir,
        interval=st.session_state.interval,
        debug=st.session_state.debug,
    )
    with st.form("settings_form"):
        data_dir = st.text_input("Carpeta de datos", value=current.data_dir)
        experiments_dir = st.text_input("Carpeta de experimentos", value=current.experiments_dir)
        default_tickers = st.text_input("Tickers default", value=current.default_tickers)
        initial_capital = st.number_input("Capital default", min_value=100.0, value=current.initial_capital, step=500.0)
        commission_bps = st.number_input("Comision default bps", min_value=0.0, value=current.commission_bps, step=0.5)
        slippage_bps = st.number_input("Slippage default bps", min_value=0.0, value=current.slippage_bps, step=0.5)
        interval = st.selectbox("Timeframe default", ["1d", "1wk", "1mo"], index=["1d", "1wk", "1mo"].index(current.interval))
        debug = st.checkbox("Modo debug", value=current.debug)
        submitted = st.form_submit_button("Guardar settings")
    if submitted:
        settings = UISettings(
            data_dir=data_dir,
            experiments_dir=experiments_dir,
            default_tickers=default_tickers,
            initial_capital=float(initial_capital),
            commission_bps=float(commission_bps),
            slippage_bps=float(slippage_bps),
            interval=interval,
            debug=debug,
        )
        try:
            path = save_ui_settings(settings)
            st.session_state.data_dir = settings.data_dir
            st.session_state.experiments_dir = settings.experiments_dir
            st.session_state.interval = settings.interval
            st.session_state.debug = settings.debug
            st.success(f"Settings guardados en {path}")
        except Exception as exc:
            _show_error(exc)
