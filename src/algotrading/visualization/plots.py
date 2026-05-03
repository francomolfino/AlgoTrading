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
