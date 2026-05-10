from __future__ import annotations

import streamlit as st


def render_placeholder(page: str) -> None:
    st.title(page)
    st.info(
        "Pantalla pendiente para la segunda iteracion. La base ya quedo preparada "
        "con adapters y navegacion segura."
    )
    if page == "Paper Trading Simulator":
        st.warning("Modo simulacion. No se envian ordenes reales.")


def render_bullets(items: list[str]) -> None:
    for item in items:
        st.markdown(f"- {item}")


def show_error(exc: Exception) -> None:
    st.error(str(exc))
    if st.session_state.get("debug", False):
        st.exception(exc)
