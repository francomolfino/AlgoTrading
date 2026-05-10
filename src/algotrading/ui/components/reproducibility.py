from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


def render_reproducibility_sheet(metadata: dict[str, Any], config: dict[str, Any] | None = None) -> None:
    st.subheader("Ficha reproducible")
    if not metadata:
        st.warning("No hay metadata reproducible disponible para este experimento.")
        return

    if metadata.get("metadata_available") is False:
        st.warning(
            "Este experimento parece anterior al archivo experiment_metadata.json. "
            "Muestro una reconstruccion parcial desde config/summary."
        )

    project = _mapping(metadata.get("project"))
    data = _mapping(metadata.get("data"))
    strategy = _mapping(metadata.get("strategy"))
    costs = _mapping(metadata.get("costs"))
    risk = _mapping(metadata.get("risk"))
    outputs = _mapping(metadata.get("outputs"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Run ID", _short_text(metadata.get("run_id"), 18))
    c2.metric("Creado", _short_text(metadata.get("created_at_utc"), 19))
    c3.metric("Commit", _short_text(project.get("git_commit"), 10))
    c4.metric("Git dirty", _yes_no(project.get("git_dirty")))

    tabs = st.tabs(["Datos", "Estrategia", "Costos y riesgo", "Proyecto", "Outputs"])
    with tabs[0]:
        st.dataframe(_key_value_frame(data), width="stretch", hide_index=True)
    with tabs[1]:
        strategy_rows = {
            "name": strategy.get("name", "no disponible"),
            "parameters": strategy.get("parameters", {}),
        }
        st.dataframe(_key_value_frame(strategy_rows), width="stretch", hide_index=True)
    with tabs[2]:
        c_left, c_right = st.columns(2)
        c_left.dataframe(_key_value_frame(costs), width="stretch", hide_index=True)
        c_right.dataframe(_key_value_frame(risk), width="stretch", hide_index=True)
    with tabs[3]:
        st.dataframe(_key_value_frame(project), width="stretch", hide_index=True)
    with tabs[4]:
        if outputs:
            st.dataframe(_key_value_frame(outputs), width="stretch", hide_index=True)
        else:
            st.info("No hay archivos de salida registrados.")

    with st.expander("JSON crudo de reproducibilidad", expanded=False):
        if config:
            st.caption("config.json")
            st.json(config)
        st.caption("experiment_metadata.json")
        st.json(metadata)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _key_value_frame(mapping: dict[str, Any]) -> pd.DataFrame:
    if not mapping:
        return pd.DataFrame([{"campo": "estado", "valor": "no disponible"}])
    return pd.DataFrame(
        [
            {"campo": str(key), "valor": _display_value(value)}
            for key, value in mapping.items()
        ]
    )


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return "no disponible"
    if isinstance(value, bool):
        return "si" if value else "no"
    if isinstance(value, dict):
        if not value:
            return "{}"
        return ", ".join(f"{key}={_display_value(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(_display_value(item) for item in value) if value else "[]"
    return str(value)


def _short_text(value: Any, max_len: int) -> str:
    text = _display_value(value)
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _yes_no(value: Any) -> str:
    if isinstance(value, bool):
        return "si" if value else "no"
    if value in {0, "0", "false", "False", "no", "No"}:
        return "no"
    if value in {1, "1", "true", "True", "si", "Si", "yes", "Yes"}:
        return "si"
    return _display_value(value)
