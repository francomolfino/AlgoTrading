from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.visualization.tradingview import (
    build_equity_drawdown_chart_html,
    build_line_comparison_chart_html,
    build_price_volume_chart_html,
)


def render_price_volume_chart(
    frame: pd.DataFrame,
    title: str,
    price_column: str = "adj_close",
    overlay_columns: tuple[str, ...] = (),
    signal_column: str | None = None,
    height: int = 560,
    show_legend: bool = True,
) -> None:
    _render_html_chart(
        html=build_price_volume_chart_html(
            frame=frame,
            title=title,
            price_column=price_column,
            overlay_columns=overlay_columns,
            signal_column=signal_column,
            height=height,
            show_legend=show_legend,
        ),
        height=height + 58,
    )


def render_equity_drawdown_chart(
    frame: pd.DataFrame,
    title: str = "Equity y drawdown",
    height: int = 560,
) -> None:
    _render_html_chart(
        html=build_equity_drawdown_chart_html(frame=frame, title=title, height=height),
        height=height + 68,
    )


def render_line_comparison_chart(
    frame: pd.DataFrame,
    title: str,
    normalize: bool = False,
    height: int = 430,
) -> None:
    _render_html_chart(
        html=build_line_comparison_chart_html(
            frame=frame,
            title=title,
            normalize=normalize,
            height=height,
        ),
        height=height + 58,
    )


def _render_html_chart(html: str, height: int) -> None:
    st.iframe(html, width="stretch", height=height)
