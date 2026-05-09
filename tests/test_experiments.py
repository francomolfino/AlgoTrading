import json
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from algotrading.data.storage import build_data_path, save_ohlcv
from algotrading.experiments import (
    build_strategy_spec,
    compare_experiments,
    load_experiment_config,
    run_experiment_config,
)


def _ohlcv_frame(prices):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(prices), freq="D"),
            "open": prices,
            "high": [price + 1 for price in prices],
            "low": [price - 1 for price in prices],
            "close": prices,
            "adj_close": prices,
            "volume": [1_000] * len(prices),
        }
    )


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _sandbox():
    path = Path("tests/.tmp/experiment_tests") / uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_load_experiment_config_requires_json_object():
    path = _sandbox() / "bad.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="objeto JSON"):
        load_experiment_config(path)


def test_build_strategy_spec_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="no soportada"):
        build_strategy_spec({"name": "magic"}, price_column="adj_close")


def test_run_experiment_config_saves_reproducible_outputs():
    sandbox = _sandbox()
    data_dir = sandbox / "data"
    save_ohlcv(_ohlcv_frame([100, 101, 102, 103, 104, 105]), build_data_path(data_dir, "SPY", "1d", "csv"))
    config_path = sandbox / "config.json"
    _write_json(
        config_path,
        {
            "experiment_name": "test_sma",
            "run_id": "fixed_run",
            "symbols": ["SPY"],
            "data_dir": str(data_dir),
            "interval": "1d",
            "output_root": str(sandbox / "experiments"),
            "strategy": {
                "name": "sma_cross",
                "parameters": {"fast_window": 2, "slow_window": 3},
            },
            "backtest": {
                "initial_capital": 1_000,
                "commission_bps": 0,
                "slippage_bps": 0,
            },
        },
    )

    result = run_experiment_config(config_path)

    assert result.experiment_dir.name == "FIXED_RUN_TEST_SMA"
    assert (result.experiment_dir / "config.json").exists()
    assert (result.experiment_dir / "metadata.json").exists()
    assert (result.experiment_dir / "summary.csv").exists()
    assert (result.experiment_dir / "SPY" / "equity.csv").exists()
    assert (result.experiment_dir / "SPY" / "trades.csv").exists()
    assert (result.experiment_dir / "SPY" / "orders.csv").exists()
    assert (result.experiment_dir / "SPY" / "metrics.json").exists()
    assert (result.experiment_dir / "SPY" / "report.md").exists()
    assert (result.experiment_dir / "SPY" / "monthly_returns.csv").exists()
    assert (result.experiment_dir / "SPY" / "period_extremes.csv").exists()
    assert (result.experiment_dir / "SPY" / "exposure.csv").exists()
    assert (result.experiment_dir / "figures" / "SPY_equity.png").exists()
    assert result.summary.loc[0, "symbol"] == "SPY"
    assert result.summary.loc[0, "strategy"] == "sma_cross_2_3"


def test_compare_experiments_combines_summaries():
    sandbox = _sandbox()
    for run_id, total_return in [("run_a", 0.10), ("run_b", 0.20)]:
        directory = sandbox / run_id
        directory.mkdir()
        _write_json(
            directory / "config.json",
            {"run_id": run_id, "experiment_name": f"experiment_{run_id}"},
        )
        _write_json(directory / "metadata.json", {"git_commit": "abc123", "git_dirty": False})
        pd.DataFrame(
            [
                {
                    "symbol": "SPY",
                    "strategy": "buy_and_hold",
                    "total_return": total_return,
                    "sharpe_ratio": 1.0,
                }
            ]
        ).to_csv(directory / "summary.csv", index=False)

    comparison = compare_experiments([sandbox / "run_a", sandbox / "run_b"])

    assert comparison["run_id"].tolist() == ["run_b", "run_a"]
    assert comparison.loc[0, "total_return"] == pytest.approx(0.20)
    assert comparison.loc[0, "git_commit"] == "abc123"
