from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import pandas as pd

from algotrading.backtesting import BacktestResult
from algotrading.visualization.tradingview import write_equity_drawdown_chart_html
from algotrading.visualization.plots import plot_equity_curve_with_drawdown


@dataclass(frozen=True)
class BacktestReportArtifacts:
    report_path: Path
    metrics_table_path: Path
    monthly_returns_path: Path
    period_extremes_path: Path
    exposure_path: Path
    figure_path: Path
    interactive_figure_path: Path


def generate_backtest_report(
    result: BacktestResult,
    output_dir: Path | str,
    symbol: str,
    strategy_name: str,
    window: int = 21,
    top_n: int = 5,
) -> BacktestReportArtifacts:
    """Genera un reporte Markdown y tablas derivadas para un backtest."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    metrics_table = build_metrics_table(result.metrics)
    monthly_returns = calculate_monthly_returns(result.equity_curve)
    period_extremes = build_period_extremes(result.equity_curve, window=window, top_n=top_n)
    exposure = build_exposure_summary(result.equity_curve)
    comment = build_report_comment(result.metrics, exposure)

    metrics_table_path = output_path / "metrics_table.csv"
    monthly_returns_path = output_path / "monthly_returns.csv"
    period_extremes_path = output_path / "period_extremes.csv"
    exposure_path = output_path / "exposure.csv"
    figure_path = output_path / "equity_drawdown.png"
    interactive_figure_path = output_path / "equity_drawdown.html"
    report_path = output_path / "report.md"

    metrics_table.to_csv(metrics_table_path, index=False)
    monthly_returns.to_csv(monthly_returns_path, index=False)
    period_extremes.to_csv(period_extremes_path, index=False)
    exposure.to_csv(exposure_path, index=False)

    figure = plot_equity_curve_with_drawdown(
        result.equity_curve,
        title=f"{symbol} - {strategy_name}",
    )
    figure.savefig(figure_path, dpi=140, bbox_inches="tight")
    write_equity_drawdown_chart_html(
        result.equity_curve,
        interactive_figure_path,
        title=f"{symbol} - {strategy_name}",
    )

    report_path.write_text(
        _render_markdown_report(
            symbol=symbol,
            strategy_name=strategy_name,
            metrics_table=metrics_table,
            monthly_returns=monthly_returns,
            period_extremes=period_extremes,
            exposure=exposure,
            trades=result.trades,
            comment=comment,
        ),
        encoding="utf-8",
    )

    return BacktestReportArtifacts(
        report_path=report_path,
        metrics_table_path=metrics_table_path,
        monthly_returns_path=monthly_returns_path,
        period_extremes_path=period_extremes_path,
        exposure_path=exposure_path,
        figure_path=figure_path,
        interactive_figure_path=interactive_figure_path,
    )


def build_metrics_table(metrics: dict[str, float | int]) -> pd.DataFrame:
    rows = [
        ("initial_capital", "Capital inicial", "currency"),
        ("final_equity", "Equity final", "currency"),
        ("total_return", "Retorno total", "percent"),
        ("cagr", "CAGR", "percent"),
        ("sharpe_ratio", "Sharpe aprox.", "number"),
        ("max_drawdown", "Max drawdown", "percent"),
        ("win_rate", "Win rate", "percent"),
        ("number_of_trades", "Numero de trades", "integer"),
        ("total_commissions", "Comisiones totales", "currency"),
        ("benchmark_total_return", "Retorno benchmark", "percent"),
        ("benchmark_max_drawdown", "Drawdown benchmark", "percent"),
        ("excess_return_vs_benchmark", "Exceso vs benchmark", "percent"),
    ]
    table_rows = []
    for key, label, kind in rows:
        value = metrics.get(key, math.nan)
        table_rows.append(
            {
                "metric": key,
                "label": label,
                "value": value,
                "formatted": _format_value(value, kind),
            }
        )
    return pd.DataFrame(table_rows)


def calculate_monthly_returns(equity_curve: pd.DataFrame) -> pd.DataFrame:
    frame = _equity_frame(equity_curve)
    grouped = frame["equity"].groupby(frame.index.to_period("M")).last()
    monthly_returns = grouped.pct_change(fill_method=None)
    if len(monthly_returns):
        monthly_returns.iloc[0] = grouped.iloc[0] / frame["equity"].iloc[0] - 1
    return pd.DataFrame(
        {
            "month": [str(month) for month in monthly_returns.index],
            "monthly_return": monthly_returns.values,
        }
    )


def build_period_extremes(
    equity_curve: pd.DataFrame,
    window: int = 21,
    top_n: int = 5,
) -> pd.DataFrame:
    if window <= 0:
        raise ValueError("window debe ser mayor a cero.")
    if top_n <= 0:
        raise ValueError("top_n debe ser mayor a cero.")

    frame = _equity_frame(equity_curve)
    effective_window = min(window, len(frame) - 1)
    if effective_window <= 0:
        return pd.DataFrame(columns=["kind", "rank", "start_date", "end_date", "window_bars", "return"])

    rolling_returns = frame["equity"] / frame["equity"].shift(effective_window) - 1
    records = []
    for end_position, value in enumerate(rolling_returns):
        if pd.isna(value):
            continue
        start_position = end_position - effective_window
        records.append(
            {
                "start_date": frame.index[start_position],
                "end_date": frame.index[end_position],
                "window_bars": effective_window,
                "return": float(value),
            }
        )

    returns = pd.DataFrame(records)
    if returns.empty:
        return pd.DataFrame(columns=["kind", "rank", "start_date", "end_date", "window_bars", "return"])

    worst = returns.nsmallest(top_n, "return").reset_index(drop=True)
    best = returns.nlargest(top_n, "return").reset_index(drop=True)
    worst.insert(0, "rank", range(1, len(worst) + 1))
    best.insert(0, "rank", range(1, len(best) + 1))
    worst.insert(0, "kind", "worst")
    best.insert(0, "kind", "best")
    combined = pd.concat([worst, best], ignore_index=True)
    combined["start_date"] = pd.to_datetime(combined["start_date"]).dt.strftime("%Y-%m-%d")
    combined["end_date"] = pd.to_datetime(combined["end_date"]).dt.strftime("%Y-%m-%d")
    return combined


def build_exposure_summary(equity_curve: pd.DataFrame) -> pd.DataFrame:
    if equity_curve.empty:
        raise ValueError("equity_curve esta vacia.")
    if "position" in equity_curve.columns:
        exposed = pd.to_numeric(equity_curve["position"], errors="coerce").fillna(0) != 0
    elif "shares" in equity_curve.columns:
        exposed = pd.to_numeric(equity_curve["shares"], errors="coerce").fillna(0) > 0
    else:
        raise ValueError("La equity_curve necesita position o shares para calcular exposicion.")

    total_bars = int(len(equity_curve))
    exposed_bars = int(exposed.sum())
    average_target_exposure = (
        float(pd.to_numeric(equity_curve["target_exposure"], errors="coerce").fillna(0).mean())
        if "target_exposure" in equity_curve.columns
        else math.nan
    )
    return pd.DataFrame(
        [
            {
                "total_bars": total_bars,
                "exposed_bars": exposed_bars,
                "cash_bars": total_bars - exposed_bars,
                "exposure_ratio": exposed_bars / total_bars,
                "average_target_exposure": average_target_exposure,
            }
        ]
    )


def build_report_comment(metrics: dict[str, float | int], exposure: pd.DataFrame) -> str:
    total_return = float(metrics.get("total_return", math.nan))
    excess_return = float(metrics.get("excess_return_vs_benchmark", math.nan))
    drawdown = float(metrics.get("max_drawdown", math.nan))
    benchmark_drawdown = float(metrics.get("benchmark_max_drawdown", math.nan))
    exposure_ratio = float(exposure.loc[0, "exposure_ratio"])
    trades = int(metrics.get("number_of_trades", 0))

    parts = []
    if not math.isnan(excess_return):
        if excess_return > 0:
            parts.append("Supero al benchmark en retorno total durante este periodo.")
        elif excess_return < 0:
            parts.append("Quedo por debajo del benchmark en retorno total durante este periodo.")
        else:
            parts.append("Empato al benchmark en retorno total durante este periodo.")

    if not math.isnan(drawdown) and not math.isnan(benchmark_drawdown):
        if drawdown > benchmark_drawdown:
            parts.append("El drawdown fue menor que el benchmark.")
        elif drawdown < benchmark_drawdown:
            parts.append("El drawdown fue mayor que el benchmark.")

    parts.append(f"Estuvo expuesta al mercado {_format_percent(exposure_ratio)} del tiempo.")
    parts.append(f"Genero {trades} trades cerrados.")

    if trades < 5:
        parts.append("La muestra de trades es chica; evita sacar conclusiones fuertes.")
    if not math.isnan(total_return) and total_return > 1.0 and trades < 3:
        parts.append("Resultado llamativo con pocos trades: revisar robustez antes de confiar.")

    return " ".join(parts)


def _render_markdown_report(
    symbol: str,
    strategy_name: str,
    metrics_table: pd.DataFrame,
    monthly_returns: pd.DataFrame,
    period_extremes: pd.DataFrame,
    exposure: pd.DataFrame,
    trades: pd.DataFrame,
    comment: str,
) -> str:
    lines = [
        f"# Reporte de backtest: {symbol} - {strategy_name}",
        "",
        "## Comentario automatico",
        "",
        comment,
        "",
        "## Metricas",
        "",
        _markdown_table(metrics_table[["label", "formatted"]], ["Metrica", "Valor"]),
        "",
        "Grafico interactivo: `equity_drawdown.html`. Grafico estatico: `equity_drawdown.png`.",
        "",
        "## Exposicion",
        "",
        _markdown_table(_formatted_exposure(exposure), ["Metrica", "Valor"]),
        "",
        "## Retornos mensuales recientes",
        "",
        _markdown_table(_format_monthly_returns(monthly_returns.tail(12)), ["Mes", "Retorno"]),
        "",
        "## Mejores y peores periodos",
        "",
        _markdown_table(_format_period_extremes(period_extremes), ["Tipo", "Rank", "Inicio", "Fin", "Barras", "Retorno"]),
        "",
        "## Trades",
        "",
        f"Trades cerrados: {len(trades)}. Ver `trades.csv` para la lista completa.",
    ]
    if not trades.empty:
        lines.extend(
            [
                "",
                _markdown_table(
                    _format_trades_preview(trades.tail(10)),
                    ["Entrada", "Salida", "Retorno", "PnL", "Motivo"],
                ),
            ]
        )
    lines.extend(
        [
            "",
            "## Nota prudente",
            "",
            "Este reporte es educativo. No modela todos los costos, liquidez, impuestos, spreads variables ni ejecucion real.",
            "",
        ]
    )
    return "\n".join(lines)


def _equity_frame(equity_curve: pd.DataFrame) -> pd.DataFrame:
    required = ["date", "equity"]
    missing = [column for column in required if column not in equity_curve.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
    frame = equity_curve[required].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["equity"] = pd.to_numeric(frame["equity"], errors="coerce")
    if frame.isna().any().any():
        raise ValueError("Hay fechas o equity invalidos.")
    if (frame["equity"] <= 0).any():
        raise ValueError("La equity debe ser positiva.")
    return frame.sort_values("date").set_index("date")


def _markdown_table(frame: pd.DataFrame, headers: list[str]) -> str:
    if frame.empty:
        return "_Sin datos._"
    rows = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for record in frame.astype(str).to_dict(orient="records"):
        rows.append("| " + " | ".join(record.values()) + " |")
    return "\n".join(rows)


def _formatted_exposure(exposure: pd.DataFrame) -> pd.DataFrame:
    row = exposure.iloc[0]
    return pd.DataFrame(
        [
            {"metric": "Barras totales", "value": str(int(row["total_bars"]))},
            {"metric": "Barras expuestas", "value": str(int(row["exposed_bars"]))},
            {"metric": "Barras en cash", "value": str(int(row["cash_bars"]))},
            {"metric": "Exposicion", "value": _format_percent(float(row["exposure_ratio"]))},
            {
                "metric": "Target exposure promedio",
                "value": _format_percent(float(row["average_target_exposure"])),
            },
        ]
    )


def _format_monthly_returns(monthly_returns: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "month": monthly_returns["month"],
            "monthly_return": monthly_returns["monthly_return"].map(_format_percent),
        }
    )


def _format_period_extremes(period_extremes: pd.DataFrame) -> pd.DataFrame:
    if period_extremes.empty:
        return period_extremes
    result = period_extremes.copy()
    result["kind"] = result["kind"].replace({"best": "mejor", "worst": "peor"})
    result["return"] = result["return"].map(_format_percent)
    return result[["kind", "rank", "start_date", "end_date", "window_bars", "return"]]


def _format_trades_preview(trades: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "entry_date": pd.to_datetime(trades["entry_date"]).dt.strftime("%Y-%m-%d"),
            "exit_date": pd.to_datetime(trades["exit_date"]).dt.strftime("%Y-%m-%d"),
            "return_pct": trades["return_pct"].map(_format_percent),
            "pnl": trades["pnl"].map(lambda value: _format_value(value, "currency")),
            "exit_reason": trades["exit_reason"],
        }
    )


def _format_value(value: float | int, kind: str) -> str:
    if pd.isna(value):
        return "n/a"
    if kind == "percent":
        return _format_percent(float(value))
    if kind == "currency":
        return f"{float(value):,.2f}"
    if kind == "integer":
        return str(int(value))
    return f"{float(value):.2f}"


def _format_percent(value: float) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{value:.2%}"
