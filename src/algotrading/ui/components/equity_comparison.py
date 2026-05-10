from __future__ import annotations

import pandas as pd


def combined_equity_frame(curves: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for label, curve in curves.items():
        data = curve[["date", "equity"]].copy()
        data["date"] = pd.to_datetime(data["date"])
        data = data.set_index("date").rename(columns={"equity": label})
        frames.append(data)
    return pd.concat(frames, axis=1).sort_index()


def comparison_has_mismatch(comparison: pd.DataFrame) -> bool:
    if comparison.empty:
        return False
    period_cols = [column for column in ["start_date", "end_date", "symbol"] if column in comparison]
    return any(comparison[column].nunique() > 1 for column in period_cols)
