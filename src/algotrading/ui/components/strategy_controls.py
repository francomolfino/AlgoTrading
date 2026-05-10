from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.strategy_adapter import (
    default_parameters,
    get_strategy_config,
    strategy_metadata_frame,
)


def render_strategy_research_metadata(strategy_key: str) -> None:
    config = get_strategy_config(strategy_key)
    c1, c2, c3 = st.columns(3)
    c1.metric("Categoria", config.category, help="Familia conceptual de la estrategia.")
    c2.metric("Complejidad", config.complexity_level, help="Complejidad operativa/metodologica, no dificultad de codigo.")
    c3.metric("Parametros", len(config.parameters), help="Mas parametros suelen aumentar riesgo de sobreajuste.")
    with st.expander("Contexto research de la estrategia", expanded=False):
        st.markdown(f"**Regimen esperado:** {config.expected_market_regime}")
        st.markdown("**Modos de falla:**")
        _render_bullets(list(config.failure_modes))
        st.markdown("**Tests recomendados:**")
        _render_bullets(list(config.recommended_tests))
        st.dataframe(strategy_metadata_frame(strategy_key), width="stretch", hide_index=True)


def render_strategy_parameters(strategy_key: str, key_prefix: str) -> dict[str, int | float]:
    config = get_strategy_config(strategy_key)
    parameters = default_parameters(strategy_key)
    if not config.parameters:
        st.info("Esta estrategia no tiene parametros configurables.")
        return parameters

    cols = st.columns(min(3, len(config.parameters)))
    for index, parameter in enumerate(config.parameters):
        column = cols[index % len(cols)]
        if parameter.kind == "int":
            parameters[parameter.name] = int(
                column.number_input(
                    parameter.label,
                    min_value=int(parameter.minimum),
                    max_value=int(parameter.maximum),
                    value=int(parameter.default),
                    step=int(parameter.step),
                    help=parameter.help,
                    key=f"{key_prefix}_{strategy_key}_{parameter.name}",
                )
            )
        else:
            parameters[parameter.name] = float(
                column.number_input(
                    parameter.label,
                    min_value=float(parameter.minimum),
                    max_value=float(parameter.maximum),
                    value=float(parameter.default),
                    step=float(parameter.step),
                    help=parameter.help,
                    key=f"{key_prefix}_{strategy_key}_{parameter.name}",
                )
            )
    return parameters


def _render_bullets(items: list[str]) -> None:
    for item in items:
        st.markdown(f"- {item}")
