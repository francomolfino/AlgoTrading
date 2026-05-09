from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.settings_adapter import load_ui_settings


PAGES = [
    "Home / Overview",
    "Data Manager",
    "Strategy Lab",
    "Backtest Runner",
    "Results Dashboard",
    "Experiment Explorer",
    "Robustness Lab",
    "Stress Tests",
    "Portfolio Lab",
    "Risk Manager",
    "Paper Trading Simulator",
    "Reports / Export",
    "Settings",
]


def init_state() -> None:
    settings = load_ui_settings()
    st.session_state.setdefault("page", PAGES[0])
    if st.session_state.page not in PAGES:
        st.session_state.page = PAGES[0]
    st.session_state.setdefault("nav_page", st.session_state.page)
    _apply_pending_navigation()
    st.session_state.setdefault("data_dir", settings.data_dir)
    st.session_state.setdefault("experiments_dir", settings.experiments_dir)
    st.session_state.setdefault("interval", settings.interval)
    st.session_state.setdefault("debug", settings.debug)


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Navegacion")
        current = st.session_state.page if st.session_state.page in PAGES else PAGES[0]
        if st.session_state.get("nav_page") not in PAGES or st.session_state.nav_page != current:
            st.session_state.nav_page = current
        st.radio(
            "Seccion",
            PAGES,
            key="nav_page",
            label_visibility="collapsed",
            on_change=_sync_page_from_sidebar,
        )
        st.divider()
        st.header("Configuracion")
        st.session_state.data_dir = st.text_input("Carpeta datos", value=st.session_state.data_dir)
        st.session_state.experiments_dir = st.text_input("Carpeta experimentos", value=st.session_state.experiments_dir)
        interval_options = ["1d", "1wk", "1mo"]
        interval = st.session_state.interval if st.session_state.interval in interval_options else "1d"
        st.session_state.interval = st.selectbox(
            "Timeframe default",
            interval_options,
            index=interval_options.index(interval),
        )
        st.session_state.debug = st.checkbox("Modo debug", value=st.session_state.debug)
        st.caption("No hay brokers reales expuestos en esta UI.")


def nav_button(column, label: str, page: str) -> None:
    if column.button(label, width="stretch"):
        go_to_page(page)


def go_to_page(page: str) -> None:
    if page not in PAGES:
        raise ValueError(f"Pagina no soportada: {page}")
    st.session_state.page = page
    st.session_state.pending_nav_page = page
    st.rerun()


def _sync_page_from_sidebar() -> None:
    selected = st.session_state.get("nav_page", PAGES[0])
    st.session_state.page = selected if selected in PAGES else PAGES[0]


def _apply_pending_navigation() -> None:
    pending = st.session_state.pop("pending_nav_page", None)
    if pending in PAGES:
        st.session_state.page = pending
        st.session_state.nav_page = pending
