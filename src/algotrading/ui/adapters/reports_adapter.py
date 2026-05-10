from __future__ import annotations

from dataclasses import dataclass
from html import escape
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from algotrading.ui.adapters.research_adapter import build_research_summary


@dataclass(frozen=True)
class ReportFile:
    label: str
    path: Path
    mime: str


def collect_experiment_report_files(experiment_dir: Path | str) -> list[ReportFile]:
    root = Path(experiment_dir)
    files: list[ReportFile] = []
    for path in [
        root / "research_report.html",
        root / "config.json",
        root / "metadata.json",
        root / "experiment_metadata.json",
        root / "data_quality.json",
        root / "summary.csv",
        root / "notes.md",
        root / "research_notes.json",
    ]:
        if path.exists():
            files.append(_report_file(path))
    for symbol_dir in sorted(child for child in root.iterdir() if child.is_dir()):
        for filename in [
            "report.md",
            "equity_drawdown.html",
            "metrics.json",
            "metrics_table.csv",
            "monthly_returns.csv",
            "period_extremes.csv",
            "exposure.csv",
            "equity.csv",
            "trades.csv",
            "orders.csv",
        ]:
            path = symbol_dir / filename
            if path.exists():
                files.append(_report_file(path, label=f"{symbol_dir.name}/{filename}"))
    return files


def generate_professional_research_report(experiment_dir: Path | str) -> Path:
    """Genera un HTML portable con lectura de research, no recomendacion de inversion."""
    summary = build_research_summary(experiment_dir)
    details = summary.details
    root = Path(experiment_dir)
    report_path = root / "research_report.html"
    data_quality = summary.data_quality
    metrics_table = details.metrics_table if not details.metrics_table.empty else pd.DataFrame()
    metrics = details.metrics if isinstance(details.metrics, dict) else {}
    limitations = [
        "Reporte educativo de research; no es una recomendacion de inversion.",
        "No modela liquidez real, impuestos, spreads variables ni ejecucion parcial.",
        "Los datos dependen de la fuente historica local disponible.",
        "La evidencia estadistica puede ser insuficiente si hay pocos trades o periodo corto.",
    ]
    chart_path = _symbol_file(root, details.symbol, "equity_drawdown.html")
    equity_html = _chart_embed(root, chart_path)
    data_quality_html = _data_quality_html(data_quality)
    preset = summary.research_preset
    outputs = summary.experiment_metadata.get("outputs", {})

    html = f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(details.path.name)} - Research Report</title>
  <style>
    :root {{ --ink: #101828; --muted: #667085; --line: #d0d5dd; --soft: #f9fafb; --accent: #155eef; }}
    body {{ font-family: Arial, sans-serif; margin: 0; color: #1f2933; line-height: 1.45; background: white; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px; }}
    h1, h2, h3 {{ color: var(--ink); }}
    h1 {{ margin-bottom: 8px; }}
    h2 {{ border-top: 1px solid var(--line); padding-top: 24px; margin-top: 32px; }}
    a {{ color: var(--accent); }}
    .muted {{ color: var(--muted); }}
    .notice {{ border: 1px solid #fdb022; background: #fffbeb; padding: 14px; border-radius: 8px; margin: 18px 0; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; }}
    .card {{ border: 1px solid #e4e7ec; border-radius: 8px; padding: 12px; background: #fff; }}
    .card strong {{ display: block; margin-bottom: 6px; color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .toc {{ border: 1px solid #e4e7ec; border-radius: 8px; padding: 12px 16px; background: var(--soft); }}
    .pill {{ display: inline-block; border: 1px solid var(--line); border-radius: 999px; padding: 3px 9px; margin: 2px; font-size: 12px; }}
    .ok {{ background: #ecfdf3; border-color: #abefc6; }}
    .warn {{ background: #fffaeb; border-color: #fedf89; }}
    .bad {{ background: #fef3f2; border-color: #fecdca; }}
    table {{ border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 14px; }}
    th, td {{ border: 1px solid #e4e7ec; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f2f4f7; }}
    code {{ background: #f2f4f7; padding: 2px 4px; border-radius: 4px; }}
    iframe {{ width: 100%; min-height: 620px; border: 1px solid var(--line); border-radius: 8px; }}
    @media print {{ iframe {{ display: none; }} .no-print {{ display: none; }} main {{ padding: 12px; }} }}
  </style>
</head>
<body>
<main>
  <h1>Reporte de Research</h1>
  <p class="muted">{escape(details.path.name)}</p>
  <div class="notice">
    <strong>No es recomendacion de inversion.</strong>
    Este reporte resume evidencia para investigar una estrategia en un laboratorio local. No habilita trading real.
  </div>
  <div class="toc">
    <strong>Contenido</strong>
    <ol>
      <li><a href="#diagnostico">Diagnostico ejecutivo</a></li>
      <li><a href="#journal">Hipotesis, conclusion y proximo test</a></li>
      <li><a href="#preset">Research preset</a></li>
      <li><a href="#evidencia">Evidence Score y verdict</a></li>
      <li><a href="#datos">Datos y calidad</a></li>
      <li><a href="#metricas">Metricas, benchmark y curvas</a></li>
      <li><a href="#trades">Trades y periodos</a></li>
      <li><a href="#robustez">Robustez y stress</a></li>
      <li><a href="#reproducibilidad">Ficha reproducible</a></li>
      <li><a href="#limitaciones">Limitaciones</a></li>
    </ol>
  </div>

  <h2 id="diagnostico">Diagnostico ejecutivo</h2>
  <div class="grid">
    {_metric_card("Experimento", details.path.name)}
    {_metric_card("Preset", summary.research_preset.label)}
    {_metric_card("Research Verdict", summary.verdict.reliability)}
    {_metric_card("Evidence Score", f"{summary.evidence_score.score:.0f}/100")}
    {_metric_card("Pipeline", summary.pipeline_state)}
    {_metric_card("Data Quality", f"{data_quality.score:.0f}/100" if data_quality else "no disponible")}
    {_metric_card("Retorno total", _format_html_metric(metrics.get("total_return"), percent=True))}
    {_metric_card("Max drawdown", _format_html_metric(metrics.get("max_drawdown"), percent=True))}
    {_metric_card("Trades", _format_html_metric(metrics.get("number_of_trades")))}
    {_metric_card("Benchmark", summary.verdict.benchmark_status)}
  </div>
  <p><strong>Proxima accion:</strong> {escape(summary.recommended_next_action)}</p>
  <h3>Flags criticos</h3>
  {_list_html(summary.critical_flags or ("Sin flags criticos obvios.",))}

  <h2 id="journal">Hipotesis, conclusion y proximo test</h2>
  <p><strong>Hipotesis:</strong> {escape(summary.journal_hypothesis or "no disponible")}</p>
  <p><strong>Conclusion:</strong> {escape(summary.journal_conclusion or "no disponible")}</p>
  <p><strong>Proximo test:</strong> {escape(summary.journal_next_test or "no disponible")}</p>
  <p><strong>Estado journal:</strong> {escape(summary.journal_state or "no disponible")}</p>
  <p><strong>Tags:</strong> {escape(", ".join(summary.journal_tags) or "no disponible")}</p>

  <h2 id="preset">Research preset</h2>
  <p>{escape(preset.description)}</p>
  <p>{escape(preset.ui_text)}</p>
  <h3>Checks requeridos</h3>
  {_list_html(preset.required_checks)}
  <h3>Metricas importantes</h3>
  {_list_html(preset.important_metrics)}
  <p><strong>Evidence minimo del preset:</strong> {preset.minimum_evidence_score}/100</p>
  <p><strong>Accion recomendada por preset:</strong> {escape(preset.recommended_next_action)}</p>

  <h2 id="evidencia">Evidence Score y Research Verdict</h2>
  <div class="grid">
    {_metric_card("Score", f"{summary.evidence_score.score:.0f}/100")}
    {_metric_card("Lectura", summary.evidence_score.label)}
    {_metric_card("Confiabilidad", summary.verdict.reliability)}
    {_metric_card("Benchmark", summary.verdict.benchmark_status)}
  </div>
  <p>{escape(summary.evidence_score.explanation)}</p>
  <p>{escape(summary.verdict.summary)}</p>
  <h3>Componentes del Evidence Score</h3>
  {_df_to_html(pd.DataFrame([component.__dict__ for component in summary.evidence_score.components]))}
  <h3>Diagnosticos del verdict</h3>
  {_df_to_html(pd.DataFrame([{"diagnostico": key, "valor": value} for key, value in summary.verdict.diagnostics]))}

  <h2 id="datos">Datos y calidad</h2>
  {_mapping_table(summary.experiment_metadata.get("data", {}))}
  {data_quality_html}

  <h2 id="metricas">Metricas, benchmark y curvas</h2>
  {_df_to_html(metrics_table if not metrics_table.empty else details.summary)}
  <p>{escape(summary.verdict.benchmark_status)}</p>
  {equity_html}

  <h2 id="trades">Trades y periodos</h2>
  <h3>Trades recientes</h3>
  {_df_to_html(details.trades.tail(25))}
  <h3>Retornos mensuales recientes</h3>
  {_df_to_html(details.monthly_returns.tail(24))}
  <h3>Mejores y peores periodos</h3>
  {_df_to_html(details.period_extremes)}
  <h3>Exposicion</h3>
  {_df_to_html(details.exposure)}

  <h2 id="robustez">Robustez y stress</h2>
  <h3>Robustez</h3>
  {_mapping_table(summary.robustness_summary or {"estado": "no corrida"})}
  <h3>Stress tests</h3>
  {_mapping_table(summary.stress_summary or {"estado": "no corrido"})}

  <h2 id="reproducibilidad">Ficha reproducible</h2>
  <h3>Configuracion completa</h3>
  {_mapping_table(details.config)}
  <h3>Proyecto</h3>
  {_mapping_table(summary.experiment_metadata.get("project", {}))}
  <h3>Costos</h3>
  {_mapping_table(summary.experiment_metadata.get("costs", {}))}
  <h3>Risk settings</h3>
  {_mapping_table(summary.experiment_metadata.get("risk", {}))}
  <h3>Archivos generados</h3>
  {_outputs_table(root, outputs)}

  <h2 id="limitaciones">Limitaciones</h2>
  {_list_html(limitations)}
  <p class="muted">Generado localmente por AlgoTrading Lab.</p>
</main>
</body>
</html>
"""
    report_path.write_text(html, encoding="utf-8")
    return report_path


def build_experiment_zip(experiment_dir: Path | str) -> bytes:
    root = Path(experiment_dir).resolve()
    if not root.exists():
        raise FileNotFoundError(f"No existe la carpeta: {root}")
    if not (root / "summary.csv").exists():
        raise ValueError("No parece ser una carpeta de experimento valida: falta summary.csv.")

    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            archive.write(path, arcname=path.relative_to(root))
    return buffer.getvalue()


def _metric_card(label: str, value: object) -> str:
    return f'<div class="card"><strong>{escape(label)}</strong><br>{escape(str(value))}</div>'


def _mapping_table(mapping: object) -> str:
    if not isinstance(mapping, dict) or not mapping:
        return "<p>Sin datos.</p>"
    rows = []
    for key, value in mapping.items():
        rows.append(f"<tr><th>{escape(str(key))}</th><td>{escape(_display_value(value))}</td></tr>")
    return "<table><tbody>" + "".join(rows) + "</tbody></table>"


def _df_to_html(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "<p>Sin datos.</p>"
    display = frame.copy()
    for column in display.columns:
        display[column] = display[column].map(_display_value)
    return display.to_html(index=False, escape=True)


def _list_html(items) -> str:
    return "<ul>" + "".join(f"<li>{escape(str(item))}</li>" for item in items) + "</ul>"


def _display_value(value: object) -> str:
    if value is None:
        return "no disponible"
    if isinstance(value, dict):
        return ", ".join(f"{key}={_display_value(item)}" for key, item in value.items()) if value else "{}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_display_value(item) for item in value) if value else "[]"
    return str(value)


def _format_html_metric(value: object, *, percent: bool = False) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "no disponible"
    if pd.isna(numeric):
        return "no disponible"
    if percent:
        return f"{numeric:.2%}"
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}"


def _symbol_file(root: Path, symbol: str | None, filename: str) -> Path | None:
    if not symbol:
        return None
    candidates = [
        root / str(symbol).replace("-", "_").upper() / filename,
        root / str(symbol).replace("-", "_") / filename,
        root / str(symbol).upper() / filename,
        root / str(symbol) / filename,
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _chart_embed(root: Path, chart_path: Path | None) -> str:
    if chart_path is None or not chart_path.exists():
        return "<p>Grafico interactivo no disponible.</p>"
    relative = escape(chart_path.relative_to(root).as_posix())
    return (
        '<div class="no-print">'
        f'<iframe src="{relative}" title="Equity y drawdown"></iframe>'
        "</div>"
        f'<p><a href="{relative}">Abrir grafico interactivo en pestana separada</a></p>'
    )


def _data_quality_html(report) -> str:
    if report is None:
        return "<p>Data Quality no disponible para este experimento.</p>"
    status_class = "ok" if report.severity == "ok" else "bad" if report.severity == "critical" else "warn"
    issue_rows = []
    for issue in report.issues:
        issue_rows.append(
            {
                "check": issue.check,
                "severity": issue.severity,
                "message": issue.message,
                "count": issue.count,
                "penalty": issue.penalty,
            }
        )
    issues = pd.DataFrame(issue_rows)
    return (
        '<div class="grid">'
        f'{_metric_card("Score", f"{report.score:.0f}/100")}'
        f'{_metric_card("Severidad", report.severity)}'
        f'{_metric_card("Tipo de activo", report.asset_type)}'
        f'{_metric_card("Calendario", report.calendar)}'
        f'{_metric_card("Fuente calendario", report.calendar_provider)}'
        f'{_metric_card("Precision calendario", report.calendar_precision)}'
        f'{_metric_card("Rango", f"{report.start_date} a {report.end_date}")}'
        "</div>"
        f"<p>Medias jornadas detectadas: {escape(', '.join(report.calendar_early_closes) or 'ninguna/no disponible')}</p>"
        f'<p><span class="pill {status_class}">Estado: {escape(report.severity)}</span></p>'
        "<h3>Issues de calidad</h3>"
        f"{_df_to_html(issues)}"
    )


def _outputs_table(root: Path, outputs: object) -> str:
    if not isinstance(outputs, dict) or not outputs:
        return "<p>No hay outputs registrados.</p>"
    rows = []
    for label, path_value in outputs.items():
        path = Path(str(path_value))
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = path
        relative_text = relative.as_posix()
        rows.append(
            {
                "archivo": escape(str(label)),
                "path": f'<a href="{escape(relative_text)}">{escape(relative_text)}</a>',
            }
        )
    return _html_table(rows)


def _html_table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "<p>Sin datos.</p>"
    columns = list(rows[0])
    head = "".join(f"<th>{escape(str(column))}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{row.get(column, '')}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"


def _report_file(path: Path, label: str | None = None) -> ReportFile:
    suffix = path.suffix.lower()
    if suffix == ".json":
        mime = "application/json"
    elif suffix == ".csv":
        mime = "text/csv"
    elif suffix == ".md":
        mime = "text/markdown"
    elif suffix == ".html":
        mime = "text/html"
    else:
        mime = "application/octet-stream"
    return ReportFile(label=label or path.name, path=path, mime=mime)
