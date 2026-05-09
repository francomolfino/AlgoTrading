from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


def find_experiment_dirs(root: Path | str) -> list[Path]:
    """Encuentra carpetas de experimentos que tengan summary.csv."""
    root_path = Path(root)
    if not root_path.exists():
        return []
    return sorted(path for path in root_path.iterdir() if (path / "summary.csv").exists())


def compare_experiments(experiment_dirs: list[Path | str]) -> pd.DataFrame:
    """Combina summaries de varios experimentos ya ejecutados."""
    rows: list[dict[str, Any]] = []
    for directory in experiment_dirs:
        experiment_dir = Path(directory)
        summary_path = experiment_dir / "summary.csv"
        if not summary_path.exists():
            raise FileNotFoundError(f"No encontre summary.csv en {experiment_dir}.")

        summary = pd.read_csv(summary_path)
        config = _read_json(experiment_dir / "config.json")
        metadata = _read_json(experiment_dir / "metadata.json")
        for row in summary.to_dict(orient="records"):
            rows.append(
                {
                    "experiment_dir": str(experiment_dir),
                    "run_id": config.get("run_id", experiment_dir.name),
                    "experiment_name": config.get("experiment_name", experiment_dir.name),
                    "git_commit": metadata.get("git_commit"),
                    "git_dirty": metadata.get("git_dirty"),
                    **row,
                }
            )

    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame(rows)
    sort_columns = [column for column in ["total_return", "sharpe_ratio"] if column in result.columns]
    if sort_columns:
        result = result.sort_values(sort_columns, ascending=False).reset_index(drop=True)
    return result


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    return payload if isinstance(payload, dict) else {}
