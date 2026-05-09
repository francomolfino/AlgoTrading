from __future__ import annotations

import html
import json
import math
from pathlib import Path
from uuid import uuid4

import pandas as pd

LIGHTWEIGHT_CHARTS_CDN = (
    "https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"
)

_LINE_COLORS = [
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#7c3aed",
    "#f97316",
    "#0891b2",
    "#4b5563",
]


def build_price_volume_chart_html(
    frame: pd.DataFrame,
    title: str,
    price_column: str = "adj_close",
    overlay_columns: tuple[str, ...] = (),
    signal_column: str | None = None,
    height: int = 520,
    log_scale: bool = True,
) -> str:
    """Construye un grafico interactivo de precio/volumen con Lightweight Charts."""
    if frame.empty:
        return _empty_chart_html(title, "No hay datos para graficar.", height)

    data = _date_sorted(frame)
    candles = _candlestick_data(data)
    price_line = _line_data(data, price_column)
    volume = _volume_data(data)
    overlays = [
        {"name": column, "data": _line_data(data, column), "color": _LINE_COLORS[index % len(_LINE_COLORS)]}
        for index, column in enumerate(overlay_columns)
        if column in data.columns
    ]
    markers = _signal_markers(data, signal_column) if signal_column else []
    chart_id = _dom_id("price")
    payload = {
        "chartId": chart_id,
        "title": title,
        "candles": candles,
        "priceLine": price_line,
        "volume": volume,
        "overlays": overlays,
        "markers": markers,
        "height": height,
        "logScale": log_scale,
    }
    return _html_document(
        title=title,
        body=f"""
<div class="tv-card">
  <div class="tv-title">{html.escape(title)}</div>
  {_price_legend_html(overlays, log_scale)}
  <div id="{chart_id}" class="tv-chart" style="height:{height}px;"></div>
  {_attribution_html()}
</div>
<script>
{_js_payload("payload", payload)}
{_price_chart_js()}
</script>
""",
    )


def build_equity_drawdown_chart_html(
    frame: pd.DataFrame,
    title: str,
    height: int = 540,
    log_scale: bool = True,
) -> str:
    """Construye equity curve y drawdown como HTML interactivo."""
    if frame.empty:
        return _empty_chart_html(title, "No hay equity curve para graficar.", height)

    data = _date_sorted(frame)
    equity_series = _line_data(data, "equity")
    benchmark_series = _line_data(data, "benchmark_equity") if "benchmark_equity" in data else []
    drawdown_series = _percent_line_data(data, "drawdown") if "drawdown" in data else []
    equity_id = _dom_id("equity")
    drawdown_id = _dom_id("drawdown")
    payload = {
        "equityId": equity_id,
        "drawdownId": drawdown_id,
        "title": title,
        "equity": equity_series,
        "benchmark": benchmark_series,
        "drawdown": drawdown_series,
        "equityHeight": max(260, int(height * 0.62)),
        "drawdownHeight": max(180, int(height * 0.32)),
        "logScale": log_scale,
    }
    equity_height = payload["equityHeight"]
    drawdown_height = payload["drawdownHeight"]
    return _html_document(
        title=title,
        body=f"""
<div class="tv-card">
  <div class="tv-title">{html.escape(title)}</div>
  {_equity_legend_html(has_benchmark=bool(benchmark_series), log_scale=log_scale)}
  <div id="{equity_id}" class="tv-chart" style="height:{equity_height}px;"></div>
  <div class="tv-panel-label">Drawdown (escala lineal, % negativos)</div>
  <div id="{drawdown_id}" class="tv-chart tv-chart-spaced" style="height:{drawdown_height}px;"></div>
  {_attribution_html()}
</div>
<script>
{_js_payload("payload", payload)}
{_equity_chart_js()}
</script>
""",
    )


def build_line_comparison_chart_html(
    frame: pd.DataFrame,
    title: str,
    normalize: bool = False,
    height: int = 420,
    log_scale: bool = True,
) -> str:
    """Construye un grafico multi-linea para comparar curvas."""
    if frame.empty:
        return _empty_chart_html(title, "No hay series para comparar.", height)

    data = _date_sorted(_frame_with_date_column(frame))
    series = []
    for index, column in enumerate(column for column in data.columns if column != "date"):
        values = _line_data(data, column)
        if normalize and values:
            first = values[0]["value"]
            if first:
                values = [{"time": point["time"], "value": point["value"] / first} for point in values]
        series.append(
            {
                "name": str(column),
                "data": values,
                "color": _LINE_COLORS[index % len(_LINE_COLORS)],
            }
        )
    chart_id = _dom_id("comparison")
    payload = {
        "chartId": chart_id,
        "title": title,
        "series": series,
        "height": height,
        "logScale": log_scale,
    }
    return _html_document(
        title=title,
        body=f"""
<div class="tv-card">
  <div class="tv-title">{html.escape(title)}</div>
  {_comparison_legend_html(series, log_scale)}
  <div id="{chart_id}" class="tv-chart" style="height:{height}px;"></div>
  {_attribution_html()}
</div>
<script>
{_js_payload("payload", payload)}
{_comparison_chart_js()}
</script>
""",
    )


def write_equity_drawdown_chart_html(
    frame: pd.DataFrame,
    output_path: Path | str,
    title: str,
) -> None:
    html_text = build_equity_drawdown_chart_html(frame, title=title)
    Path(output_path).write_text(html_text, encoding="utf-8")


def _html_document(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <script src="{LIGHTWEIGHT_CHARTS_CDN}"></script>
  <script>
{_base_js_helpers()}
  </script>
  <style>
    body {{ margin: 0; background: transparent; color: #111827; font-family: Arial, sans-serif; }}
    .tv-card {{ width: 100%; }}
    .tv-title {{ font-size: 15px; font-weight: 700; margin: 0 0 8px 0; }}
    .tv-subtitle {{ font-size: 12px; color: #4b5563; margin: -2px 0 8px 0; }}
    .tv-legend {{ display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center; margin: 0 0 8px 0; font-size: 12px; color: #374151; }}
    .tv-legend-item {{ display: inline-flex; align-items: center; gap: 5px; white-space: nowrap; }}
    .tv-swatch {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
    .tv-panel-label {{ margin: 9px 0 4px 0; font-size: 12px; color: #4b5563; font-weight: 600; }}
    .tv-chart {{ width: 100%; border: 1px solid #e5e7eb; border-radius: 6px; overflow: hidden; }}
    .tv-chart-spaced {{ margin-top: 10px; }}
    .tv-attribution {{ margin-top: 6px; font-size: 11px; color: #6b7280; }}
    .tv-attribution a {{ color: #2563eb; text-decoration: none; }}
    .tv-empty {{ padding: 16px; border: 1px solid #e5e7eb; border-radius: 6px; color: #6b7280; }}
  </style>
</head>
<body>
{body}
</body>
</html>"""


def _empty_chart_html(title: str, message: str, height: int) -> str:
    return _html_document(
        title,
        f"""
<div class="tv-card" style="min-height:{height}px;">
  <div class="tv-title">{html.escape(title)}</div>
  <div class="tv-empty">{html.escape(message)}</div>
  {_attribution_html()}
</div>
""",
    )


def _attribution_html() -> str:
    return (
        '<div class="tv-attribution">Graficos con '
        '<a href="https://www.tradingview.com/" target="_blank" rel="noopener">'
        'TradingView Lightweight Charts</a>. Datos propios del laboratorio.</div>'
    )


def _price_legend_html(overlays: list[dict[str, object]], log_scale: bool) -> str:
    items = [
        ("#16a34a", "Vela alcista"),
        ("#dc2626", "Vela bajista"),
        ("#94a3b8", "Volumen"),
        ("#16a34a", "Entrada"),
        ("#dc2626", "Salida"),
    ]
    for overlay in overlays:
        items.append((str(overlay["color"]), str(overlay["name"])))
    subtitle = f"Precio OHLC + volumen. Escala {'logaritmica' if log_scale else 'lineal'}."
    return _legend_html(subtitle, items)


def _equity_legend_html(has_benchmark: bool, log_scale: bool) -> str:
    items = [("#2563eb", "Equity estrategia")]
    if has_benchmark:
        items.append(("#64748b", "Benchmark / buy and hold"))
    items.append(("#dc2626", "Drawdown"))
    subtitle = f"Panel superior: equity. Escala {'logaritmica' if log_scale else 'lineal'}."
    return _legend_html(subtitle, items)


def _comparison_legend_html(series: list[dict[str, object]], log_scale: bool) -> str:
    items = [(str(item["color"]), str(item["name"])) for item in series]
    subtitle = f"Comparacion de curvas. Escala {'logaritmica' if log_scale else 'lineal'}."
    return _legend_html(subtitle, items)


def _legend_html(subtitle: str, items: list[tuple[str, str]]) -> str:
    legend_items = "\n".join(
        f'<span class="tv-legend-item"><span class="tv-swatch" style="background:{html.escape(color)}"></span>{html.escape(label)}</span>'
        for color, label in items
    )
    return f"""
  <div class="tv-subtitle">{html.escape(subtitle)}</div>
  <div class="tv-legend">{legend_items}</div>
"""


def _js_payload(name: str, payload: dict) -> str:
    return f"const {name} = {json.dumps(payload, allow_nan=False)};"


def _price_chart_js() -> str:
    return r"""
const chart = createBaseChart(payload.chartId, payload.height, payload.logScale);
let priceSeries;
if (payload.candles.length > 0) {
  priceSeries = chart.addCandlestickSeries({
    upColor: '#16a34a',
    downColor: '#dc2626',
    borderVisible: false,
    wickUpColor: '#16a34a',
    wickDownColor: '#dc2626'
  });
  priceSeries.setData(payload.candles);
} else {
  priceSeries = chart.addLineSeries({ color: '#111827', lineWidth: 2 });
  priceSeries.setData(payload.priceLine);
}
if (payload.markers.length > 0) {
  priceSeries.setMarkers(payload.markers);
}
payload.overlays.forEach((overlay) => {
  const line = chart.addLineSeries({ color: overlay.color, lineWidth: 1, priceLineVisible: false });
  line.setData(overlay.data);
});
if (payload.volume.length > 0) {
  const volumeSeries = chart.addHistogramSeries({
    color: '#94a3b8',
    priceFormat: { type: 'volume' },
    priceScaleId: ''
  });
  chart.priceScale('').applyOptions({ scaleMargins: { top: 0.80, bottom: 0 } });
  volumeSeries.setData(payload.volume);
}
chart.timeScale().fitContent();
attachResizeObserver(chart, payload.chartId);
"""


def _equity_chart_js() -> str:
    return r"""
const equityChart = createBaseChart(payload.equityId, payload.equityHeight, payload.logScale);
const equity = equityChart.addLineSeries({ color: '#2563eb', lineWidth: 2 });
equity.setData(payload.equity);
if (payload.benchmark.length > 0) {
  const benchmark = equityChart.addLineSeries({ color: '#64748b', lineWidth: 1 });
  benchmark.setData(payload.benchmark);
}
equityChart.timeScale().fitContent();
attachResizeObserver(equityChart, payload.equityId);

const drawdownChart = createBaseChart(payload.drawdownId, payload.drawdownHeight, false);
if (payload.drawdown.length > 0) {
  const drawdown = drawdownChart.addAreaSeries({
    lineColor: '#dc2626',
    topColor: 'rgba(220, 38, 38, 0.05)',
    bottomColor: 'rgba(220, 38, 38, 0.35)',
    lineWidth: 1,
    priceFormat: {
      type: 'custom',
      minMove: 0.1,
      formatter: (price) => `${price.toFixed(1)}%`
    }
  });
  drawdown.setData(payload.drawdown);
}
drawdownChart.timeScale().fitContent();
attachResizeObserver(drawdownChart, payload.drawdownId);
"""


def _comparison_chart_js() -> str:
    return r"""
const chart = createBaseChart(payload.chartId, payload.height, payload.logScale);
payload.series.forEach((item) => {
  const line = chart.addLineSeries({ color: item.color, lineWidth: 2 });
  line.setData(item.data);
});
chart.timeScale().fitContent();
attachResizeObserver(chart, payload.chartId);
"""


def _base_js_helpers() -> str:
    return r"""
function createBaseChart(containerId, height, logScale = true) {
  const container = document.getElementById(containerId);
  return LightweightCharts.createChart(container, {
    width: container.clientWidth || 800,
    height: height,
    layout: {
      background: { type: 'solid', color: '#ffffff' },
      textColor: '#374151'
    },
    grid: {
      vertLines: { color: '#eef2f7' },
      horzLines: { color: '#eef2f7' }
    },
    rightPriceScale: {
      mode: logScale ? 1 : 0,
      borderColor: '#e5e7eb'
    },
    timeScale: {
      borderColor: '#e5e7eb',
      timeVisible: false
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal
    }
  });
}

function attachResizeObserver(chart, containerId) {
  const container = document.getElementById(containerId);
  if (!window.ResizeObserver || !container) {
    return;
  }
  new ResizeObserver((entries) => {
    if (entries.length === 0) {
      return;
    }
    chart.applyOptions({ width: Math.floor(entries[0].contentRect.width) });
  }).observe(container);
}
"""


def _date_sorted(frame: pd.DataFrame) -> pd.DataFrame:
    if "date" not in frame.columns:
        raise ValueError("El DataFrame necesita columna date.")
    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data = data.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return data


def _frame_with_date_column(frame: pd.DataFrame) -> pd.DataFrame:
    if "date" in frame.columns:
        return frame.copy()
    if isinstance(frame.index, pd.DatetimeIndex):
        return frame.reset_index(names="date")
    result = frame.copy()
    result.insert(0, "date", frame.index)
    return result


def _candlestick_data(frame: pd.DataFrame) -> list[dict[str, float | str]]:
    if not {"open", "high", "low", "close"}.issubset(frame.columns):
        return []
    rows = []
    for _, row in frame.iterrows():
        values = [_safe_float(row[column]) for column in ["open", "high", "low", "close"]]
        if any(value is None for value in values):
            continue
        rows.append(
            {
                "time": _date_value(row["date"]),
                "open": values[0],
                "high": values[1],
                "low": values[2],
                "close": values[3],
            }
        )
    return rows


def _line_data(frame: pd.DataFrame, column: str) -> list[dict[str, float | str]]:
    if column not in frame.columns:
        return []
    rows = []
    for _, row in frame.iterrows():
        value = _safe_float(row[column])
        if value is None:
            continue
        rows.append({"time": _date_value(row["date"]), "value": value})
    return rows


def _percent_line_data(frame: pd.DataFrame, column: str) -> list[dict[str, float | str]]:
    raw_rows = _line_data(frame, column)
    if not raw_rows:
        return []
    max_abs = max(abs(float(row["value"])) for row in raw_rows)
    scale = 100 if max_abs <= 1 else 1
    return [
        {"time": row["time"], "value": round(float(row["value"]) * scale, 6)}
        for row in raw_rows
    ]


def _volume_data(frame: pd.DataFrame) -> list[dict[str, float | str]]:
    if "volume" not in frame.columns:
        return []
    rows = []
    for _, row in frame.iterrows():
        value = _safe_float(row["volume"])
        if value is None:
            continue
        color = "#16a34a55"
        open_value = _safe_float(row.get("open"))
        close_value = _safe_float(row.get("close"))
        if open_value is not None and close_value is not None and close_value < open_value:
            color = "#dc262655"
        rows.append({"time": _date_value(row["date"]), "value": value, "color": color})
    return rows


def _signal_markers(frame: pd.DataFrame, signal_column: str | None) -> list[dict[str, str]]:
    if signal_column is None or signal_column not in frame.columns:
        return []
    signal = pd.to_numeric(frame[signal_column], errors="coerce").fillna(0).astype(int)
    previous = signal.shift(1).fillna(0).astype(int)
    markers = []
    for index, row in frame.iterrows():
        if signal.iloc[index] == 1 and previous.iloc[index] == 0:
            markers.append(
                {
                    "time": _date_value(row["date"]),
                    "position": "belowBar",
                    "color": "#16a34a",
                    "shape": "arrowUp",
                    "text": "Entrada",
                }
            )
        elif signal.iloc[index] == 0 and previous.iloc[index] == 1:
            markers.append(
                {
                    "time": _date_value(row["date"]),
                    "position": "aboveBar",
                    "color": "#dc2626",
                    "shape": "arrowDown",
                    "text": "Salida",
                }
            )
    return markers


def _date_value(value: object) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def _safe_float(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(result):
        return None
    return result


def _dom_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"
