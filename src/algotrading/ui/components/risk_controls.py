from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.risk_adapter import RiskSettings
from algotrading.ui.texts import TOOLTIPS


def render_risk_settings(key_prefix: str) -> RiskSettings:
    with st.expander("Risk management", expanded=False):
        c1, c2, c3 = st.columns(3)
        position_fraction = c1.slider("Position sizing", 0.01, 1.0, 1.0, 0.01, help=TOOLTIPS["position_sizing"], key=f"{key_prefix}_position")
        max_total_exposure = c2.slider("Exposicion maxima", 0.01, 1.0, 1.0, 0.01, help=TOOLTIPS["exposure"], key=f"{key_prefix}_exposure")
        use_max_dd = c3.checkbox("Corte por drawdown", value=False, help=TOOLTIPS["drawdown"], key=f"{key_prefix}_use_dd")
        max_drawdown_pct = c3.slider("Max drawdown permitido", 0.01, 0.80, 0.20, 0.01, disabled=not use_max_dd, key=f"{key_prefix}_dd")

        c4, c5, c6 = st.columns(3)
        use_stop = c4.checkbox("Stop loss", value=False, help=TOOLTIPS["stop_loss"], key=f"{key_prefix}_use_stop")
        stop_loss_pct = c4.slider("Stop loss %", 0.01, 0.80, 0.10, 0.01, disabled=not use_stop, key=f"{key_prefix}_stop")
        use_take = c5.checkbox("Take profit", value=False, help=TOOLTIPS["take_profit"], key=f"{key_prefix}_use_take")
        take_profit_pct = c5.slider("Take profit %", 0.01, 2.0, 0.25, 0.01, disabled=not use_take, key=f"{key_prefix}_take")
        use_trade_limit = c6.checkbox("Limite trades/dia", value=False, key=f"{key_prefix}_use_trade_limit")
        max_trades_per_day = c6.number_input("Max trades/dia", min_value=0, value=2, step=1, disabled=not use_trade_limit, key=f"{key_prefix}_trades")

        use_vol = st.checkbox("Volatility targeting", value=False, help="Reduce exposicion si la volatilidad realizada supera el objetivo.", key=f"{key_prefix}_use_vol")
        v1, v2 = st.columns(2)
        volatility_target_pct = v1.slider("Vol objetivo anual", 0.01, 1.0, 0.15, 0.01, disabled=not use_vol, key=f"{key_prefix}_vol")
        volatility_window = v2.number_input("Ventana volatilidad", min_value=2, value=20, step=1, disabled=not use_vol, key=f"{key_prefix}_vol_window")

    return RiskSettings(
        position_fraction=float(position_fraction),
        max_total_exposure=float(max_total_exposure),
        max_drawdown_pct=float(max_drawdown_pct) if use_max_dd else None,
        max_trades_per_day=int(max_trades_per_day) if use_trade_limit else None,
        stop_loss_pct=float(stop_loss_pct) if use_stop else None,
        take_profit_pct=float(take_profit_pct) if use_take else None,
        volatility_target_pct=float(volatility_target_pct) if use_vol else None,
        volatility_window=int(volatility_window),
    )
