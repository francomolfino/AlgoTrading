from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path

os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str((Path.cwd() / ".cache" / "matplotlib").resolve()))
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib.pyplot as plt
import pandas as pd


def plot_price_volume_with_moving_averages(
    frame: pd.DataFrame,
    title: str,
    ma_columns: Iterable[str],
    price_column: str = "adj_close",
) -> plt.Figure:
    """Grafica precio, medias moviles y volumen en dos paneles."""
    required_columns = ["date", price_column, "volume"]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    dates = pd.to_datetime(frame["date"])
    figure, (price_axis, volume_axis) = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(12, 7),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    price_axis.plot(dates, frame[price_column], label=price_column, linewidth=1.4)
    for column in ma_columns:
        if column in frame.columns:
            price_axis.plot(dates, frame[column], label=column, linewidth=1.1)

    price_axis.set_title(title)
    price_axis.set_ylabel("Precio")
    price_axis.grid(True, alpha=0.25)
    price_axis.legend(loc="best")

    volume_axis.bar(dates, frame["volume"], width=1.0, color="#6b7280", alpha=0.55)
    volume_axis.set_ylabel("Volumen")
    volume_axis.grid(True, axis="y", alpha=0.25)

    figure.autofmt_xdate()
    figure.tight_layout()
    return figure


def plot_equity_curve_with_drawdown(frame: pd.DataFrame, title: str) -> plt.Figure:
    """Grafica equity curve y drawdown para revisar un backtest."""
    required_columns = ["date", "equity", "drawdown"]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")

    dates = pd.to_datetime(frame["date"])
    figure, (equity_axis, drawdown_axis) = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(12, 7),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    equity_axis.plot(dates, frame["equity"], color="#2563eb", linewidth=1.5)
    equity_axis.set_title(title)
    equity_axis.set_ylabel("Equity")
    equity_axis.grid(True, alpha=0.25)

    drawdown_axis.fill_between(dates, frame["drawdown"], 0, color="#dc2626", alpha=0.35)
    drawdown_axis.set_ylabel("Drawdown")
    drawdown_axis.grid(True, axis="y", alpha=0.25)

    figure.autofmt_xdate()
    figure.tight_layout()
    return figure


def plot_equity_comparison(
    equity_curves: dict[str, pd.DataFrame],
    title: str,
) -> plt.Figure:
    """Compara curvas de equity normalizadas a 1.0."""
    if not equity_curves:
        raise ValueError("Se requiere al menos una equity curve.")

    figure, axis = plt.subplots(figsize=(12, 6))
    for name, frame in equity_curves.items():
        missing = [column for column in ["date", "equity"] if column not in frame.columns]
        if missing:
            raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
        dates = pd.to_datetime(frame["date"])
        normalized = frame["equity"] / frame["equity"].iloc[0]
        axis.plot(dates, normalized, label=name, linewidth=1.4)

    axis.set_title(title)
    axis.set_ylabel("Equity normalizada")
    axis.grid(True, alpha=0.25)
    axis.legend(loc="best")
    figure.autofmt_xdate()
    figure.tight_layout()
    return figure


def plot_portfolio_equity_and_drawdown(
    individual_equity: pd.DataFrame,
    portfolio_equity: pd.DataFrame,
    title: str,
) -> plt.Figure:
    """Grafica equity normalizada de activos y drawdown de la cartera."""
    missing = [column for column in ["date", "equity", "drawdown"] if column not in portfolio_equity.columns]
    if missing:
        raise ValueError(f"Faltan columnas requeridas: {', '.join(missing)}")
    if individual_equity.empty:
        raise ValueError("individual_equity esta vacio.")

    figure, (equity_axis, drawdown_axis) = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(12, 7),
        sharex=False,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    for column in individual_equity.columns:
        normalized = individual_equity[column] / individual_equity[column].iloc[0]
        equity_axis.plot(individual_equity.index, normalized, label=column, linewidth=1.0, alpha=0.7)

    portfolio_normalized = portfolio_equity["equity"] / portfolio_equity["equity"].iloc[0]
    equity_axis.plot(
        pd.to_datetime(portfolio_equity["date"]),
        portfolio_normalized,
        label="equal_weight",
        linewidth=2.2,
        color="#111827",
    )
    equity_axis.set_title(title)
    equity_axis.set_ylabel("Equity normalizada")
    equity_axis.grid(True, alpha=0.25)
    equity_axis.legend(loc="best")

    drawdown_axis.fill_between(
        pd.to_datetime(portfolio_equity["date"]),
        portfolio_equity["drawdown"],
        0,
        color="#dc2626",
        alpha=0.35,
    )
    drawdown_axis.set_ylabel("Drawdown cartera")
    drawdown_axis.grid(True, axis="y", alpha=0.25)

    figure.autofmt_xdate()
    figure.tight_layout()
    return figure


def plot_correlation_heatmap(correlations: pd.DataFrame, title: str) -> plt.Figure:
    """Grafica una matriz de correlaciones simple."""
    if correlations.empty:
        raise ValueError("correlations esta vacio.")
    if correlations.shape[0] != correlations.shape[1]:
        raise ValueError("La matriz de correlaciones debe ser cuadrada.")

    figure, axis = plt.subplots(figsize=(7, 6))
    image = axis.imshow(correlations.values, vmin=-1, vmax=1, cmap="coolwarm")
    axis.set_title(title)
    axis.set_xticks(range(len(correlations.columns)))
    axis.set_yticks(range(len(correlations.index)))
    axis.set_xticklabels(correlations.columns, rotation=45, ha="right")
    axis.set_yticklabels(correlations.index)

    for row_index in range(correlations.shape[0]):
        for column_index in range(correlations.shape[1]):
            value = correlations.iloc[row_index, column_index]
            axis.text(column_index, row_index, f"{value:.2f}", ha="center", va="center", fontsize=9)

    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    figure.tight_layout()
    return figure
