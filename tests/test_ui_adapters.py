from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

from algotrading.data.storage import save_ohlcv
from algotrading.backtesting import BacktestConfig, BacktestResult
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
from algotrading.ui.adapters.guided_adapter import (
    GUIDED_WORKFLOW_STEPS,
    build_draft_backtest_request,
    build_draft_robustness_request,
    guided_step_label,
    new_experiment_draft,
    recommend_journal_status,
    update_experiment_draft,
)
from algotrading.ui.adapters.journal_adapter import (
    DEFAULT_RESEARCH_STATUS,
    RESEARCH_NOTE_STATUSES,
    RESEARCH_NOTES_FILENAME,
    ResearchNotes,
    load_research_notes,
    parse_tags,
    save_research_notes,
    tags_to_text,
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
from algotrading.ui.adapters.research_adapter import (
    build_research_summary,
    load_robustness_for_experiment,
    load_stress_for_experiment,
    research_records_frame,
    save_robustness_for_experiment,
    save_stress_for_experiment,
)
from algotrading.ui.adapters.risk_adapter import RiskSettings, validate_risk_settings
from algotrading.ui.adapters.robustness_adapter import (
    RobustnessResult,
    RobustnessRequest,
    regime_comment,
    run_robustness_request,
)
from algotrading.ui.adapters.settings_adapter import UISettings, load_ui_settings, save_ui_settings
from algotrading.ui.adapters.stress_adapter import (
    StressTestResult,
    StressTestRequest,
    equity_curves_frame,
    run_stress_test_request,
    stress_conclusion,
)
from algotrading.ui.adapters.strategy_adapter import (
    STRATEGIES,
    generate_strategy_signals,
    get_strategy_config,
    signal_events_frame,
    signal_summary,
    strategy_metadata_frame,
    validate_strategy_parameters,
)
from algotrading.ui.adapters.evidence_adapter import (
    build_evidence_score_from_result,
    components_frame,
)
from algotrading.ui.adapters.verdict_adapter import build_research_verdict_from_result


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
    config = get_strategy_config("sma_cross")

    warnings = validate_strategy_parameters("sma_cross", params, frame_length=len(frame))
    signals = generate_strategy_signals(frame, "sma_cross", params)
    summary = signal_summary(signals)
    metadata = strategy_metadata_frame("sma_cross")

    assert config.category == "Trend following"
    assert config.expected_market_regime
    assert config.failure_modes
    assert config.recommended_tests
    assert config.complexity_level == "Baja-media"
    assert metadata["campo"].tolist() == [
        "Categoria",
        "Regimen esperado",
        "Complejidad",
        "Modos de falla",
        "Tests recomendados",
    ]
    assert warnings == []
    assert signals["signal"].tolist() == [0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1]
    assert summary["entries"] == 1
    events = signal_events_frame(signals)
    assert events["event"].tolist() == ["entrada"]
    assert events.loc[0, "signal"] == 1
    assert events.loc[0, "previous_signal"] == 0
    with pytest.raises(ValueError, match="media rapida"):
        validate_strategy_parameters("sma_cross", {"fast_window": 6, "slow_window": 5})


def test_strategy_registry_metadata_is_complete_for_all_strategies():
    assert set(STRATEGIES) == {"buy_and_hold", "sma_cross", "rsi", "breakout", "trend_filter"}

    for strategy_key, config in STRATEGIES.items():
        metadata = strategy_metadata_frame(strategy_key)

        assert config.category
        assert config.expected_market_regime
        assert config.failure_modes
        assert config.recommended_tests
        assert config.complexity_level
        assert metadata.shape == (5, 2)
        assert metadata["valor"].map(lambda value: isinstance(value, str) and bool(value)).all()
        assert all(parameter.help for parameter in config.parameters)


def test_ui_risk_adapter_warns_on_aggressive_settings():
    warnings = validate_risk_settings(
        RiskSettings(position_fraction=0.9, max_total_exposure=1.0)
    )

    assert any("80%" in warning for warning in warnings)


def test_guided_draft_builds_backtest_and_robustness_requests():
    draft = new_experiment_draft(interval="1wk")

    assert len(GUIDED_WORKFLOW_STEPS) == 7
    assert guided_step_label(999).startswith("7.")
    assert draft.step == 1
    assert draft.strategy_key == "sma_cross"
    assert draft.strategy_parameters == {"fast_window": 50, "slow_window": 200}
    with pytest.raises(ValueError, match="activo"):
        build_draft_backtest_request(draft, data_dir="data/raw", experiments_root="experiments")

    configured = update_experiment_draft(
        draft,
        step=99,
        symbol="SPY",
        strategy_key="rsi",
        strategy_parameters={"window": 14, "oversold": 30.0, "overbought": 70.0},
        start="2020-01-01",
        end="2023-12-31",
        price_column="close",
        initial_capital=25_000,
        commission_bps=1.5,
        slippage_bps=3.0,
        risk=RiskSettings(position_fraction=0.5, max_total_exposure=0.75),
        experiment_name="guided_test",
        notes="hipotesis inicial",
    )
    backtest_request = build_draft_backtest_request(
        configured,
        data_dir="data/raw",
        experiments_root="experiments",
    )
    robustness_request = build_draft_robustness_request(
        configured,
        symbols=("SPY", "QQQ"),
        data_dir="data/raw",
        train_ratio=0.6,
        run_walk_forward=True,
    )

    assert draft.symbol is None
    assert configured.step == 7
    assert backtest_request.symbol == "SPY"
    assert backtest_request.strategy_key == "rsi"
    assert backtest_request.save_experiment is True
    assert backtest_request.risk.position_fraction == 0.5
    assert robustness_request.symbols == ("SPY", "QQQ")
    assert robustness_request.train_ratio == 0.6
    assert robustness_request.interval == "1wk"


def test_guided_journal_status_is_recommended_from_robustness_and_stress():
    robustness = RobustnessResult(
        train_test=pd.DataFrame(),
        walk_forward=pd.DataFrame(),
        regimes=pd.DataFrame(),
        diagnostics=pd.DataFrame(
            [
                {"symbol": "SPY", "strategy": "buy_and_hold", "flags": ""},
                {"symbol": "SPY", "strategy": "sma_cross_50_200", "flags": ""},
            ]
        ),
    )
    weak_robustness = RobustnessResult(
        train_test=pd.DataFrame(),
        walk_forward=pd.DataFrame(),
        regimes=pd.DataFrame(),
        diagnostics=pd.DataFrame(
            [
                {"symbol": "SPY", "strategy": "sma_cross_50_200", "flags": "underperforms_benchmark"},
            ]
        ),
    )
    robust_stress = StressTestResult(
        request=StressTestRequest(
            symbol="SPY",
            strategy_key="sma_cross",
            strategy_parameters={"fast_window": 50, "slow_window": 200},
        ),
        scenarios=(),
        comparison=pd.DataFrame(),
        conclusion="Robusta",
        flags=(),
    )
    fragile_stress = StressTestResult(
        request=robust_stress.request,
        scenarios=(),
        comparison=pd.DataFrame(),
        conclusion="Fragil",
        flags=("Pocos trades: la evidencia sigue siendo fragil.",),
    )
    unreliable_stress = StressTestResult(
        request=robust_stress.request,
        scenarios=(),
        comparison=pd.DataFrame(),
        conclusion="No confiable",
        flags=("Muy pocos trades.",),
    )

    assert recommend_journal_status(robustness_result=None, stress_result=None) == "Needs Review"
    assert recommend_journal_status(robustness_result=robustness) == "Promising"
    assert recommend_journal_status(robustness_result=robustness, stress_result=robust_stress) == "Robustness Passed"
    assert recommend_journal_status(robustness_result=robustness, stress_result=fragile_stress) == "Needs Review"
    assert recommend_journal_status(robustness_result=weak_robustness, stress_result=fragile_stress) == "Rejected"
    assert recommend_journal_status(robustness_result=robustness, stress_result=unreliable_stress) == "Rejected"


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


def test_ui_journal_adapter_saves_notes_and_enriches_experiment_records():
    root = _workspace_tmp("ui_journal")
    data_dir = root / "data"
    experiments_dir = root / "experiments"
    save_ohlcv(_frame([100, 101, 102, 103, 104, 105, 106, 107]), data_dir / "SPY_1D.csv")
    run_backtest_request(
        BacktestRequest(
            symbol="SPY",
            strategy_key="sma_cross",
            strategy_parameters={"fast_window": 3, "slow_window": 5},
            data_dir=data_dir,
            interval="1d",
            commission_bps=0,
            slippage_bps=0,
            experiment_name="journal_test",
            experiments_root=experiments_dir,
        )
    )
    record = list_experiments(experiments_dir)[0]

    assert load_research_notes(record.path).status == DEFAULT_RESEARCH_STATUS
    assert parse_tags("trend, SPY; trend, revisar") == ("trend", "spy", "revisar")
    assert tags_to_text(("trend", "spy")) == "trend, spy"

    notes_path = save_research_notes(
        record.path,
        ResearchNotes(
            status="Promising",
            hypothesis="Cruce captura tendencias largas.",
            conclusion="Necesita robustez multi-activo.",
            next_test="Correr walk-forward.",
            tags=("trend", "spy", "trend"),
            favorite=True,
        ),
    )
    updated = list_experiments(experiments_dir)[0]
    loaded = load_research_notes(record.path)

    assert notes_path.name == RESEARCH_NOTES_FILENAME
    assert loaded.status == "Promising"
    assert loaded.tags == ("trend", "spy")
    assert loaded.favorite is True
    assert loaded.updated_at_utc
    assert updated.status == "Promising"
    assert updated.favorite is True
    assert updated.tags == ("trend", "spy")


def test_ui_journal_adapter_normalizes_unknown_status_and_tags():
    experiment_dir = _workspace_tmp("ui_journal_normalize")
    notes_path = experiment_dir / RESEARCH_NOTES_FILENAME
    notes_path.write_text(
        """
{
  "status": "Definitely Not A Status",
  "hypothesis": "  revisar  ",
  "tags": ["Trend", "trend", "  RSI  ", ""],
  "favorite": true
}
""".strip(),
        encoding="utf-8",
    )

    notes = load_research_notes(experiment_dir)
    saved_path = save_research_notes(
        experiment_dir,
        ResearchNotes(status="Bad Status", hypothesis="  h  ", tags=("A", "a", "B")),
    )
    saved = load_research_notes(experiment_dir)

    assert notes.status == DEFAULT_RESEARCH_STATUS
    assert notes.tags == ("trend", "rsi")
    assert notes.favorite is True
    assert saved_path == notes_path
    assert saved.status == DEFAULT_RESEARCH_STATUS
    assert saved.hypothesis == "h"
    assert saved.tags == ("a", "b")
    assert DEFAULT_RESEARCH_STATUS in RESEARCH_NOTE_STATUSES


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


def test_research_verdict_flags_weak_evidence():
    equity = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=30, freq="D"),
            "equity": [10_000 + index for index in range(30)],
        }
    )
    result = BacktestResult(
        equity_curve=equity,
        trades=pd.DataFrame(),
        orders=pd.DataFrame(),
        metrics={
            "number_of_trades": 2,
            "max_drawdown": -0.35,
            "sharpe_ratio": 1.2,
            "excess_return_vs_benchmark": -0.05,
        },
        config=BacktestConfig(),
    )

    verdict = build_research_verdict_from_result(
        result,
        parameter_count=5,
        symbol_count=1,
    )

    assert verdict.reliability == "Baja"
    assert verdict.benchmark_status == "Pierde contra benchmark"
    assert any("Pocos trades" in flag for flag in verdict.flags)
    assert any("Drawdown peligroso" in flag for flag in verdict.flags)
    assert any("sobreoptimizacion" in flag for flag in verdict.flags)
    assert "Ampliar el periodo" in verdict.next_action


def test_evidence_score_penalizes_missing_robustness_and_uses_matching_diagnostics():
    equity = pd.DataFrame(
        {
            "date": pd.date_range("2020-01-01", periods=800, freq="D"),
            "equity": [10_000 + index for index in range(800)],
        }
    )
    result = BacktestResult(
        equity_curve=equity,
        trades=pd.DataFrame(),
        orders=pd.DataFrame(),
        metrics={
            "number_of_trades": 12,
            "max_drawdown": -0.12,
            "sharpe_ratio": 0.9,
            "excess_return_vs_benchmark": 0.03,
        },
        config=BacktestConfig(commission_bps=1, slippage_bps=2),
    )
    robustness = RobustnessResult(
        train_test=pd.DataFrame(),
        walk_forward=pd.DataFrame(),
        regimes=pd.DataFrame(),
        diagnostics=pd.DataFrame(
            [
                {
                    "symbol": "SPY",
                    "strategy": "sma_cross_50_200",
                    "test_vs_buy_and_hold_return": 0.04,
                    "abs_train_test_return_gap": 0.08,
                    "test_number_of_trades": 7,
                    "walk_forward_windows": 3,
                    "walk_forward_positive_rate": 0.67,
                    "walk_forward_avg_vs_buy_and_hold": 0.01,
                },
                {
                    "symbol": "QQQ",
                    "strategy": "sma_cross_50_200",
                    "test_vs_buy_and_hold_return": 0.01,
                    "abs_train_test_return_gap": 0.10,
                    "test_number_of_trades": 6,
                    "walk_forward_windows": 3,
                    "walk_forward_positive_rate": 0.60,
                    "walk_forward_avg_vs_buy_and_hold": 0.005,
                },
            ]
        ),
    )

    base_score = build_evidence_score_from_result(
        result,
        parameter_count=2,
        symbol_count=1,
        strategy_key="sma_cross",
        symbol="SPY",
    )
    robust_score = build_evidence_score_from_result(
        result,
        parameter_count=2,
        symbol_count=1,
        strategy_key="sma_cross",
        symbol="SPY",
        robustness_result=robustness,
    )
    fragile_stress = StressTestResult(
        request=StressTestRequest(
            symbol="SPY",
            strategy_key="sma_cross",
            strategy_parameters={"fast_window": 50, "slow_window": 200},
        ),
        scenarios=(),
        comparison=pd.DataFrame(
            [
                {"scenario": "Base", "delta_return_vs_base": 0.0},
                {"scenario": "Comision x2", "delta_return_vs_base": -0.35},
            ]
        ),
        conclusion="Fragil",
        flags=("El retorno cae demasiado frente al escenario base.",),
    )
    stressed_score = build_evidence_score_from_result(
        result,
        parameter_count=2,
        symbol_count=1,
        strategy_key="sma_cross",
        symbol="SPY",
        robustness_result=robustness,
        stress_result=fragile_stress,
    )
    frame = components_frame(robust_score)
    stressed_frame = components_frame(stressed_score)

    assert robust_score.score > base_score.score
    assert stressed_score.score < robust_score.score
    assert sum(component.weight for component in robust_score.components) == 100
    assert frame["componente"].tolist()[0] == "Cantidad de trades"
    assert frame.loc[frame["componente"] == "Out-of-sample", "estado"].iloc[0] == "bien"
    assert frame.loc[frame["componente"] == "Validacion multi-activo", "estado"].iloc[0] == "aceptable"
    assert frame.loc[frame["componente"] == "Stress tests", "estado"].iloc[0] == "no corrido"
    assert stressed_frame.loc[stressed_frame["componente"] == "Stress tests", "estado"].iloc[0] == "fragil"


def test_evidence_score_handles_missing_data_and_penalizes_weak_setup():
    result = BacktestResult(
        equity_curve=pd.DataFrame(),
        trades=pd.DataFrame(),
        orders=pd.DataFrame(),
        metrics={
            "number_of_trades": 0,
            "max_drawdown": -0.65,
            "excess_return_vs_benchmark": -0.20,
        },
        config=BacktestConfig(commission_bps=0, slippage_bps=0),
    )

    score = build_evidence_score_from_result(
        result,
        parameter_count=7,
        symbol_count=1,
        strategy_key="rsi",
        symbol="SPY",
    )
    frame = components_frame(score)

    assert score.score < 30
    assert frame.loc[frame["componente"] == "Cantidad de trades", "estado"].iloc[0] == "sin evidencia"
    assert frame.loc[frame["componente"] == "Drawdown", "estado"].iloc[0] == "muy alto"
    assert frame.loc[frame["componente"] == "Cantidad de parametros", "estado"].iloc[0] == "sobreajuste probable"


def test_research_adapter_persists_associated_validation_and_builds_summary():
    root = _workspace_tmp("research_summary")
    data_dir = root / "data"
    experiments_dir = root / "experiments"
    save_ohlcv(_frame(list(range(100, 380))), data_dir / "SPY_1D.csv")
    artifacts = run_backtest_request(
        BacktestRequest(
            symbol="SPY",
            strategy_key="sma_cross",
            strategy_parameters={"fast_window": 3, "slow_window": 5},
            data_dir=data_dir,
            interval="1d",
            commission_bps=1,
            slippage_bps=2,
            experiment_name="research_integration",
            experiments_root=experiments_dir,
        )
    )
    record = list_experiments(experiments_dir)[0]
    save_research_notes(
        record.path,
        ResearchNotes(
            status="Promising",
            hypothesis="Cruce corto captura tramo tendencial.",
            conclusion="Sirve para seguir validando, no para operar.",
            next_test="Stress test y multi-activo.",
            tags=("trend", "spy"),
            favorite=True,
        ),
    )
    robustness = RobustnessResult(
        train_test=pd.DataFrame([{"symbol": "SPY", "strategy": "sma_cross_3_5"}]),
        walk_forward=pd.DataFrame([{"symbol": "SPY", "strategy": "sma_cross_3_5"}]),
        regimes=pd.DataFrame(),
        diagnostics=pd.DataFrame(
            [
                {"symbol": "SPY", "strategy": "buy_and_hold", "flags": ""},
                {
                    "symbol": "SPY",
                    "strategy": "sma_cross_3_5",
                    "flags": "",
                    "robustness_score": 82.0,
                    "test_vs_buy_and_hold_return": 0.04,
                    "abs_train_test_return_gap": 0.05,
                    "test_number_of_trades": 8,
                    "walk_forward_windows": 3,
                    "walk_forward_positive_rate": 0.67,
                    "walk_forward_avg_vs_buy_and_hold": 0.01,
                },
            ]
        ),
    )
    robustness_request = RobustnessRequest(
        symbols=("SPY",),
        strategy_key="sma_cross",
        strategy_parameters={"fast_window": 3, "slow_window": 5},
        data_dir=data_dir,
        interval="1d",
    )
    stress = StressTestResult(
        request=StressTestRequest(
            symbol="SPY",
            strategy_key="sma_cross",
            strategy_parameters={"fast_window": 3, "slow_window": 5},
            data_dir=data_dir,
            interval="1d",
        ),
        scenarios=(),
        comparison=pd.DataFrame(
            [
                {"scenario": "Base", "total_return": 0.20, "delta_return_vs_base": 0.0, "number_of_trades": 12},
                {"scenario": "Comision x2", "total_return": 0.18, "delta_return_vs_base": -0.02, "number_of_trades": 12},
            ]
        ),
        conclusion="Robusta",
        flags=("Sin quiebres obvios en estos stresses. No implica aptitud para operar real.",),
    )

    save_robustness_for_experiment(record.path, robustness_request, robustness)
    save_stress_for_experiment(record.path, stress)
    summary = build_research_summary(record.path)
    frame = research_records_frame([record])

    assert artifacts.experiment_dir == record.path
    assert load_robustness_for_experiment(record.path) is not None
    assert load_stress_for_experiment(record.path) is not None
    assert summary.has_robustness is True
    assert summary.has_stress is True
    assert summary.journal_state == "Promising"
    assert summary.journal_favorite is True
    assert summary.stress_summary["conclusion"] == "Robusta"
    assert "evidence_score" in frame.columns
    assert bool(frame.loc[0, "has_robustness"]) is True
    assert bool(frame.loc[0, "has_stress"]) is True


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


def test_ui_stress_adapter_runs_base_and_adverse_scenarios():
    root = _workspace_tmp("ui_stress")
    data_dir = root / "data"
    save_ohlcv(_frame(list(range(100, 140))), data_dir / "SPY_1D.csv")

    result = run_stress_test_request(
        StressTestRequest(
            symbol="SPY",
            strategy_key="sma_cross",
            strategy_parameters={"fast_window": 3, "slow_window": 5},
            data_dir=data_dir,
            interval="1d",
            commission_bps=1,
            slippage_bps=2,
            remove_best_trades=1,
        )
    )
    curves = equity_curves_frame(result.scenarios)

    assert result.conclusion in {"Robusta", "Fragil", "No confiable"}
    assert result.comparison["scenario"].tolist() == [
        "Base",
        "Comision x2",
        "Slippage x2",
        "Ejecucion +1 barra",
        "Sin mejores 1 trades",
        "Sin mejor mes",
    ]
    assert "delta_return_vs_base" in result.comparison.columns
    assert not curves.empty
    assert "Base" in curves.columns
    assert result.comparison.loc[0, "method"] == "backtest"
    assert "post-hoc" in result.comparison["method"].tolist()


def test_stress_conclusion_classifies_fragile_and_unreliable_cases():
    fragile = pd.DataFrame(
        [
            {"total_return": 0.40, "number_of_trades": 12, "max_drawdown": -0.20, "delta_return_vs_base": 0.0},
            {"total_return": 0.05, "number_of_trades": 12, "max_drawdown": -0.22, "delta_return_vs_base": -0.35},
        ]
    )
    unreliable = pd.DataFrame(
        [
            {"total_return": 0.20, "number_of_trades": 3, "max_drawdown": -0.10, "delta_return_vs_base": 0.0},
            {"total_return": 0.18, "number_of_trades": 3, "max_drawdown": -0.11, "delta_return_vs_base": -0.02},
        ]
    )
    robust = pd.DataFrame(
        [
            {"total_return": 0.20, "number_of_trades": 20, "max_drawdown": -0.15, "delta_return_vs_base": 0.0},
            {"total_return": 0.14, "number_of_trades": 20, "max_drawdown": -0.16, "delta_return_vs_base": -0.06},
        ]
    )

    fragile_label, fragile_flags = stress_conclusion(fragile)
    unreliable_label, unreliable_flags = stress_conclusion(unreliable)
    robust_label, robust_flags = stress_conclusion(robust)

    assert fragile_label == "Fragil"
    assert any("retorno cae" in flag for flag in fragile_flags)
    assert unreliable_label == "No confiable"
    assert any("Muy pocos trades" in flag for flag in unreliable_flags)
    assert robust_label == "Robusta"
    assert robust_flags == ["Sin quiebres obvios en estos stresses. No implica aptitud para operar real."]


def test_ui_stress_adapter_handles_empty_trades():
    root = _workspace_tmp("ui_stress_empty_trades")
    data_dir = root / "data"
    save_ohlcv(_frame([100] * 40), data_dir / "SPY_1D.csv")

    result = run_stress_test_request(
        StressTestRequest(
            symbol="SPY",
            strategy_key="breakout",
            strategy_parameters={"entry_window": 20, "exit_window": 10},
            data_dir=data_dir,
            interval="1d",
            remove_best_trades=3,
        )
    )

    assert result.comparison["number_of_trades"].iloc[0] == 0
    assert "Sin mejores trades" in result.comparison["scenario"].tolist()
    assert result.conclusion == "No confiable"


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
