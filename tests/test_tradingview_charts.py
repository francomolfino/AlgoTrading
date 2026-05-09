import pandas as pd

from algotrading.visualization.tradingview import (
    build_equity_drawdown_chart_html,
    build_line_comparison_chart_html,
    build_price_volume_chart_html,
)


def test_build_price_volume_chart_html_contains_candles_volume_and_markers():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=4, freq="D"),
            "open": [100, 101, 102, 101],
            "high": [102, 103, 104, 102],
            "low": [99, 100, 101, 100],
            "close": [101, 102, 101, 100],
            "adj_close": [101, 102, 101, 100],
            "volume": [1000, 1200, 900, 1100],
            "sma_2": [None, 101.5, 101.5, 100.5],
            "signal": [0, 1, 1, 0],
        }
    )

    html = build_price_volume_chart_html(
        frame,
        title="SPY",
        overlay_columns=("sma_2",),
        signal_column="signal",
    )

    assert "lightweight-charts" in html
    assert "addCandlestickSeries" in html
    assert "addHistogramSeries" in html
    assert "Entrada" in html
    assert "Salida" in html
    assert "Precio OHLC + volumen" in html
    assert "Vela alcista" in html
    assert "TradingView Lightweight Charts" in html
    assert '"logScale": true' in html
    assert "mode: logScale ? 1 : 0" in html


def test_build_equity_drawdown_chart_html_contains_benchmark_and_drawdown():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=3, freq="D"),
            "equity": [1000, 1100, 1050],
            "benchmark_equity": [1000, 1080, 1040],
            "drawdown": [0.0, 0.0, -0.045],
        }
    )

    html = build_equity_drawdown_chart_html(frame, title="Equity")

    assert "benchmark" in html
    assert "drawdown" in html
    assert "addAreaSeries" in html
    assert "Equity estrategia" in html
    assert "Benchmark / buy and hold" in html
    assert "Drawdown (escala lineal, % negativos)" in html
    assert '"logScale": true' in html
    assert "createBaseChart(payload.drawdownId, payload.drawdownHeight, false)" in html
    assert '"value": -4.5' in html
    assert "formatter: (price) => `${price.toFixed(1)}%`" in html


def test_build_equity_drawdown_chart_html_scales_fractional_drawdown_to_percent_points():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=2, freq="D"),
            "equity": [1000, 448.1],
            "drawdown": [0.0, -0.5519],
        }
    )

    html = build_equity_drawdown_chart_html(frame, title="Drawdown")

    assert '"value": -55.19' in html


def test_build_equity_drawdown_chart_html_keeps_percent_point_drawdown_scale():
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=2, freq="D"),
            "equity": [1000, 500],
            "drawdown": [0.0, -50.0],
        }
    )

    html = build_equity_drawdown_chart_html(frame, title="Drawdown")

    assert '"value": -50.0' in html
    assert '"value": -5000.0' not in html


def test_build_line_comparison_chart_html_supports_datetime_index():
    frame = pd.DataFrame(
        {"a": [100, 110], "b": [100, 105]},
        index=pd.date_range("2024-01-01", periods=2, freq="D"),
    )

    html = build_line_comparison_chart_html(frame, title="Comparacion", normalize=True)

    assert "Comparacion" in html
    assert "Comparacion de curvas" in html
    assert ">a</span>" in html
    assert '"value": 1.1' in html
    assert '"logScale": true' in html
