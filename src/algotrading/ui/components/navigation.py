from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.settings_adapter import load_ui_settings


PAGES = [
    "Home / Overview",
    "Nuevo experimento guiado",
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

PAGE_AREAS = {
    "Home / Overview": "Research",
    "Nuevo experimento guiado": "Research",
    "Data Manager": "Research",
    "Strategy Lab": "Research",
    "Backtest Runner": "Research",
    "Results Dashboard": "Research",
    "Experiment Explorer": "Research",
    "Robustness Lab": "Research",
    "Stress Tests": "Research",
    "Portfolio Lab": "Portfolio / Risk",
    "Risk Manager": "Portfolio / Risk",
    "Paper Trading Simulator": "Paper Runtime",
    "Reports / Export": "Research",
    "Settings": "Sistema",
}

AREA_DESCRIPTIONS = {
    "Research": "Datos, experimentos, resultados, robustez y reportes.",
    "Portfolio / Risk": "Carteras y controles de riesgo para simulacion.",
    "Paper Runtime": "Simulacion local con broker fake, sin dinero real.",
    "Sistema": "Preferencias locales de la app.",
}


def init_state() -> None:
    settings = load_ui_settings()
    query_page = _page_from_query_params()
    st.session_state.setdefault("page", query_page or PAGES[0])
    if query_page and st.session_state.get("_query_page_applied") != query_page:
        st.session_state.page = query_page
        st.session_state._query_page_applied = query_page
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
        area = page_area(current)
        st.caption(f"Area actual: {area}")
        st.caption(AREA_DESCRIPTIONS.get(area, ""))
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
        with st.expander("Mapa conceptual", expanded=False):
            for group in ("Research", "Portfolio / Risk", "Paper Runtime", "Sistema"):
                st.markdown(f"**{group}**")
                for page in [item for item in PAGES if page_area(item) == group]:
                    marker = ">" if page == current else "-"
                    st.caption(f"{marker} {page}")
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


def page_area(page: str) -> str:
    return PAGE_AREAS.get(page, "Research")


def _sync_page_from_sidebar() -> None:
    selected = st.session_state.get("nav_page", PAGES[0])
    st.session_state.page = selected if selected in PAGES else PAGES[0]


def _apply_pending_navigation() -> None:
    pending = st.session_state.pop("pending_nav_page", None)
    if pending in PAGES:
        st.session_state.page = pending
        st.session_state.nav_page = pending


def _page_from_query_params() -> str | None:
    try:
        raw_page = st.query_params.get("page")
    except Exception:
        return None
    if isinstance(raw_page, list):
        raw_page = raw_page[0] if raw_page else None
    page = str(raw_page).strip() if raw_page is not None else ""
    return page if page in PAGES else None
