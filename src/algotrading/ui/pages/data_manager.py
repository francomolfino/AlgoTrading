from __future__ import annotations

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.data_adapter import (
    data_summary,
    download_and_save,
    load_data_file,
    parse_symbols,
    quality_report_frame,
    validate_data_quality,
)
from algotrading.ui.adapters.data_quality_adapter import (
    advanced_quality_frame,
    build_advanced_data_quality_report,
)
from algotrading.ui.charts import render_price_volume_chart
from algotrading.ui.components.common import (
    render_empty_state as _render_empty_state,
    render_page_header as _render_page_header,
    show_error as _show_error,
)
from algotrading.ui.components.data_quality import render_data_quality_reading as _render_data_quality_reading
from algotrading.ui.components.selectors import asset_selector as _asset_selector
from algotrading.ui.texts import EMPTY_STATES, TOOLTIPS


def render_data_manager() -> None:
    _render_page_header(
        "Data Manager",
        "Descarga, recarga y valida datos historicos locales antes de mirar estrategias.",
        area="Research",
    )
    download_tab, explore_tab = st.tabs(["Descargar datos", "Explorar datos"])

    with download_tab:
        with st.form("download_data_form"):
            symbols_raw = st.text_input("Tickers", value="SPY QQQ", help=TOOLTIPS["ticker"])
            col1, col2, col3 = st.columns(3)
            start = col1.date_input("Fecha inicial", value=pd.Timestamp("2018-01-01"), help=TOOLTIPS["date_range"])
            end_enabled = col2.checkbox("Usar fecha final", value=False)
            end = col2.date_input("Fecha final", value=pd.Timestamp.today(), disabled=not end_enabled)
            interval = col3.selectbox("Timeframe", ["1d", "1wk", "1mo"], index=0, help=TOOLTIPS["timeframe"])
            file_format = st.selectbox("Formato", ["csv", "parquet"], index=0)
            submitted = st.form_submit_button("Descargar y guardar")

        if submitted:
            symbols = parse_symbols(symbols_raw)
            if not symbols:
                st.error("Ingresa al menos un ticker.")
            else:
                with st.spinner("Descargando datos historicos..."):
                    for symbol in symbols:
                        try:
                            frame, path = download_and_save(
                                symbol=symbol,
                                start=str(start),
                                end=str(end) if end_enabled else None,
                                interval=interval,
                                data_dir=st.session_state.data_dir,
                                file_format=file_format,
                            )
                            st.success(f"{symbol}: {len(frame)} filas guardadas en {path}")
                        except Exception as exc:
                            _show_error(exc)

    with explore_tab:
        asset = _asset_selector("data_manager_asset")
        if asset is None:
            empty = EMPTY_STATES["no_data"]
            _render_empty_state(
                empty["title"],
                missing=empty["missing"],
                why_it_matters=empty["why"],
                next_step=empty["next"],
            )
            return
        try:
            frame = load_data_file(asset.path)
            report = validate_data_quality(frame)
            advanced_report = build_advanced_data_quality_report(
                frame,
                symbol=asset.symbol_hint,
                interval=asset.interval,
            )
        except Exception as exc:
            _show_error(exc)
            return

        st.write(f"Archivo: `{asset.path}`")
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Filas", report.rows)
        m2.metric("Inicio", report.start_date)
        m3.metric("Fin", report.end_date)
        m4.metric("Estado", "ok" if report.is_valid else "revisar")
        m5.metric("Data Quality", f"{advanced_report.score:.0f}/100", advanced_report.severity)
        st.caption(
            f"Calendario aplicado: `{advanced_report.calendar}` | "
            f"Fuente: `{advanced_report.calendar_provider}` | "
            f"Precision: `{advanced_report.calendar_precision}` | "
            f"Tipo detectado: `{advanced_report.asset_type}`."
        )
        st.dataframe(quality_report_frame(report), width="stretch", hide_index=True)
        _render_data_quality_reading(report)
        with st.expander("Diagnostico avanzado de calidad", expanded=advanced_report.severity != "ok"):
            st.caption(
                "Score heuristico para research local. No reemplaza revisar fuente, splits, dividendos ni calendario."
            )
            st.write(f"Tipo detectado: `{advanced_report.asset_type}`")
            st.dataframe(advanced_quality_frame(advanced_report), width="stretch", hide_index=True)
        if report.null_counts:
            st.warning(f"Valores faltantes detectados: {report.null_counts}", icon="!")
        if report.gap_count:
            st.warning("Hay gaps grandes de fechas. Puede ser normal en ETFs, pero revisalo.", icon="!")

        price_column = "adj_close" if "adj_close" in frame else "close"
        render_price_volume_chart(
            frame,
            title=f"{asset.symbol_hint} - precio y volumen",
            price_column=price_column,
            height=520,
        )
        st.subheader("Resumen estadistico")
        st.dataframe(data_summary(frame), width="stretch", hide_index=True)
        st.subheader("Vista previa")
        st.dataframe(frame.tail(50), width="stretch", hide_index=True)
