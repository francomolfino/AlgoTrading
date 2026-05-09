import pandas as pd
import pytest
from pathlib import Path
from uuid import uuid4

from algotrading.data.storage import save_ohlcv
from algotrading.ui.adapters.backtest_adapter import (
    BacktestRequest,
    build_result_warnings,
    preflight_backtest_request,
    run_backtest_request,
    trade_details_frame,
)
from algotrading.ui.adapters.data_adapter import (
    data_summary,
    list_data_assets,
    parse_symbols,
    quality_report_frame,
    validate_data_quality,
)
from algotrading.ui.adapters.experiment_adapter import (
    critical_reading,
    delete_experiment_dir,
    diff_experiment_configs,
    list_experiments,
    load_experiment_details,
)
from algotrading.ui.adapters.paper_adapter import (
    PaperTradingRequest,
    run_paper_trading_request,
    supported_paper_strategies,
)
from algotrading.ui.adapters.portfolio_adapter import (
    PortfolioRequest,
    preflight_portfolio_request,
    run_portfolio_request,
    validate_portfolio_request,
)
from algotrading.ui.adapters.reports_adapter import build_experiment_zip, collect_experiment_report_files
from algotrading.ui.adapters.risk_adapter import RiskSettings, validate_risk_settings
from algotrading.ui.adapters.robustness_adapter import (
    RobustnessRequest,
    regime_comment,
    run_robustness_request,
)
from algotrading.ui.adapters.settings_adapter import UISettings, load_ui_settings, save_ui_settings
from algotrading.ui.adapters.strategy_adapter import (
    generate_strategy_signals,
    signal_events_frame,
    signal_summary,
    validate_strategy_parameters,
)


def _frame(prices):
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


def _workspace_tmp(name):
    path = Path("tests/.tmp") / f"{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def test_ui_data_adapter_lists_and_validates_assets():
    data_dir = _workspace_tmp("ui_data") / "data"
    save_ohlcv(_frame([100, 101, 102]), data_dir / "SPY_1D.csv")

    assets = list_data_assets(data_dir, interval="1d")
    report = validate_data_quality(_frame([100, 101, 102]))

    assert parse_symbols("spy, qqq BTC-USD spy") == ["SPY", "QQQ", "BTC-USD"]
    assert len(assets) == 1
    assert assets[0].symbol_hint == "SPY"
    assert report.is_valid
    assert data_summary(_frame([100, 101, 102])).loc[0, "column"] == "open"
    assert quality_report_frame(report)["value"].map(type).eq(str).all()


def test_ui_strategy_adapter_validates_and_summarizes_signals():
    frame = _frame([100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111])
    params = {"fast_window": 3, "slow_window": 5}

    warnings = validate_strategy_parameters("sma_cross", params, frame_length=len(frame))
    signals = generate_strategy_signals(frame, "sma_cross", params)
    summary = signal_summary(signals)

    assert warnings == []
    assert signals["signal"].tolist() == [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1]
    assert summary["entries"] == 1
    events = signal_events_frame(signals)
    assert events["event"].tolist() == ["entrada"]
    assert events.loc[0, "signal"] == 1
    assert events.loc[0, "previous_signal"] == 0
    with pytest.raises(ValueError, match="media rapida"):
        validate_strategy_parameters("sma_cross", {"fast_window": 6, "slow_window": 5})


def test_ui_risk_adapter_warns_on_aggressive_settings():
    warnings = validate_risk_settings(
        RiskSettings(position_fraction=0.9, max_total_exposure=1.0)
    )

    assert any("80%" in warning for warning in warnings)


def test_ui_backtest_adapter_runs_and_saves_experiment():
    root = _workspace_tmp("ui_backtest")
    data_dir = root / "data"
    experiments_dir = root / "experiments"
    save_ohlcv(_frame([100, 101, 102, 103, 104, 105, 106, 107]), data_dir / "SPY_1D.csv")

    artifacts = run_backtest_request(
        BacktestRequest(
            symbol="SPY",
            strategy_key="sma_cross",
            strategy_parameters={"fast_window": 3, "slow_window": 5},
            data_dir=data_dir,
            interval="1d",
            commission_bps=0,
            slippage_bps=0,
            experiment_name="adapter_test",
            experiments_root=experiments_dir,
        )
    )
    records = list_experiments(experiments_dir)
    details = load_experiment_details(records[0].path)

    assert artifacts.result.metrics["number_of_trades"] == 1
    assert build_result_warnings(artifacts.result, parameter_count=2, symbol_count=1)
    assert artifacts.experiment_dir is not None
    assert artifacts.report_path is not None
    assert artifacts.report_path.exists()
    assert len(records) == 1
    assert details.symbol == "SPY"
    assert not details.equity.empty
    assert critical_reading(details)
    assert collect_experiment_report_files(records[0].path)
    assert build_experiment_zip(records[0].path)


def test_ui_trade_details_frame_formats_trade_rows():
    trades = pd.DataFrame(
        {
            "entry_date": ["2024-01-02"],
            "exit_date": ["2024-01-05"],
            "entry_price": [100.0],
            "exit_price": [110.0],
            "shares": [2.5],
            "entry_notional": [250.0],
            "exit_notional": [275.0],
            "entry_commission": [0.25],
            "exit_commission": [0.28],
            "pnl": [24.47],
            "return_pct": [0.09788],
            "bars_held": [3],
            "exit_reason": ["signal_exit"],
        }
    )

    details = trade_details_frame(trades)

    assert details.loc[0, "entrada"] == "2024-01-02"
    assert details.loc[0, "precio_entrada"] == 100.0
    assert details.loc[0, "cantidad"] == 2.5
    assert details.loc[0, "roi_pct"] == pytest.approx(9.788)
    assert details.loc[0, "comisiones"] == pytest.approx(0.53)


def test_ui_backtest_preflight_blocks_short_period():
    root = _workspace_tmp("ui_backtest_preflight_short")
    data_dir = root / "data"
    save_ohlcv(_frame([100, 101, 102, 103, 104, 105, 106, 107]), data_dir / "SPY_1D.csv")

    preflight = preflight_backtest_request(
        BacktestRequest(
            symbol="SPY",
            strategy_key="buy_and_hold",
            strategy_parameters={},
            data_dir=data_dir,
            interval="1d",
            save_experiment=False,
        )
    )

    assert preflight.can_run is False
    assert any("Periodo demasiado corto" in error for error in preflight.errors)


def test_ui_backtest_preflight_blocks_strategy_without_entries():
    root = _workspace_tmp("ui_backtest_preflight_no_entries")
    data_dir = root / "data"
    save_ohlcv(_frame([100] * 260), data_dir / "SPY_1D.csv")

    preflight = preflight_backtest_request(
        BacktestRequest(
            symbol="SPY",
            strategy_key="breakout",
            strategy_parameters={"entry_window": 20, "exit_window": 10},
            data_dir=data_dir,
            interval="1d",
            save_experiment=False,
        )
    )

    assert preflight.can_run is False
    assert preflight.rows == 260
    assert any("no genera entradas" in error for error in preflight.errors)


def test_ui_experiment_adapter_diffs_and_deletes_experiments():
    root = _workspace_tmp("ui_experiment_diff")
    data_dir = root / "data"
    experiments_dir = root / "experiments"
    save_ohlcv(_frame([100, 101, 102, 103, 104, 105, 106, 107]), data_dir / "SPY_1D.csv")

    for fast in [3, 4]:
        run_backtest_request(
            BacktestRequest(
                symbol="SPY",
                strategy_key="sma_cross",
                strategy_parameters={"fast_window": fast, "slow_window": 5},
                data_dir=data_dir,
                interval="1d",
                commission_bps=0,
                slippage_bps=0,
                experiment_name=f"adapter_test_{fast}",
                experiments_root=experiments_dir,
            )
        )

    records = list_experiments(experiments_dir)
    diff = diff_experiment_configs(records, only_changed=True)

    assert len(records) == 2
    assert "strategy.parameters.fast_window" in diff["field"].tolist()
    experiment_columns = [column for column in diff.columns if column not in {"field", "changed"}]
    assert all(diff[column].map(type).eq(str).all() for column in experiment_columns)
    with pytest.raises(ValueError, match="Confirmacion"):
        delete_experiment_dir(records[0].path, experiments_dir, confirmation="wrong")

    deleted = delete_experiment_dir(records[0].path, experiments_dir, confirmation=records[0].path.name)

    assert deleted.exists() is False
    assert len(list_experiments(experiments_dir)) == 1


def test_ui_robustness_adapter_runs_train_test():
    root = _workspace_tmp("ui_robustness")
    data_dir = root / "data"
    save_ohlcv(_frame(list(range(100, 130))), data_dir / "SPY_1D.csv")

    result = run_robustness_request(
        RobustnessRequest(
            symbols=("SPY",),
            strategy_key="sma_cross",
            strategy_parameters={"fast_window": 3, "slow_window": 5},
            data_dir=data_dir,
            interval="1d",
            train_ratio=0.6,
            run_regime_analysis=True,
            regime_min_rows=5,
        )
    )

    assert not result.train_test.empty
    assert not result.diagnostics.empty
    assert not result.regimes.empty
    assert regime_comment(result.regimes)


def test_ui_portfolio_adapter_runs_equal_weight():
    root = _workspace_tmp("ui_portfolio")
    data_dir = root / "data"
    save_ohlcv(_frame([100, 101, 102, 103, 104, 105]), data_dir / "SPY_1D.csv")
    save_ohlcv(_frame([50, 51, 52, 53, 54, 55]), data_dir / "QQQ_1D.csv")

    result = run_portfolio_request(
        PortfolioRequest(
            symbols=("SPY", "QQQ"),
            data_dir=data_dir,
            interval="1d",
            rebalance_frequency="monthly",
        )
    )

    assert not result.portfolio_equity.empty
    assert result.correlations.shape == (2, 2)


def test_ui_portfolio_preflight_blocks_dangerous_concentration():
    root = _workspace_tmp("ui_portfolio_preflight")
    data_dir = root / "data"
    save_ohlcv(_frame(list(range(100, 360))), data_dir / "SPY_1D.csv")
    save_ohlcv(_frame(list(range(50, 310))), data_dir / "QQQ_1D.csv")

    request = PortfolioRequest(
        symbols=("SPY", "QQQ"),
        data_dir=data_dir,
        interval="1d",
        weighting_mode="manual",
        manual_weights={"SPY": 0.85, "QQQ": 0.15},
    )
    preflight = preflight_portfolio_request(request)

    assert preflight.can_run is False
    assert any("demasiada concentracion" in error for error in preflight.errors)


def test_ui_portfolio_validation_warns_on_high_but_allowed_concentration():
    warnings = validate_portfolio_request(
        PortfolioRequest(
            symbols=("SPY", "QQQ"),
            weighting_mode="manual",
            manual_weights={"SPY": 0.7, "QQQ": 0.3},
        )
    )

    assert any("concentracion" in warning for warning in warnings)


def test_ui_paper_adapter_runs_dry_run_simulation():
    root = _workspace_tmp("ui_paper")
    data_dir = root / "data"
    save_ohlcv(_frame([100, 101, 102]), data_dir / "SPY_1D.csv")

    result = run_paper_trading_request(
        PaperTradingRequest(
            symbol="SPY",
            strategy_key="buy_and_hold",
            strategy_parameters={},
            data_dir=data_dir,
            interval="1d",
            dry_run=True,
            min_trade_value=0,
        )
    )

    assert result.summary["dry_run"] == 1
    assert result.summary["fills"] == 0
    assert not result.order_events.empty


def test_ui_paper_adapter_defaults_to_simulated_fills():
    root = _workspace_tmp("ui_paper_fills")
    data_dir = root / "data"
    save_ohlcv(_frame([100, 110, 120]), data_dir / "SPY_1D.csv")

    result = run_paper_trading_request(
        PaperTradingRequest(
            symbol="SPY",
            strategy_key="buy_and_hold",
            strategy_parameters={},
            data_dir=data_dir,
            interval="1d",
            commission_bps=0,
            slippage_bps=0,
            min_trade_value=0,
        )
    )

    assert result.summary["dry_run"] == 0
    assert result.summary["fills"] == 1
    assert result.summary["total_return"] == pytest.approx(120 / 110 - 1)


def test_ui_paper_adapter_exposes_all_research_strategies():
    assert set(supported_paper_strategies()) == {
        "buy_and_hold",
        "sma_cross",
        "rsi",
        "breakout",
        "trend_filter",
    }


def test_ui_settings_adapter_saves_and_loads_json():
    root = _workspace_tmp("ui_settings")
    path = root / "settings.json"

    saved = save_ui_settings(UISettings(data_dir="custom/data", debug=True), path)
    loaded = load_ui_settings(saved)

    assert loaded.data_dir == "custom/data"
    assert loaded.debug is True
