from __future__ import annotations

import streamlit as st


def render_page_header(
    title: str,
    subtitle: str,
    *,
    area: str = "Research",
    warning: str | None = None,
) -> None:
    """Header consistente para pantallas de research y simulacion."""
    st.caption(f"Area: {area}")
    st.title(title)
    if subtitle:
        st.write(subtitle)
    if warning:
        st.warning(warning)


def render_empty_state(
    title: str,
    *,
    missing: str,
    why_it_matters: str,
    next_step: str,
) -> None:
    """Empty state accionable: que falta, por que importa y que hacer."""
    st.info(f"**{title}**")
    st.markdown(f"**Que falta:** {missing}")
    st.markdown(f"**Por que importa:** {why_it_matters}")
    st.markdown(f"**Que hacer ahora:** {next_step}")


def render_status_badge(label: str, value: str, *, severity: str = "info") -> None:
    message = f"**{label}:** {value}"
    if severity == "ok":
        st.success(message)
    elif severity == "warning":
        st.warning(message)
    elif severity == "critical":
        st.error(message)
    else:
        st.info(message)


def render_warning_panel(title: str, warnings: list[str] | tuple[str, ...], *, severity: str = "warning") -> None:
    if not warnings:
        return
    renderer = st.warning if severity == "warning" else st.error if severity == "critical" else st.info
    renderer("**" + title + "**\n\n" + "\n".join(f"- {item}" for item in warnings))


def render_metric_card(container, label: str, value: object, delta: object | None = None) -> None:
    container.metric(label, value, delta=delta)


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
