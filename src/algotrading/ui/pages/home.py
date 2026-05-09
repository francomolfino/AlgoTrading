from __future__ import annotations

from algotrading.ui.pages._shared import *


def render_home() -> None:
    st.title("AlgoTrading Lab")
    st.warning(EDUCATIONAL_WARNING)
    st.write(
        "Interfaz local para investigar estrategias simples, validar datos, correr backtests "
        "y revisar resultados con una lectura critica."
    )

    data_assets = list_data_assets(st.session_state.data_dir, st.session_state.interval)
    experiments = list_experiments(st.session_state.experiments_dir)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Datos locales", len(data_assets))
    col2.metric("Experimentos", len(experiments))
    col3.metric("Timeframe", st.session_state.interval)
    col4.metric("Modo", "simulacion")
    _render_next_step(data_assets, experiments)

    st.subheader("Accesos rapidos")
    cols = st.columns(6)
    _nav_button(cols[0], "Nuevo guiado", "Nuevo experimento guiado")
    _nav_button(cols[1], "Descargar datos", "Data Manager")
    _nav_button(cols[2], "Correr backtest", "Backtest Runner")
    _nav_button(cols[3], "Ver resultados", "Results Dashboard")
    _nav_button(cols[4], "Comparar", "Experiment Explorer")
    _nav_button(cols[5], "Paper simulado", "Paper Trading Simulator")

    st.subheader("Flujo recomendado")
    _render_bullets(RESEARCH_FLOW_STEPS)

    st.subheader("Ultimos experimentos")
    if experiments:
        st.dataframe(records_frame(experiments[:5]), width="stretch", hide_index=True)
    else:
        st.info("Todavia no hay experimentos guardados.")
