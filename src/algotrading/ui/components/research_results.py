from __future__ import annotations

import streamlit as st

from algotrading.ui.adapters.backtest_adapter import (
    BacktestRunArtifacts,
    build_result_warnings,
    metric_cards,
    metrics_frame,
)
from algotrading.ui.adapters.evidence_adapter import build_evidence_score_from_result
from algotrading.ui.adapters.experiment_adapter import (
    ExperimentDetails,
    critical_reading,
    details_metrics_frame,
)
from algotrading.ui.adapters.preset_adapter import get_research_preset
from algotrading.ui.adapters.research_adapter import build_research_summary
from algotrading.ui.adapters.verdict_adapter import build_research_verdict_from_result
from algotrading.ui.components.evidence_score import render_evidence_score
from algotrading.ui.components.research_diagnostic import render_research_diagnostic
from algotrading.ui.components.reproducibility import render_reproducibility_sheet
from algotrading.ui.components.research_presets import render_preset_summary
from algotrading.ui.components.research_verdict import render_research_verdict
from algotrading.ui.components.result_views import render_equity_and_drawdown, render_trade_details
from algotrading.ui.texts import METRIC_EXPLANATIONS, RESULT_READING_ORDER


def render_backtest_result(artifacts: BacktestRunArtifacts) -> None:
    result = artifacts.result
    st.subheader(f"Resultado: {artifacts.request.symbol} - {artifacts.strategy_name}")
    saved_summary = _render_backtest_research_header(artifacts)
    _render_result_reading_order()
    cols = st.columns(6)
    for column, (label, value) in zip(cols, metric_cards(result.metrics)):
        column.metric(label, value)
    render_equity_and_drawdown(result.equity_curve)
    st.subheader("Metricas")
    st.dataframe(metrics_frame(result.metrics), width="stretch", hide_index=True)
    _render_metric_guide()
    _render_critical_reading_from_result(artifacts)
    if artifacts.experiment_dir:
        st.success(f"Experimento guardado en `{artifacts.experiment_dir}`")
    if artifacts.report_path and artifacts.report_path.exists():
        st.write(f"Reporte: `{artifacts.report_path}`")
        st.download_button(
            "Descargar reporte Markdown",
            data=artifacts.report_path.read_text(encoding="utf-8"),
            file_name="report.md",
            mime="text/markdown",
        )
    if saved_summary is not None:
        render_reproducibility_sheet(saved_summary.experiment_metadata, saved_summary.details.config)
    st.subheader("Trades")
    render_trade_details(result.trades)


def render_experiment_details(details: ExperimentDetails) -> None:
    st.subheader(f"{details.path.name}")
    if details.notes:
        st.info(details.notes)
    c1, c2, c3 = st.columns(3)
    c1.write(f"Activo: `{details.symbol}`")
    c2.write(f"Ejecucion: `{details.metadata.get('created_at_utc', 'n/a')}`")
    c3.write(f"Path: `{details.path}`")

    if not details.metrics:
        st.warning("No encontre metrics.json en este experimento.")
        return
    summary = build_research_summary(details.path)
    render_research_diagnostic(summary)
    _render_result_reading_order()
    cols = st.columns(6)
    for column, (label, value) in zip(cols, metric_cards(details.metrics)):
        column.metric(label, value)
    if not details.equity.empty:
        render_equity_and_drawdown(details.equity)
    st.subheader("Lectura critica")
    for warning in critical_reading(details):
        st.warning(warning)
    st.subheader("Metricas")
    metrics_table = details.metrics_table if not details.metrics_table.empty else details_metrics_frame(details)
    st.dataframe(metrics_table, width="stretch", hide_index=True)
    _render_metric_guide()

    render_reproducibility_sheet(summary.experiment_metadata, details.config)

    tabs = st.tabs(["Trades", "Retornos mensuales", "Mejores/peores periodos", "JSON crudo"])
    with tabs[0]:
        render_trade_details(details.trades)
    with tabs[1]:
        st.dataframe(details.monthly_returns, width="stretch", hide_index=True)
    with tabs[2]:
        st.dataframe(details.period_extremes, width="stretch", hide_index=True)
    with tabs[3]:
        st.caption("config.json")
        st.json(details.config)
        st.caption("metadata reproducible")
        st.json(summary.experiment_metadata)


def matching_robustness(
    strategy_key: str | None,
    strategy_parameters: dict[str, int | float],
    symbol: str | None,
):
    result = st.session_state.get("latest_robustness")
    request = st.session_state.get("latest_robustness_request")
    if result is None or request is None:
        return None
    if strategy_key and request.strategy_key != strategy_key:
        return None
    if dict(request.strategy_parameters) != dict(strategy_parameters):
        return None
    if symbol and symbol not in request.symbols:
        return None
    return result


def matching_stress_test(
    strategy_key: str | None,
    strategy_parameters: dict[str, int | float],
    symbol: str | None,
    *,
    interval: str | None = None,
    start: str | None = None,
    end: str | None = None,
):
    result = st.session_state.get("latest_stress_test")
    request = getattr(result, "request", None)
    if result is None or request is None:
        return None
    if strategy_key and request.strategy_key != strategy_key:
        return None
    if dict(request.strategy_parameters) != dict(strategy_parameters):
        return None
    if symbol and request.symbol != symbol:
        return None
    if interval is not None and request.interval != interval:
        return None
    if not _same_optional_date(request.start, start) or not _same_optional_date(request.end, end):
        return None
    return result


def _render_backtest_research_header(artifacts: BacktestRunArtifacts):
    if artifacts.experiment_dir is not None and artifacts.experiment_dir.exists():
        try:
            summary = build_research_summary(artifacts.experiment_dir)
            render_research_diagnostic(summary)
            return summary
        except Exception as exc:
            st.warning("No pude cargar el diagnostico persistido. Muestro diagnostico temporal.")
            _show_error(exc)

    st.subheader("Diagnostico de Research temporal")
    render_preset_summary(get_research_preset(artifacts.request.research_preset))
    st.warning(
        "Este backtest todavia no funciona como experimento completo: no tiene pipeline, "
        "journal ni robustez/stress persistidos. Guardalo como experimento para que sea reproducible."
    )
    render_research_verdict(
        build_research_verdict_from_result(
            artifacts.result,
            parameter_count=len(artifacts.request.strategy_parameters),
            symbol_count=1,
        )
    )
    render_evidence_score(
        build_evidence_score_from_result(
            artifacts.result,
            parameter_count=len(artifacts.request.strategy_parameters),
            symbol_count=1,
            strategy_key=artifacts.request.strategy_key,
            symbol=artifacts.request.symbol,
            robustness_result=matching_robustness(
                artifacts.request.strategy_key,
                artifacts.request.strategy_parameters,
                artifacts.request.symbol,
            ),
            stress_result=matching_stress_test(
                artifacts.request.strategy_key,
                artifacts.request.strategy_parameters,
                artifacts.request.symbol,
                interval=artifacts.request.interval,
                start=artifacts.request.start,
                end=artifacts.request.end,
            ),
        )
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pipeline", "no disponible")
    c2.metric("Journal", "no disponible")
    c3.metric("Robustez", "no persistida")
    c4.metric("Stress", "no persistido")
    st.info("Proxima accion sugerida: volver a correr guardando el experimento o abrir el experimento guardado si ya existe.")
    return None


def _render_metric_guide() -> None:
    with st.expander("Como leer estas metricas", expanded=False):
        for metric, explanation in METRIC_EXPLANATIONS.items():
            st.markdown(f"- **{metric}:** {explanation}")


def _render_result_reading_order() -> None:
    with st.expander("Orden recomendado de lectura", expanded=False):
        for item in RESULT_READING_ORDER:
            st.markdown(f"- {item}")


def _render_critical_reading_from_result(artifacts: BacktestRunArtifacts) -> None:
    warnings = build_result_warnings(
        artifacts.result,
        parameter_count=len(artifacts.request.strategy_parameters),
        symbol_count=1,
    )
    st.subheader("Lectura critica")
    for warning in warnings or ["No hay alertas obvias, pero esto sigue siendo solo research."]:
        st.warning(warning)


def _same_optional_date(left: object, right: object) -> bool:
    return str(left or "") == str(right or "")


def _show_error(exc: Exception) -> None:
    st.error(str(exc))
    if st.session_state.get("debug", False):
        st.exception(exc)
