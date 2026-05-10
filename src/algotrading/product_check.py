from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from pathlib import Path
import shutil
import tempfile
from typing import Any

import pandas as pd

from algotrading.data.market_calendar import US_EQUITY_CALENDAR, expected_trading_dates
from algotrading.data.storage import build_data_path, save_ohlcv
from algotrading.ui.adapters.backtest_adapter import (
    BacktestRequest,
    preflight_backtest_request,
    run_backtest_request,
)
from algotrading.ui.adapters.data_adapter import (
    list_data_assets,
    load_symbol_data,
    validate_data_quality,
)
from algotrading.ui.adapters.data_quality_adapter import (
    build_advanced_data_quality_report,
)
from algotrading.ui.adapters.experiment_adapter import (
    filter_records,
    list_experiments,
)
from algotrading.ui.adapters.journal_adapter import (
    ResearchNotes,
    load_research_notes,
    save_research_notes,
)
from algotrading.ui.adapters.reports_adapter import generate_professional_research_report
from algotrading.ui.adapters.research_adapter import (
    build_research_summary,
    compare_experiment_fairness,
    save_robustness_for_experiment,
    save_stress_for_experiment,
)
from algotrading.ui.adapters.risk_adapter import RiskSettings
from algotrading.ui.adapters.robustness_adapter import RobustnessRequest, run_robustness_request
from algotrading.ui.adapters.stress_adapter import StressTestRequest, run_stress_test_request


@dataclass(frozen=True)
class ProductCheckStep:
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class ProductCheckResult:
    passed: bool
    report_path: Path
    workspace: Path
    data_dir: Path
    experiments_dir: Path
    steps: tuple[ProductCheckStep, ...]
    artifacts: dict[str, Path] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()


@dataclass
class _ProductCheckContext:
    workspace: Path
    data_dir: Path
    experiments_dir: Path
    report_path: Path
    steps: list[ProductCheckStep] = field(default_factory=list)
    artifacts: dict[str, Path] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def run_product_check(
    *,
    workspace: Path | str | None = None,
    report_path: Path | str = "reports/product_validation_report.md",
    keep_workspace: bool = True,
) -> ProductCheckResult:
    """Valida el flujo principal del producto sin depender de internet ni Streamlit abierto."""
    owns_workspace = workspace is None
    if workspace is None:
        workspace_path = Path(tempfile.mkdtemp(prefix="algotrading_product_check_"))
    else:
        workspace_path = Path(workspace)
        workspace_path.mkdir(parents=True, exist_ok=True)

    context = _ProductCheckContext(
        workspace=workspace_path,
        data_dir=workspace_path / "data",
        experiments_dir=workspace_path / "experiments",
        report_path=Path(report_path),
    )

    try:
        _run_checks(context)
    except Exception as exc:
        context.steps.append(ProductCheckStep("Fallo no controlado", False, str(exc)))

    passed = all(step.passed for step in context.steps)
    result = ProductCheckResult(
        passed=passed,
        report_path=context.report_path,
        workspace=context.workspace,
        data_dir=context.data_dir,
        experiments_dir=context.experiments_dir,
        steps=tuple(context.steps),
        artifacts=dict(context.artifacts),
        warnings=tuple(context.warnings),
    )
    _write_product_report(result)

    if owns_workspace and not keep_workspace:
        shutil.rmtree(workspace_path, ignore_errors=True)
    return result


def _run_checks(context: _ProductCheckContext) -> None:
    _check_clean_state(context)
    _create_fixture_data(context)
    _check_data_manager_flow(context)
    primary_experiment = _check_guided_and_backtest_flow(context, symbol="SPY", name="product_check_spy")
    comparison_experiment = _check_guided_and_backtest_flow(
        context,
        symbol="QQQ",
        name="product_check_qqq",
        save_artifact_prefix="comparison",
    )
    _check_results_dashboard_flow(context, primary_experiment)
    _check_robustness_flow(context, primary_experiment)
    _check_stress_flow(context, primary_experiment)
    _check_journal_flow(context, primary_experiment)
    _check_experiment_explorer_flow(context, primary_experiment, comparison_experiment)


def _check_clean_state(context: _ProductCheckContext) -> None:
    context.data_dir.mkdir(parents=True, exist_ok=True)
    context.experiments_dir.mkdir(parents=True, exist_ok=True)
    data_assets = list_data_assets(context.data_dir)
    experiments = list_experiments(context.experiments_dir)
    _record(
        context,
        "Primer uso: estado limpio",
        not data_assets and not experiments,
        f"datos={len(data_assets)}, experimentos={len(experiments)}",
    )


def _create_fixture_data(context: _ProductCheckContext) -> None:
    spy = _fixture_ohlcv("SPY", base=100.0, amplitude=7.0)
    qqq = _fixture_ohlcv("QQQ", base=75.0, amplitude=9.5)
    spy_path = save_ohlcv(spy, build_data_path(context.data_dir, "SPY", "1d", "csv"))
    qqq_path = save_ohlcv(qqq, build_data_path(context.data_dir, "QQQ", "1d", "csv"))
    context.artifacts["fixture_spy"] = spy_path
    context.artifacts["fixture_qqq"] = qqq_path
    _record(
        context,
        "Fixtures deterministicas",
        spy_path.exists() and qqq_path.exists() and len(spy) > 700 and len(qqq) > 700,
        f"SPY={len(spy)} filas, QQQ={len(qqq)} filas",
    )


def _check_data_manager_flow(context: _ProductCheckContext) -> None:
    assets = list_data_assets(context.data_dir, interval="1d")
    symbols = {asset.symbol_hint for asset in assets}
    _record(
        context,
        "Data Manager: datos locales detectados",
        symbols == {"SPY", "QQQ"},
        f"activos={sorted(symbols)}",
    )

    frame, path = load_symbol_data(context.data_dir, "SPY", "1d")
    basic = validate_data_quality(frame)
    advanced = build_advanced_data_quality_report(frame, symbol="SPY", interval="1d")
    _record(
        context,
        "Data Manager: validacion OHLCV y Data Quality",
        basic.is_valid and advanced.score >= 90 and path.exists(),
        f"basic={basic.message}, score={advanced.score:.0f}/100, severity={advanced.severity}",
    )

    bad_frame = frame.head(10).copy()
    bad_frame.loc[1, "date"] = bad_frame.loc[0, "date"]
    bad_frame.loc[2, "high"] = bad_frame.loc[2, "low"] - 1
    bad_report = build_advanced_data_quality_report(bad_frame, symbol="SPY", interval="1d")
    _record(
        context,
        "Data Manager: issues controlados detectados",
        bad_report.score < advanced.score and any(issue.check == "fechas duplicadas" for issue in bad_report.issues),
        f"score_malo={bad_report.score:.0f}/100, issues={len(bad_report.issues)}",
    )


def _check_guided_and_backtest_flow(
    context: _ProductCheckContext,
    *,
    symbol: str,
    name: str,
    save_artifact_prefix: str = "primary",
) -> Path:
    invalid_request = BacktestRequest(
        symbol=symbol,
        strategy_key="buy_and_hold",
        strategy_parameters={},
        data_dir=context.data_dir,
        interval="1d",
        start="2024-01-02",
        end="2024-01-10",
        save_experiment=False,
    )
    invalid_preflight = preflight_backtest_request(invalid_request)
    _record(
        context,
        f"Guided Workflow: preflight invalido bloquea {symbol}",
        not invalid_preflight.can_run and bool(invalid_preflight.errors),
        "; ".join(invalid_preflight.errors[:2]),
    )

    request = BacktestRequest(
        symbol=symbol,
        strategy_key="sma_cross",
        strategy_parameters={"fast_window": 20, "slow_window": 60},
        data_dir=context.data_dir,
        interval="1d",
        price_column="adj_close",
        initial_capital=10_000,
        commission_bps=1,
        slippage_bps=2,
        risk=RiskSettings(position_fraction=0.8, max_total_exposure=0.9),
        experiment_name=name,
        notes="Product check offline.",
        research_preset="benchmark_comparison",
        save_experiment=True,
        experiments_root=context.experiments_dir,
    )
    preflight = preflight_backtest_request(request)
    _record(
        context,
        f"Guided Workflow: preflight valido {symbol}",
        preflight.can_run and preflight.entries > 0,
        f"filas={preflight.rows}, entradas={preflight.entries}, warnings={len(preflight.warnings)}",
    )
    if not preflight.can_run:
        raise RuntimeError(f"Preflight valido esperado para {symbol}; errores={preflight.errors}")

    artifacts = run_backtest_request(request)
    experiment_dir = artifacts.experiment_dir
    if experiment_dir is None:
        raise RuntimeError("El backtest no devolvio carpeta de experimento.")
    report_path = generate_professional_research_report(experiment_dir)
    context.artifacts[f"{save_artifact_prefix}_experiment"] = experiment_dir
    context.artifacts[f"{save_artifact_prefix}_html_report"] = report_path

    expected_files = _expected_experiment_files(experiment_dir, symbol)
    missing = [str(path.relative_to(experiment_dir)) for path in expected_files if not path.exists()]
    _record(
        context,
        f"Backtest Runner: experimento guardado {symbol}",
        not missing and artifacts.result.metrics["number_of_trades"] > 0,
        f"trades={artifacts.result.metrics['number_of_trades']}, faltantes={missing or 'ninguno'}",
    )
    return experiment_dir


def _check_results_dashboard_flow(context: _ProductCheckContext, experiment_dir: Path) -> None:
    summary = build_research_summary(experiment_dir)
    checks = [
        summary.verdict.reliability,
        summary.evidence_score.score > 0,
        summary.data_quality is not None,
        summary.pipeline_state == "Backtest creado",
        bool(summary.recommended_next_action),
    ]
    _record(
        context,
        "Results Dashboard: Research Summary inicial",
        all(checks),
        (
            f"verdict={summary.verdict.reliability}, "
            f"evidence={summary.evidence_score.score:.0f}/100, "
            f"pipeline={summary.pipeline_state}, "
            f"data_quality={summary.data_quality.score if summary.data_quality else 'n/a'}"
        ),
    )


def _check_robustness_flow(context: _ProductCheckContext, experiment_dir: Path) -> None:
    request = RobustnessRequest(
        symbols=("SPY", "QQQ"),
        strategy_key="sma_cross",
        strategy_parameters={"fast_window": 20, "slow_window": 60},
        data_dir=context.data_dir,
        interval="1d",
        price_column="adj_close",
        initial_capital=10_000,
        commission_bps=1,
        slippage_bps=2,
        train_ratio=0.7,
        run_walk_forward=True,
        run_regime_analysis=True,
        wf_train_rows=300,
        wf_test_rows=120,
        wf_step_rows=120,
        regime_min_rows=80,
    )
    result = run_robustness_request(request)
    save_robustness_for_experiment(experiment_dir, request, result)
    summary = build_research_summary(experiment_dir)
    _record(
        context,
        "Robustness Lab: resultado asociado",
        summary.has_robustness and not result.diagnostics.empty,
        f"diagnostics={len(result.diagnostics)}, evidence={summary.evidence_score.score:.0f}/100",
    )


def _check_stress_flow(context: _ProductCheckContext, experiment_dir: Path) -> None:
    request = StressTestRequest(
        symbol="SPY",
        strategy_key="sma_cross",
        strategy_parameters={"fast_window": 20, "slow_window": 60},
        data_dir=context.data_dir,
        interval="1d",
        price_column="adj_close",
        initial_capital=10_000,
        commission_bps=1,
        slippage_bps=2,
        remove_best_trades=1,
    )
    result = run_stress_test_request(request)
    save_stress_for_experiment(experiment_dir, result)
    summary = build_research_summary(experiment_dir)
    _record(
        context,
        "Stress Tests: resultado asociado",
        summary.has_stress and result.conclusion in {"Robusta", "Fragil", "No confiable"},
        f"conclusion={result.conclusion}, escenarios={len(result.comparison)}, evidence={summary.evidence_score.score:.0f}/100",
    )


def _check_journal_flow(context: _ProductCheckContext, experiment_dir: Path) -> None:
    notes = ResearchNotes(
        status="Promising",
        hypothesis="El cruce SMA podria capturar tramos tendenciales amplios.",
        conclusion="Sirve para seguir investigando, no para operar.",
        next_test="Revisar sensibilidad de ventanas y costos mas altos.",
        tags=("product-check", "sma", "offline"),
        favorite=True,
    )
    save_research_notes(experiment_dir, notes)
    before = load_research_notes(experiment_dir)
    summary = build_research_summary(experiment_dir)
    after = load_research_notes(experiment_dir)
    _record(
        context,
        "Experiment Journal: notas manuales persistentes",
        (
            before.hypothesis == after.hypothesis
            and before.conclusion == after.conclusion
            and after.favorite
            and summary.journal_state == "Promising"
            and "product-check" in after.tags
        ),
        f"estado={after.status}, tags={after.tags}, favorito={after.favorite}",
    )


def _check_experiment_explorer_flow(
    context: _ProductCheckContext,
    primary_experiment: Path,
    comparison_experiment: Path,
) -> None:
    records = list_experiments(context.experiments_dir)
    by_strategy = filter_records(records, strategy="sma")
    by_symbol = filter_records(records, symbol="SPY")
    by_status = filter_records(records, status="Promising")
    favorites = filter_records(records, favorites_only=True)
    fairness = compare_experiment_fairness(records)
    _record(
        context,
        "Experiment Explorer: listado, filtros y fairness",
        (
            len(records) >= 2
            and any(record.path == primary_experiment for record in records)
            and any(record.path == comparison_experiment for record in records)
            and by_strategy
            and by_symbol
            and by_status
            and favorites
            and fairness
        ),
        (
            f"records={len(records)}, strategy={len(by_strategy)}, symbol={len(by_symbol)}, "
            f"status={len(by_status)}, favorites={len(favorites)}, fairness={len(fairness)}"
        ),
    )


def _fixture_ohlcv(symbol: str, *, base: float, amplitude: float) -> pd.DataFrame:
    dates = expected_trading_dates("2020-01-02", "2024-12-31", calendar_key=US_EQUITY_CALENDAR)
    index = pd.RangeIndex(len(dates))
    slow_wave = pd.Series(index).map(lambda value: amplitude * math.sin(value / 35))
    fast_wave = pd.Series(index).map(lambda value: amplitude * 0.35 * math.sin(value / 9))
    trend = pd.Series(index).astype(float) * 0.035
    close = base + trend + slow_wave + fast_wave
    close = close.clip(lower=1.0)
    open_ = close.shift(1).fillna(close.iloc[0]) * 0.998
    high = pd.concat([open_, close], axis=1).max(axis=1) * 1.006
    low = pd.concat([open_, close], axis=1).min(axis=1) * 0.994
    volume = 1_000_000 + (pd.Series(index) % 31) * 5_000
    return pd.DataFrame(
        {
            "date": dates,
            "open": open_.round(4),
            "high": high.round(4),
            "low": low.round(4),
            "close": close.round(4),
            "adj_close": close.round(4),
            "volume": volume.astype(int),
        }
    )


def _expected_experiment_files(experiment_dir: Path, symbol: str) -> list[Path]:
    symbol_dir = experiment_dir / symbol
    return [
        experiment_dir / "config.json",
        experiment_dir / "metadata.json",
        experiment_dir / "experiment_metadata.json",
        experiment_dir / "summary.csv",
        experiment_dir / "data_quality.json",
        experiment_dir / "research_report.html",
        symbol_dir / "equity.csv",
        symbol_dir / "orders.csv",
        symbol_dir / "trades.csv",
        symbol_dir / "metrics.json",
        symbol_dir / "equity_drawdown.html",
    ]


def _record(context: _ProductCheckContext, name: str, passed: bool, detail: str) -> None:
    context.steps.append(ProductCheckStep(name=name, passed=bool(passed), detail=detail))
    if not passed:
        raise AssertionError(f"{name}: {detail}")


def _write_product_report(result: ProductCheckResult) -> None:
    result.report_path.parent.mkdir(parents=True, exist_ok=True)
    status = "PASS" if result.passed else "FAIL"
    lines = [
        "# Product Validation Report",
        "",
        f"- Fecha UTC: {datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"- Estado: **{status}**",
        f"- Workspace temporal: `{result.workspace}`",
        f"- Data dir: `{result.data_dir}`",
        f"- Experiments dir: `{result.experiments_dir}`",
        "",
        "## Checks",
        "",
    ]
    for step in result.steps:
        mark = "PASS" if step.passed else "FAIL"
        lines.append(f"- **{mark}** - {step.name}: {step.detail}")
    lines.extend(["", "## Artefactos", ""])
    for label, path in sorted(result.artifacts.items()):
        lines.append(f"- `{label}`: `{path}`")
    lines.extend(["", "## Advertencias", ""])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- Sin advertencias adicionales del product check.")
    lines.extend(
        [
            "",
            "## Pendientes siguientes",
            "",
            "- UX Polish & Consistency: empty states, badges, headers y mensajes comunes.",
            "- Backtest Correctness Audit: golden tests manuales y reporte de supuestos.",
            "- Smoke visual opcional con snapshots Streamlit/Playwright.",
            "",
        ]
    )
    result.report_path.write_text("\n".join(lines), encoding="utf-8")
