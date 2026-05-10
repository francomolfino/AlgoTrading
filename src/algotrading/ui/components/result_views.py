from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.backtest_adapter import trade_details_frame
from algotrading.ui.charts import render_equity_drawdown_chart


def render_equity_and_drawdown(equity: pd.DataFrame) -> None:
    if equity.empty:
        st.warning("No hay equity curve para mostrar.")
        return
    data = equity.copy()
    data["date"] = pd.to_datetime(data["date"])
    render_equity_drawdown_chart(data, title="Equity y drawdown", height=560)


def render_trade_details(trades: pd.DataFrame) -> None:
    if trades.empty:
        st.info("No hay trades cerrados para mostrar.")
        return
    try:
        display = trade_details_frame(trades)
    except Exception as exc:
        st.warning("No pude construir la vista amigable de trades. Muestro tabla cruda.")
        st.error(str(exc))
        if st.session_state.get("debug", False):
            st.exception(exc)
        st.dataframe(trades, width="stretch", hide_index=True)
        return

    wins = int((display["pnl"] > 0).sum())
    losses = int((display["pnl"] <= 0).sum())
    avg_roi = float(display["roi_pct"].mean()) if len(display) else 0.0
    total_pnl = float(display["pnl"].sum()) if len(display) else 0.0
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Trades cerrados", len(display))
    c2.metric("Ganadores / perdedores", f"{wins} / {losses}")
    c3.metric("ROI promedio", f"{avg_roi:.2f}%")
    c4.metric("PnL total", f"{total_pnl:,.2f}")

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        column_config={
            "trade": st.column_config.NumberColumn("Trade", format="%d"),
            "entrada": st.column_config.TextColumn("Entrada"),
            "salida": st.column_config.TextColumn("Salida"),
            "precio_entrada": st.column_config.NumberColumn("Precio entrada", format="%.4f"),
            "precio_salida": st.column_config.NumberColumn("Precio salida", format="%.4f"),
            "cantidad": st.column_config.NumberColumn("Cantidad comprada", format="%.6f"),
            "capital_entrada": st.column_config.NumberColumn("Capital entrada", format="%.2f"),
            "valor_salida": st.column_config.NumberColumn("Valor salida", format="%.2f"),
            "pnl": st.column_config.NumberColumn("PnL", format="%.2f"),
            "roi_pct": st.column_config.NumberColumn("ROI", format="%.2f%%"),
            "barras": st.column_config.NumberColumn("Barras", format="%d"),
            "motivo_salida": st.column_config.TextColumn("Motivo salida"),
            "comisiones": st.column_config.NumberColumn("Comisiones", format="%.2f"),
        },
    )
    with st.expander("Ver tabla cruda de trades", expanded=False):
        st.dataframe(trades, width="stretch", hide_index=True)
