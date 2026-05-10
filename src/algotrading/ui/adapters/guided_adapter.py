from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from algotrading.ui.adapters.backtest_adapter import BacktestRequest, BacktestRunArtifacts
from algotrading.ui.adapters.risk_adapter import RiskSettings
from algotrading.ui.adapters.robustness_adapter import RobustnessRequest, RobustnessResult
from algotrading.ui.adapters.stress_adapter import StressTestResult
from algotrading.ui.adapters.strategy_adapter import default_parameters


GUIDED_WORKFLOW_STEPS = (
    "Seleccionar/validar datos",
    "Elegir estrategia",
    "Configurar backtest",
    "Ejecutar",
    "Revisar resultados",
    "Correr robustez",
    "Guardar notas/conclusion",
)


@dataclass(frozen=True)
class ExperimentDraft:
    step: int = 1
    symbol: str | None = None
    interval: str = "1d"
    strategy_key: str = "sma_cross"
    strategy_parameters: dict[str, int | float] = field(default_factory=lambda: default_parameters("sma_cross"))
    research_preset: str = "sanity_check"
    start: str | None = None
    end: str | None = None
    price_column: str = "adj_close"
    initial_capital: float = 10_000.0
    commission_bps: float = 1.0
    slippage_bps: float = 2.0
    risk: RiskSettings = field(default_factory=RiskSettings)
    experiment_name: str = "guided_experiment"
    notes: str = ""
    hypothesis: str = ""
    conclusion: str = ""
    next_test: str = ""
    tags: tuple[str, ...] = ()
    favorite: bool = False
    journal_status: str = "Needs Review"
    backtest_request: BacktestRequest | None = None
    backtest_artifacts: BacktestRunArtifacts | None = None
    robustness_request: RobustnessRequest | None = None
    robustness_result: RobustnessResult | None = None
    journal_saved_path: Path | None = None


def new_experiment_draft(interval: str = "1d") -> ExperimentDraft:
    return ExperimentDraft(interval=interval)


def update_experiment_draft(draft: ExperimentDraft, **changes: Any) -> ExperimentDraft:
    if "step" in changes:
        changes["step"] = clamp_guided_step(int(changes["step"]))
    return replace(draft, **changes)


def clamp_guided_step(step: int) -> int:
    return max(1, min(len(GUIDED_WORKFLOW_STEPS), step))


def guided_step_label(step: int) -> str:
    step = clamp_guided_step(step)
    return f"{step}. {GUIDED_WORKFLOW_STEPS[step - 1]}"


def build_draft_backtest_request(
    draft: ExperimentDraft,
    *,
    data_dir: Path | str,
    experiments_root: Path | str,
) -> BacktestRequest:
    if not draft.symbol:
        raise ValueError("El draft necesita un activo seleccionado.")
    return BacktestRequest(
        symbol=draft.symbol,
        strategy_key=draft.strategy_key,
        strategy_parameters=draft.strategy_parameters,
        data_dir=data_dir,
        interval=draft.interval,
        start=draft.start,
        end=draft.end,
        price_column=draft.price_column,
        initial_capital=draft.initial_capital,
        commission_bps=draft.commission_bps,
        slippage_bps=draft.slippage_bps,
        risk=draft.risk,
        experiment_name=draft.experiment_name,
        notes=draft.notes,
        research_preset=draft.research_preset,
        save_experiment=True,
        experiments_root=experiments_root,
    )


def build_draft_robustness_request(
    draft: ExperimentDraft,
    *,
    symbols: tuple[str, ...],
    data_dir: Path | str,
    train_ratio: float = 0.7,
    run_walk_forward: bool = True,
    run_regime_analysis: bool = True,
    wf_train_rows: int = 756,
    wf_test_rows: int = 252,
    wf_step_rows: int = 252,
    regime_min_rows: int = 60,
) -> RobustnessRequest:
    if not draft.symbol:
        raise ValueError("El draft necesita un activo base seleccionado.")
    selected_symbols = symbols or (draft.symbol,)
    return RobustnessRequest(
        symbols=selected_symbols,
        strategy_key=draft.strategy_key,
        strategy_parameters=draft.strategy_parameters,
        data_dir=data_dir,
        interval=draft.interval,
        start=draft.start,
        end=draft.end,
        price_column=draft.price_column,
        initial_capital=draft.initial_capital,
        commission_bps=draft.commission_bps,
        slippage_bps=draft.slippage_bps,
        train_ratio=train_ratio,
        run_walk_forward=run_walk_forward,
        run_regime_analysis=run_regime_analysis,
        wf_train_rows=wf_train_rows,
        wf_test_rows=wf_test_rows,
        wf_step_rows=wf_step_rows,
        regime_min_rows=regime_min_rows,
    )


def recommend_journal_status(
    *,
    robustness_result: RobustnessResult | None = None,
    stress_result: StressTestResult | None = None,
    fallback: str = "Needs Review",
) -> str:
    """Sugiere un estado editorial sin convertirlo en recomendacion de inversion."""
    has_robustness = _has_strategy_diagnostics(robustness_result)
    has_robustness_flags = _has_strategy_diagnostic_flags(robustness_result)
    stress_conclusion = str(getattr(stress_result, "conclusion", "") or "")

    if stress_conclusion == "No confiable":
        return "Rejected"
    if stress_conclusion == "Fragil":
        return "Rejected" if has_robustness_flags else "Needs Review"
    if stress_conclusion == "Robusta" and has_robustness and not has_robustness_flags:
        return "Robustness Passed"
    if has_robustness and not has_robustness_flags:
        return "Promising"
    if has_robustness_flags:
        return "Needs Review"
    return fallback


def _strategy_diagnostics(result: RobustnessResult | None):
    diagnostics = getattr(result, "diagnostics", None)
    if diagnostics is None or diagnostics.empty or "strategy" not in diagnostics:
        return None
    subset = diagnostics[diagnostics["strategy"] != "buy_and_hold"]
    return subset if not subset.empty else None


def _has_strategy_diagnostics(result: RobustnessResult | None) -> bool:
    subset = _strategy_diagnostics(result)
    return subset is not None and not subset.empty


def _has_strategy_diagnostic_flags(result: RobustnessResult | None) -> bool:
    subset = _strategy_diagnostics(result)
    if subset is None or subset.empty or "flags" not in subset:
        return False
    return any(bool(str(value).strip()) for value in subset["flags"].fillna(""))
