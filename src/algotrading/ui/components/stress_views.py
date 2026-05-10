from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.stress_adapter import StressTestResult, equity_curves_frame
from algotrading.ui.charts import render_line_comparison_chart


def render_stress_result(result: StressTestResult) -> None:
    st.subheader("Conclusion critica")
    if result.conclusion == "Robusta":
        st.success(result.conclusion)
    elif result.conclusion == "Fragil":
        st.warning(result.conclusion)
    else:
        st.error(result.conclusion)
    for flag in result.flags:
        st.warning(flag)

    st.subheader("Base vs stress")
    st.dataframe(
        result.comparison,
        width="stretch",
        hide_index=True,
        column_config={
            "final_equity": st.column_config.NumberColumn("Final equity", format="$%.2f"),
            "total_return": st.column_config.NumberColumn("Retorno", format="%.2%%"),
            "delta_return_vs_base": st.column_config.NumberColumn("Delta retorno", format="%.2%%"),
            "cagr": st.column_config.NumberColumn("CAGR", format="%.2%%"),
            "sharpe_ratio": st.column_config.NumberColumn("Sharpe", format="%.2f"),
            "max_drawdown": st.column_config.NumberColumn("Max drawdown", format="%.2%%"),
            "delta_drawdown_vs_base": st.column_config.NumberColumn("Delta drawdown", format="%.2%%"),
            "total_commissions": st.column_config.NumberColumn("Comisiones", format="$%.2f"),
        },
    )

    curves = equity_curves_frame(result.scenarios)
    if not curves.empty:
        st.subheader("Equity curves stress")
        render_line_comparison_chart(curves, title="Base vs escenarios de stress", height=460)

    with st.expander("Notas metodologicas de escenarios", expanded=False):
        st.markdown("- **backtest:** se vuelve a ejecutar la estrategia cambiando supuestos.")
        st.markdown("- **post-hoc:** se altera la curva base para medir dependencia de eventos extremos.")
        for scenario in result.scenarios:
            st.markdown(f"- **{scenario.name}:** {scenario.note}")
