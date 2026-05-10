from pathlib import Path
import json
from uuid import uuid4

import pandas as pd

from algotrading.data.storage import save_ohlcv
from algotrading.data import market_calendar as market_calendar_module
from algotrading.data.market_calendar import CalendarSchedule, US_EQUITY_CALENDAR, expected_trading_dates
from algotrading.ui.adapters.backtest_adapter import BacktestRequest, run_backtest_request
from algotrading.ui.adapters.data_quality_adapter import (
    advanced_quality_frame,
    build_advanced_data_quality_report,
    diagnose_asset_mix,
)
from algotrading.ui.adapters.experiment_adapter import list_experiments
from algotrading.ui.adapters.paper_adapter import (
    PaperTradingRequest,
    build_paper_replay_frame,
    run_paper_trading_request,
)
from algotrading.ui.adapters.preset_adapter import (
    get_research_preset,
    list_research_presets,
    preset_frame,
)
from algotrading.ui.adapters.reports_adapter import (
    collect_experiment_report_files,
    generate_professional_research_pdf,
    generate_professional_research_report,
)
from algotrading.ui.adapters.research_adapter import build_research_summary


def _workspace_tmp(name: str) -> Path:
    path = Path("tests/.tmp") / f"{name}_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _frame(prices: list[float]) -> pd.DataFrame:
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


def _dated_frame(dates: list[str], prices: list[float] | None = None) -> pd.DataFrame:
    values = prices or [100 + index for index in range(len(dates))]
    frame = _frame(values)
    frame["date"] = pd.to_datetime(dates)
    return frame


def test_research_presets_are_complete_and_have_fallback():
    presets = list_research_presets()
    keys = {preset.key for preset in presets}

    assert keys == {
        "sanity_check",
        "benchmark_comparison",
        "robustness_validation",
        "stress_test_only",
        "paper_candidate_review",
        "strategy_rejection_review",
    }
    assert get_research_preset("missing").key == "sanity_check"
    assert preset_frame("benchmark_comparison")["campo"].tolist()[0] == "Descripcion"
    assert all(preset.required_checks for preset in presets)
    assert all(preset.important_metrics for preset in presets)


def test_advanced_data_quality_flags_common_data_problems():
    frame = _frame([100, 101, 250, 102, 103])
    frame.loc[1, "date"] = frame.loc[0, "date"]
    frame.loc[2, "high"] = 90
    frame.loc[3, "volume"] = 0

    report = build_advanced_data_quality_report(frame, symbol="SPY", interval="1d")
    checks = set(advanced_quality_frame(report)["check"])

    assert report.score < 100
    assert report.severity == "critical"
    assert "fechas duplicadas" in checks
    assert "OHLC inconsistente" in checks
    assert "volumen sospechoso" in checks
    assert diagnose_asset_mix(("SPY", "BTC-USD")) is not None


def test_us_equity_calendar_ignores_weekends_and_holidays_but_flags_missing_trading_days():
    expected = expected_trading_dates("2024-03-28", "2024-04-01", calendar_key=US_EQUITY_CALENDAR)
    assert "2024-03-29" not in [item.strftime("%Y-%m-%d") for item in expected]  # Good Friday

    clean_report = build_advanced_data_quality_report(
        _dated_frame(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05", "2024-01-08"]),
        symbol="SPY",
        interval="1d",
    )
    missing_report = build_advanced_data_quality_report(
        _dated_frame(["2024-01-02", "2024-01-04", "2024-01-05", "2024-01-08"]),
        symbol="SPY",
        interval="1d",
    )

    assert clean_report.calendar == "us_equities"
    assert clean_report.calendar_provider
    assert clean_report.calendar_precision
    assert clean_report.severity == "ok"
    assert not any(issue.severity == "warning" and issue.check == "calendario" for issue in clean_report.issues)
    assert any("2024-01-03" in issue.message for issue in missing_report.issues if issue.check == "calendario")


def test_crypto_calendar_expects_weekends():
    report = build_advanced_data_quality_report(
        _dated_frame(["2024-01-05", "2024-01-08"]),
        symbol="BTC-USD",
        interval="1d",
    )

    assert report.calendar == "crypto_24_7"
    assert any("2024-01-06" in issue.message for issue in report.issues if issue.check == "calendario")


def test_calendar_provider_prioritizes_precise_source_when_available(monkeypatch):
    def fake_precise_provider(start_ts, end_ts, calendar_key):
        return CalendarSchedule(
            calendar_key=calendar_key,
            provider="fake-precise:NYSE",
            precision="exchange_calendar",
            dates=pd.DatetimeIndex([pd.Timestamp("2024-01-02")]),
            early_closes=("2024-01-03",),
            note="Calendario preciso fake.",
        )

    monkeypatch.setattr(market_calendar_module, "_precise_market_calendar_schedule", fake_precise_provider)

    schedule = market_calendar_module.expected_market_schedule(
        "2024-01-02",
        "2024-01-03",
        calendar_key=US_EQUITY_CALENDAR,
    )
    diagnostic = market_calendar_module.diagnose_calendar_gaps(
        pd.Series(pd.to_datetime(["2024-01-02", "2024-01-03"])),
        asset_type="traditional",
        interval="1d",
        symbol="SPY",
    )

    assert schedule.provider == "fake-precise:NYSE"
    assert schedule.precision == "exchange_calendar"
    assert diagnostic.provider == "fake-precise:NYSE"
    assert diagnostic.early_closes == ("2024-01-03",)


def test_backtest_experiment_persists_research_preset_and_data_quality():
    root = _workspace_tmp("professional_backtest")
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
            commission_bps=1,
            slippage_bps=2,
            research_preset="benchmark_comparison",
            experiment_name="professional_test",
            experiments_root=experiments_dir,
        )
    )
    assert artifacts.experiment_dir is not None
    summary = build_research_summary(artifacts.experiment_dir)

    assert summary.research_preset.key == "benchmark_comparison"
    assert summary.data_quality is not None
    assert (artifacts.experiment_dir / "data_quality.json").exists()
    assert summary.experiment_metadata["research"]["preset"] == "benchmark_comparison"


def test_professional_html_report_is_generated_for_experiment():
    root = _workspace_tmp("professional_report")
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
            commission_bps=1,
            slippage_bps=2,
            experiment_name="html_report_test",
            experiments_root=experiments_dir,
        )
    )
    record = list_experiments(experiments_dir)[0]

    report_path = generate_professional_research_report(record.path)
    content = report_path.read_text(encoding="utf-8")

    assert report_path.name == "research_report.html"
    assert "Reporte de Research" in content
    assert "No es recomendacion de inversion" in content
    assert "Evidence Score" in content
    assert "Research preset" in content
    assert "Trades recientes" in content
    assert "Ficha reproducible" in content
    assert "Archivos generados" in content
    assert "Data Quality" in content


def test_professional_pdf_report_is_generated_for_experiment():
    root = _workspace_tmp("professional_pdf")
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
            commission_bps=1,
            slippage_bps=2,
            experiment_name="pdf_report_test",
            experiments_root=experiments_dir,
        )
    )
    record = list_experiments(experiments_dir)[0]

    report_path = generate_professional_research_pdf(record.path)
    files = collect_experiment_report_files(record.path)

    assert report_path.name == "research_report.pdf"
    assert report_path.read_bytes().startswith(b"%PDF-")
    assert any(item.label == "research_report.pdf" and item.mime == "application/pdf" for item in files)


def test_paper_replay_frame_handles_orders_and_empty_fills():
    root = _workspace_tmp("paper_replay")
    data_dir = root / "data"
    save_ohlcv(_frame([100, 101, 102, 103, 104, 105]), data_dir / "SPY_1D.csv")

    result = run_paper_trading_request(
        PaperTradingRequest(
            symbol="SPY",
            strategy_key="buy_and_hold",
            strategy_parameters={},
            data_dir=data_dir,
            interval="1d",
            dry_run=True,
        )
    )
    replay = build_paper_replay_frame(result)

    assert len(replay) == len(result.account_history)
    assert {"bar", "date", "next_target_weight", "order_status", "cash", "equity"}.issubset(replay.columns)
    assert replay["equity"].notna().all()


def test_examples_are_valid_json():
    for path in Path("examples").glob("*.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert payload
