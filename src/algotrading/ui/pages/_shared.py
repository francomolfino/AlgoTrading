from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from algotrading.ui.adapters.backtest_adapter import (
    BacktestRequest,
    BacktestRunArtifacts,
    BacktestPreflight,
    build_result_warnings,
    metric_cards,
    metrics_frame,
    preflight_backtest_request,
    run_backtest_request,
    trade_details_frame,
)
from algotrading.ui.adapters.data_adapter import (
    data_summary,
    download_and_save,
    list_data_assets,
    load_data_file,
    load_symbol_data,
    parse_symbols,
    quality_report_frame,
    validate_data_quality,
)
from algotrading.ui.adapters.experiment_adapter import (
    ExperimentDetails,
    ExperimentRecord,
    compare_experiment_records,
    critical_reading,
    delete_experiment_dir,
    diff_experiment_configs,
    details_metrics_frame,
    filter_records,
    list_experiments,
    load_equity_curves,
    load_experiment_details,
    records_frame,
    sort_records,
)
from algotrading.ui.adapters.guided_adapter import (
    GUIDED_WORKFLOW_STEPS,
    ExperimentDraft,
    build_draft_backtest_request,
    build_draft_robustness_request,
    guided_step_label,
    new_experiment_draft,
    recommend_journal_status,
    update_experiment_draft,
)
from algotrading.ui.adapters.journal_adapter import (
    RESEARCH_NOTE_STATUSES,
    ResearchNotes,
    load_research_notes,
    parse_tags,
    save_research_notes,
    tags_to_text,
)
from algotrading.ui.adapters.paper_adapter import (
    PaperTradingRequest,
    run_paper_trading_request,
    supported_paper_strategies,
)
from algotrading.ui.adapters.portfolio_adapter import (
    PortfolioPreflight,
    PortfolioRequest,
    preflight_portfolio_request,
    run_portfolio_request,
)
from algotrading.ui.adapters.reports_adapter import build_experiment_zip, collect_experiment_report_files
from algotrading.ui.adapters.research_adapter import (
    ResearchSummary,
    build_research_summary,
    compare_experiment_fairness,
    research_records_cache_signature,
    research_records_frame,
    research_records_frame_from_paths,
    save_robustness_for_experiment,
    save_stress_for_experiment,
    suggested_journal_status,
)
from algotrading.ui.adapters.risk_adapter import RiskSettings
from algotrading.ui.adapters.robustness_adapter import (
    RobustnessRequest,
    regime_comment,
    robustness_comment,
    run_robustness_request,
)
from algotrading.ui.adapters.settings_adapter import UISettings, load_ui_settings, save_ui_settings
from algotrading.ui.adapters.stress_adapter import (
    StressTestResult,
    StressTestRequest,
    equity_curves_frame,
    run_stress_test_request,
)
from algotrading.ui.adapters.strategy_adapter import (
    STRATEGIES,
    default_parameters,
    generate_strategy_signals,
    get_strategy_config,
    signal_events_frame,
    signal_summary,
    strategy_metadata_frame,
    validate_strategy_parameters,
)
from algotrading.ui.charts import (
    render_equity_drawdown_chart,
    render_line_comparison_chart,
    render_price_volume_chart,
)
from algotrading.ui.adapters.evidence_adapter import (
    build_evidence_score_from_details,
    build_evidence_score_from_result,
)
from algotrading.ui.components.evidence_score import render_evidence_score
from algotrading.ui.components.navigation import go_to_page as _go_to_page, nav_button as _nav_button
from algotrading.ui.components.research_diagnostic import render_research_diagnostic
from algotrading.ui.components.research_verdict import render_research_verdict
from algotrading.ui.adapters.verdict_adapter import (
    build_research_verdict_from_details,
    build_research_verdict_from_result,
)
from algotrading.ui.texts import (
    EDUCATIONAL_WARNING,
    METRIC_EXPLANATIONS,
    PAPER_SIMULATION_WARNING,
    RESEARCH_FLOW_STEPS,
    RESULT_READING_ORDER,
    TOOLTIPS,
)

def render_placeholder(page: str) -> None:
    st.title(page)
    st.info(
        "Pantalla pendiente para la segunda iteracion. La base ya quedo preparada "
        "con adapters y navegacion segura."
    )
    if page == "Paper Trading Simulator":
        st.warning("Modo simulacion. No se envian ordenes reales.")


def _render_backtest_result(artifacts: BacktestRunArtifacts) -> None:
    result = artifacts.result
    st.subheader(f"Resultado: {artifacts.request.symbol} - {artifacts.strategy_name}")
    render_research_verdict(
        build_research_verdict_from_result(
            result,
            parameter_count=len(artifacts.request.strategy_parameters),
            symbol_count=1,
        )
    )
    render_evidence_score(
        build_evidence_score_from_result(
            result,
            parameter_count=len(artifacts.request.strategy_parameters),
            symbol_count=1,
            strategy_key=artifacts.request.strategy_key,
            symbol=artifacts.request.symbol,
            robustness_result=_matching_robustness(
                artifacts.request.strategy_key,
                artifacts.request.strategy_parameters,
                artifacts.request.symbol,
            ),
            stress_result=_matching_stress_test(
                artifacts.request.strategy_key,
                artifacts.request.strategy_parameters,
                artifacts.request.symbol,
                interval=artifacts.request.interval,
                start=artifacts.request.start,
                end=artifacts.request.end,
            ),
        )
    )
    _render_result_reading_order()
    cols = st.columns(6)
    for column, (label, value) in zip(cols, metric_cards(result.metrics)):
        column.metric(label, value)
    _render_equity_and_drawdown(result.equity_curve)
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
    st.subheader("Trades")
    _render_trade_details(result.trades)


def _render_experiment_details(details: ExperimentDetails) -> None:
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
        _render_equity_and_drawdown(details.equity)
    st.subheader("Lectura critica")
    for warning in critical_reading(details):
        st.warning(warning)
    st.subheader("Metricas")
    metrics_table = details.metrics_table if not details.metrics_table.empty else details_metrics_frame(details)
    st.dataframe(metrics_table, width="stretch", hide_index=True)
    _render_metric_guide()

    tabs = st.tabs(["Trades", "Retornos mensuales", "Mejores/peores periodos", "Config", "Metadata"])
    with tabs[0]:
        _render_trade_details(details.trades)
    with tabs[1]:
        st.dataframe(details.monthly_returns, width="stretch", hide_index=True)
    with tabs[2]:
        st.dataframe(details.period_extremes, width="stretch", hide_index=True)
    with tabs[3]:
        st.json(details.config)
    with tabs[4]:
        st.json(summary.experiment_metadata)


def _render_equity_and_drawdown(equity: pd.DataFrame) -> None:
    if equity.empty:
        st.warning("No hay equity curve para mostrar.")
        return
    data = equity.copy()
    data["date"] = pd.to_datetime(data["date"])
    render_equity_drawdown_chart(data, title="Equity y drawdown", height=560)


def _render_trade_details(trades: pd.DataFrame) -> None:
    if trades.empty:
        st.info("No hay trades cerrados para mostrar.")
        return
    try:
        display = trade_details_frame(trades)
    except Exception as exc:
        st.warning("No pude construir la vista amigable de trades. Muestro tabla cruda.")
        _show_error(exc)
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


def _render_signal_tables(signal_frame: pd.DataFrame) -> None:
    st.subheader("Tablas de senales")
    st.caption("La vista mas util suele ser cambios de senal: entradas y salidas. Las ultimas filas solas pueden enganar.")
    price_column = "adj_close" if "adj_close" in signal_frame else "close"
    events = signal_events_frame(signal_frame, price_column=price_column)
    tabs = st.tabs(["Cambios de senal", "Primeras filas", "Ultimas filas", "Dataset completo"])
    with tabs[0]:
        if events.empty:
            st.info("No hubo cambios de senal en el periodo seleccionado.")
        else:
            st.dataframe(
                events,
                width="stretch",
                hide_index=True,
                column_config={
                    "price": st.column_config.NumberColumn("Precio", format="%.4f"),
                    "signal": st.column_config.NumberColumn("Signal", format="%d"),
                    "previous_signal": st.column_config.NumberColumn("Signal previa", format="%d"),
                },
            )
    with tabs[1]:
        st.dataframe(signal_frame.head(80), width="stretch", hide_index=True)
    with tabs[2]:
        st.dataframe(signal_frame.tail(80), width="stretch", hide_index=True)
    with tabs[3]:
        st.warning("Mostrar todo el dataset puede ser pesado si descargaste muchos datos intradia.")
        st.dataframe(signal_frame, width="stretch", hide_index=True)


def _render_stress_result(result: StressTestResult) -> None:
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


def _render_next_step(data_assets, experiments) -> None:
    if not data_assets:
        st.warning("Siguiente paso: descarga o carga datos en Data Manager.")
    elif not experiments:
        st.info("Siguiente paso: revisa senales en Strategy Lab y corre un primer backtest guardado.")
    else:
        st.success("Ya hay datos y experimentos. Siguiente paso: comparar resultados y correr robustez.")


def _render_bullets(items: list[str]) -> None:
    for item in items:
        st.markdown(f"- {item}")


def _render_strategy_research_metadata(strategy_key: str) -> None:
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


def _experiment_request_defaults(details: ExperimentDetails) -> dict:
    config = details.config if isinstance(details.config, dict) else {}
    strategy_config = config.get("strategy", {})
    backtest_config = config.get("backtest", {})
    if not isinstance(strategy_config, dict):
        strategy_config = {}
    if not isinstance(backtest_config, dict):
        backtest_config = {}

    symbols = tuple(str(symbol) for symbol in (config.get("symbols") or []) if str(symbol))
    strategy_parameters = strategy_config.get("parameters", {})
    if not isinstance(strategy_parameters, dict):
        strategy_parameters = {}

    return {
        "symbol": details.symbol,
        "symbols": symbols,
        "data_dir": Path(str(config.get("data_dir", st.session_state.data_dir))),
        "interval": str(config.get("interval", st.session_state.interval)),
        "start": _optional_config_text(config.get("start")),
        "end": _optional_config_text(config.get("end")),
        "price_column": str(config.get("price_column", "adj_close")),
        "strategy_key": str(strategy_config.get("name", "")),
        "strategy_parameters": strategy_parameters,
        "initial_capital": _config_float(backtest_config, "initial_capital", 10_000.0),
        "commission_bps": _config_float(backtest_config, "commission_bps", 1.0),
        "slippage_bps": _config_float(backtest_config, "slippage_bps", 2.0),
    }


def _render_experiment_config_summary(record: ExperimentRecord, defaults: dict) -> None:
    st.caption(
        "Configuracion cargada desde experimento: "
        f"`{record.name}` | activo `{defaults['symbol']}` | "
        f"estrategia `{defaults['strategy_key']}` | timeframe `{defaults['interval']}`"
    )
    with st.expander("Ver parametros cargados", expanded=False):
        st.json(
            {
                "path": str(record.path),
                "symbols": defaults["symbols"],
                "data_dir": str(defaults["data_dir"]),
                "start": defaults["start"],
                "end": defaults["end"],
                "price_column": defaults["price_column"],
                "strategy_parameters": defaults["strategy_parameters"],
                "initial_capital": defaults["initial_capital"],
                "commission_bps": defaults["commission_bps"],
                "slippage_bps": defaults["slippage_bps"],
            }
        )


def _render_linked_journal_status_action(experiment_path: str | None, key_prefix: str) -> None:
    if not experiment_path:
        return
    try:
        summary = build_research_summary(experiment_path)
        suggested = suggested_journal_status(summary)
        notes = load_research_notes(experiment_path)
    except Exception as exc:
        _show_error(exc)
        return

    st.divider()
    st.subheader("Estado del journal")
    st.caption(
        "El estado no cambia automaticamente porque es una conclusion editorial. "
        "La app puede sugerirlo usando robustez y stress tests conectados al experimento."
    )
    c1, c2 = st.columns(2)
    c1.metric("Estado actual", notes.status)
    c2.metric("Estado sugerido", suggested)
    if notes.status == suggested:
        st.success("El journal ya refleja la evidencia disponible.")
        return
    if notes.status not in {"Draft", "Needs Review"}:
        st.info("No sobrescribo un estado curado manualmente. Cambialo desde Experiment Journal si queres.")
        return
    if st.button("Aplicar estado sugerido al journal", key=f"{key_prefix}_apply_suggested_status"):
        path = save_research_notes(
            experiment_path,
            ResearchNotes(
                status=suggested,
                hypothesis=notes.hypothesis,
                conclusion=notes.conclusion,
                next_test=notes.next_test,
                tags=notes.tags,
                favorite=notes.favorite,
            ),
        )
        st.success(f"Estado actualizado en `{path}`")
        st.rerun()


def _config_float(config: dict, key: str, default: float) -> float:
    try:
        return float(config.get(key, default))
    except (TypeError, ValueError):
        return default


def _optional_config_text(value: object) -> str | None:
    if value is None or str(value).strip() == "":
        return None
    return str(value)


def _render_data_quality_reading(report) -> None:
    if not report.is_valid:
        st.error("No uses estos datos para backtest hasta corregir la validacion.")
        return
    if report.rows < 252:
        st.warning("Hay menos de un ano aproximado de barras diarias; cualquier metrica sera fragil.")
    elif report.gap_count or report.null_counts or report.suspicious_rows:
        st.warning("Los datos pasan validacion basica, pero tienen puntos a revisar antes de confiar.")
    else:
        st.success("Datos aptos para exploracion basica. Igual revisa fuente, splits y periodo.")


def _render_backtest_preflight(preflight: BacktestPreflight) -> None:
    st.subheader("Validacion previa")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Barras", preflight.rows)
    c2.metric("Inicio", preflight.start_date)
    c3.metric("Fin", preflight.end_date)
    c4.metric("Entradas", preflight.entries)
    if preflight.errors:
        for error in preflight.errors:
            st.error(error)
    if preflight.warnings:
        for warning in preflight.warnings:
            st.warning(warning)
    if preflight.can_run:
        st.success("Validacion previa aprobada. Esto no garantiza calidad, solo evita errores obvios.")


def _render_portfolio_preflight(preflight: PortfolioPreflight) -> None:
    st.subheader("Validacion previa")
    c1, c2, c3 = st.columns(3)
    c1.metric("Fechas comunes", preflight.aligned_rows)
    c2.metric("Inicio comun", preflight.start_date)
    c3.metric("Fin comun", preflight.end_date)
    if preflight.rows_by_symbol:
        st.dataframe(
            pd.DataFrame(
                [{"activo": symbol, "filas": rows} for symbol, rows in preflight.rows_by_symbol.items()]
            ),
            width="stretch",
            hide_index=True,
        )
    if preflight.errors:
        for error in preflight.errors:
            st.error(error)
    if preflight.warnings:
        for warning in preflight.warnings:
            st.warning(warning)
    if preflight.can_run:
        st.success("Portfolio validado: pesos, datos y fechas comunes pasan controles basicos.")


def _render_signal_reading(strategy_key: str, summary: dict[str, int | float], rows: int) -> None:
    entries = int(summary["entries"])
    exposure = float(summary["exposure_ratio"])
    if entries == 0:
        st.warning("Esta configuracion no genera entradas en el periodo. El backtest no va a decir mucho.")
    elif entries < 5 and strategy_key != "buy_and_hold":
        st.warning("Pocas entradas: la muestra de trades probablemente sera debil.")
    if exposure > 0.95 and strategy_key != "buy_and_hold":
        st.warning("La senal esta casi siempre long; tal vez se parece demasiado a buy and hold.")
    if rows < 252:
        st.warning("Poco historial para evaluar senales con confianza.")


def _render_metric_guide() -> None:
    with st.expander("Como leer estas metricas", expanded=False):
        for metric, explanation in METRIC_EXPLANATIONS.items():
            st.markdown(f"- **{metric}:** {explanation}")


def _render_result_reading_order() -> None:
    with st.expander("Orden recomendado de lectura", expanded=False):
        _render_bullets(RESULT_READING_ORDER)


def _render_critical_reading_from_result(artifacts: BacktestRunArtifacts) -> None:
    warnings = build_result_warnings(
        artifacts.result,
        parameter_count=len(artifacts.request.strategy_parameters),
        symbol_count=1,
    )
    st.subheader("Lectura critica")
    for warning in warnings or ["No hay alertas obvias, pero esto sigue siendo solo research."]:
        st.warning(warning)


def _price_overlay_columns(frame: pd.DataFrame) -> tuple[str, ...]:
    prefixes = ("sma_", "rolling_high_", "rolling_low_")
    columns = [
        column
        for column in frame.columns
        if column.startswith(prefixes) and pd.api.types.is_numeric_dtype(frame[column])
    ]
    return tuple(columns[:5])


def _asset_selector(key: str):
    assets = list_data_assets(st.session_state.data_dir, st.session_state.interval)
    if not assets:
        return None
    return st.selectbox(
        "Activo local",
        options=assets,
        format_func=lambda asset: f"{asset.symbol_hint} ({asset.interval}, {asset.rows} filas)",
        help=TOOLTIPS["ticker"],
        key=key,
    )


def _experiment_selector(key: str) -> ExperimentRecord | None:
    records = list_experiments(st.session_state.experiments_dir)
    if not records:
        return None
    return st.selectbox(
        "Experimento",
        records,
        format_func=lambda record: f"{record.name} - {record.strategy} - {', '.join(record.symbols)}",
        key=key,
    )


def _strategy_selector(key: str) -> str:
    return st.selectbox(
        "Estrategia",
        list(STRATEGIES),
        format_func=lambda strategy_key: STRATEGIES[strategy_key].label,
        key=key,
    )


def _render_strategy_parameters(strategy_key: str, key_prefix: str) -> dict[str, int | float]:
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


def _render_risk_settings(key_prefix: str) -> RiskSettings:
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


def _combined_equity_frame(curves: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for label, curve in curves.items():
        data = curve[["date", "equity"]].copy()
        data["date"] = pd.to_datetime(data["date"])
        data = data.set_index("date").rename(columns={"equity": label})
        frames.append(data)
    return pd.concat(frames, axis=1).sort_index()


def _comparison_has_mismatch(comparison: pd.DataFrame) -> bool:
    if comparison.empty:
        return False
    period_cols = [column for column in ["start_date", "end_date", "symbol"] if column in comparison]
    return any(comparison[column].nunique() > 1 for column in period_cols)


def _matching_robustness(
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


def _matching_stress_test(
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


def _same_optional_date(left: object, right: object) -> bool:
    return str(left or "") == str(right or "")


def _get_guided_draft() -> ExperimentDraft:
    draft = st.session_state.get("experiment_draft")
    if not isinstance(draft, ExperimentDraft):
        draft = new_experiment_draft(st.session_state.get("interval", "1d"))
        st.session_state.experiment_draft = draft
    return draft


def _set_guided_draft(draft: ExperimentDraft) -> None:
    st.session_state.experiment_draft = draft
    st.session_state.pending_guided_step = draft.step


def _asset_index(assets, symbol: str | None) -> int:
    if symbol is None:
        return 0
    for index, asset in enumerate(assets):
        if asset.symbol_hint == symbol:
            return index
    return 0


def _strategy_index(strategy_keys: list[str], strategy_key: str) -> int:
    try:
        return strategy_keys.index(strategy_key)
    except ValueError:
        return 0


def _show_error(exc: Exception) -> None:
    st.error(str(exc))
    if st.session_state.get("debug", False):
        st.exception(exc)

__all__ = [name for name in globals() if not name.startswith("__")]
