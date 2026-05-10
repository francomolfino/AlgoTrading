from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd

from algotrading.ui.adapters.data_quality_adapter import AdvancedDataQualityReport, advanced_quality_from_dict
from algotrading.ui.adapters.evidence_adapter import EvidenceScore, build_evidence_score_from_details
from algotrading.ui.adapters.experiment_adapter import (
    ExperimentDetails,
    ExperimentRecord,
    load_experiment_details,
)
from algotrading.ui.adapters.guided_adapter import recommend_journal_status
from algotrading.ui.adapters.journal_adapter import ResearchNotes, load_research_notes
from algotrading.ui.adapters.preset_adapter import ResearchPreset, get_research_preset, normalize_preset_key
from algotrading.ui.adapters.robustness_adapter import RobustnessRequest, RobustnessResult, robustness_comment
from algotrading.ui.adapters.stress_adapter import StressTestRequest, StressTestResult
from algotrading.ui.adapters.verdict_adapter import ResearchVerdict, build_research_verdict_from_details


RESEARCH_DIR = "research"
EXPERIMENT_METADATA_FILENAME = "experiment_metadata.json"
ROBUSTNESS_REQUEST = "robustness_request.json"
ROBUSTNESS_DIAGNOSTICS = "robustness_diagnostics.csv"
ROBUSTNESS_TRAIN_TEST = "robustness_train_test.csv"
ROBUSTNESS_WALK_FORWARD = "robustness_walk_forward.csv"
ROBUSTNESS_REGIMES = "robustness_regimes.csv"
STRESS_REQUEST = "stress_request.json"
STRESS_METADATA = "stress_metadata.json"
STRESS_COMPARISON = "stress_comparison.csv"
DATA_QUALITY_FILENAME = "data_quality.json"

PIPELINE_BACKTEST_CREATED = "Backtest creado"
PIPELINE_RESULTS_REVIEWED = "Resultados revisados"
PIPELINE_ROBUSTNESS_DONE = "Robustez corrida"
PIPELINE_STRESS_DONE = "Stress test corrido"
PIPELINE_JOURNAL_COMPLETED = "Journal completado"
PIPELINE_PAPER_CANDIDATE = "Candidato a paper trading"
PIPELINE_REJECTED = "Rechazado"
PIPELINE_ARCHIVED = "Archivado"

TERMINAL_JOURNAL_STATUS_TO_PIPELINE = {
    "Paper Simulation Candidate": PIPELINE_PAPER_CANDIDATE,
    "Rejected": PIPELINE_REJECTED,
    "Archived": PIPELINE_ARCHIVED,
}


@dataclass(frozen=True)
class ResearchPipelineStep:
    name: str
    completed: bool
    source: str


@dataclass(frozen=True)
class ComparisonFairnessIssue:
    category: str
    message: str
    severity: str = "warning"


@dataclass(frozen=True)
class ResearchSummary:
    experiment_id: str
    experiment_path: Path
    details: ExperimentDetails
    verdict: ResearchVerdict
    evidence_score: EvidenceScore
    journal_state: str | None
    journal_tags: tuple[str, ...]
    journal_hypothesis: str
    journal_conclusion: str
    journal_next_test: str
    journal_favorite: bool
    has_journal: bool
    pipeline_state: str
    pipeline_steps: tuple[ResearchPipelineStep, ...]
    has_robustness: bool
    robustness_summary: dict[str, Any] | None
    has_stress: bool
    stress_summary: dict[str, Any] | None
    research_preset: ResearchPreset
    data_quality: AdvancedDataQualityReport | None
    experiment_metadata: dict[str, Any]
    recommended_next_action: str
    critical_flags: tuple[str, ...]


def build_research_summary(experiment_dir: Path | str) -> ResearchSummary:
    details = load_experiment_details(experiment_dir)
    notes = load_research_notes(experiment_dir)
    robustness = load_robustness_for_experiment(experiment_dir)
    stress = load_stress_for_experiment(experiment_dir)
    verdict = build_research_verdict_from_details(details)
    evidence_score = build_evidence_score_from_details(
        details,
        robustness_result=robustness,
        stress_result=stress,
    )
    robustness_summary = summarize_robustness(robustness)
    stress_summary = summarize_stress(stress)
    research_preset = _research_preset_from_details(details)
    data_quality = load_data_quality_for_experiment(experiment_dir)
    has_journal = _has_journal(notes)
    pipeline_steps = build_pipeline_steps(
        details=details,
        notes=notes,
        has_robustness=robustness is not None,
        has_stress=stress is not None,
    )
    pipeline_state = derive_pipeline_state(notes=notes, steps=pipeline_steps)
    experiment_metadata = load_experiment_metadata(experiment_dir, details=details)
    flags = _critical_flags(verdict, robustness_summary, stress_summary)
    return ResearchSummary(
        experiment_id=details.config.get("run_id", details.path.name),
        experiment_path=details.path,
        details=details,
        verdict=verdict,
        evidence_score=evidence_score,
        journal_state=notes.status,
        journal_tags=notes.tags,
        journal_hypothesis=notes.hypothesis,
        journal_conclusion=notes.conclusion,
        journal_next_test=notes.next_test,
        journal_favorite=notes.favorite,
        has_journal=has_journal,
        pipeline_state=pipeline_state,
        pipeline_steps=pipeline_steps,
        has_robustness=robustness is not None,
        robustness_summary=robustness_summary,
        has_stress=stress is not None,
        stress_summary=stress_summary,
        research_preset=research_preset,
        data_quality=data_quality,
        experiment_metadata=experiment_metadata,
        recommended_next_action=recommend_next_action(
            verdict=verdict,
            evidence_score=evidence_score,
            notes=notes,
            has_robustness=robustness is not None,
            stress=stress,
        ),
        critical_flags=tuple(flags),
    )


def build_research_summaries(records: list[ExperimentRecord]) -> list[ResearchSummary]:
    summaries: list[ResearchSummary] = []
    for record in records:
        try:
            summaries.append(build_research_summary(record.path))
        except Exception:
            continue
    return summaries


def research_records_frame(records: list[ExperimentRecord]) -> pd.DataFrame:
    summaries_by_path = {str(summary.experiment_path): summary for summary in build_research_summaries(records)}
    rows = []
    for record in records:
        summary = summaries_by_path.get(str(record.path))
        rows.append(_research_record_row(record, summary))
    return pd.DataFrame(rows)


def research_records_frame_from_paths(paths: tuple[str, ...] | list[str]) -> pd.DataFrame:
    rows = []
    for path_value in paths:
        try:
            summary = build_research_summary(path_value)
        except Exception:
            continue
        rows.append(_research_summary_row(summary))
    return pd.DataFrame(rows)


def research_records_cache_signature(records: list[ExperimentRecord]) -> tuple[tuple[str, float], ...]:
    return tuple(
        (str(record.path), _experiment_fingerprint(record.path))
        for record in records
    )


def build_pipeline_steps(
    *,
    details: ExperimentDetails,
    notes: ResearchNotes,
    has_robustness: bool,
    has_stress: bool,
) -> tuple[ResearchPipelineStep, ...]:
    return (
        ResearchPipelineStep(
            PIPELINE_BACKTEST_CREATED,
            completed=bool(details.config and not details.summary.empty and bool(details.metrics)),
            source="config/summary/metrics",
        ),
        ResearchPipelineStep(
            PIPELINE_RESULTS_REVIEWED,
            completed=_has_journal(notes),
            source="research_notes.json",
        ),
        ResearchPipelineStep(
            PIPELINE_ROBUSTNESS_DONE,
            completed=has_robustness,
            source=f"{RESEARCH_DIR}/{ROBUSTNESS_DIAGNOSTICS}",
        ),
        ResearchPipelineStep(
            PIPELINE_STRESS_DONE,
            completed=has_stress,
            source=f"{RESEARCH_DIR}/{STRESS_COMPARISON}",
        ),
        ResearchPipelineStep(
            PIPELINE_JOURNAL_COMPLETED,
            completed=_journal_completed(notes),
            source="research_notes.json",
        ),
    )


def derive_pipeline_state(
    *,
    notes: ResearchNotes,
    steps: tuple[ResearchPipelineStep, ...],
) -> str:
    terminal = TERMINAL_JOURNAL_STATUS_TO_PIPELINE.get(notes.status)
    if terminal:
        return terminal
    completed = {step.name for step in steps if step.completed}
    if {
        PIPELINE_ROBUSTNESS_DONE,
        PIPELINE_STRESS_DONE,
        PIPELINE_JOURNAL_COMPLETED,
    }.issubset(completed):
        return PIPELINE_JOURNAL_COMPLETED
    if PIPELINE_STRESS_DONE in completed:
        return PIPELINE_STRESS_DONE
    if PIPELINE_ROBUSTNESS_DONE in completed:
        return PIPELINE_ROBUSTNESS_DONE
    if PIPELINE_RESULTS_REVIEWED in completed:
        return PIPELINE_RESULTS_REVIEWED
    return PIPELINE_BACKTEST_CREATED


def load_experiment_metadata(
    experiment_dir: Path | str,
    *,
    details: ExperimentDetails | None = None,
) -> dict[str, Any]:
    directory = Path(experiment_dir)
    path = directory / EXPERIMENT_METADATA_FILENAME
    if path.exists():
        payload = _read_json(path)
        if payload:
            payload.setdefault("metadata_available", True)
            return payload
    details = details or load_experiment_details(directory)
    return _fallback_experiment_metadata(details)


def load_data_quality_for_experiment(experiment_dir: Path | str) -> AdvancedDataQualityReport | None:
    payload = _read_json(Path(experiment_dir) / DATA_QUALITY_FILENAME)
    return advanced_quality_from_dict(payload)


def compare_experiment_fairness(records: list[ExperimentRecord]) -> list[ComparisonFairnessIssue]:
    if len(records) < 2:
        return []
    details = []
    for record in records:
        try:
            details.append(load_experiment_details(record.path))
        except Exception:
            continue
    if len(details) < 2:
        return []

    issues: list[ComparisonFairnessIssue] = []
    _add_issue_if_multiple(
        issues,
        "Activos",
        "Los experimentos usan activos distintos; comparar retornos directos puede ser enganoso.",
        [_symbols_key(item) for item in details],
    )
    _add_issue_if_multiple(
        issues,
        "Periodos",
        "Los experimentos usan fechas distintas; el ranking puede depender del periodo.",
        [_period_key(item) for item in details],
    )
    _add_issue_if_multiple(
        issues,
        "Benchmark",
        "La comparacion contra benchmark no es equivalente o no esta disponible en todos.",
        [_benchmark_key(item) for item in details],
    )
    _add_issue_if_multiple(
        issues,
        "Costos",
        "Comision o slippage difieren entre experimentos.",
        [_costs_key(item) for item in details],
    )
    _add_issue_if_multiple(
        issues,
        "Risk settings",
        "Las reglas de risk management difieren entre experimentos.",
        [_risk_key(item) for item in details],
    )
    return issues


def save_robustness_for_experiment(
    experiment_dir: Path | str,
    request: RobustnessRequest,
    result: RobustnessResult,
) -> Path:
    directory = _research_dir(experiment_dir)
    _write_json(directory / ROBUSTNESS_REQUEST, _json_safe(asdict(request)))
    result.diagnostics.to_csv(directory / ROBUSTNESS_DIAGNOSTICS, index=False)
    result.train_test.to_csv(directory / ROBUSTNESS_TRAIN_TEST, index=False)
    result.walk_forward.to_csv(directory / ROBUSTNESS_WALK_FORWARD, index=False)
    result.regimes.to_csv(directory / ROBUSTNESS_REGIMES, index=False)
    return directory


def load_robustness_for_experiment(experiment_dir: Path | str) -> RobustnessResult | None:
    directory = Path(experiment_dir) / RESEARCH_DIR
    diagnostics_path = directory / ROBUSTNESS_DIAGNOSTICS
    if not diagnostics_path.exists():
        return None
    return RobustnessResult(
        train_test=_safe_read_csv(directory / ROBUSTNESS_TRAIN_TEST),
        walk_forward=_safe_read_csv(directory / ROBUSTNESS_WALK_FORWARD),
        diagnostics=_safe_read_csv(diagnostics_path),
        regimes=_safe_read_csv(directory / ROBUSTNESS_REGIMES),
    )


def save_stress_for_experiment(
    experiment_dir: Path | str,
    result: StressTestResult,
) -> Path:
    directory = _research_dir(experiment_dir)
    _write_json(directory / STRESS_REQUEST, _json_safe(asdict(result.request)))
    _write_json(
        directory / STRESS_METADATA,
        {
            "conclusion": result.conclusion,
            "flags": list(result.flags),
        },
    )
    result.comparison.to_csv(directory / STRESS_COMPARISON, index=False)
    return directory


def load_stress_for_experiment(experiment_dir: Path | str) -> StressTestResult | None:
    directory = Path(experiment_dir) / RESEARCH_DIR
    request_path = directory / STRESS_REQUEST
    metadata_path = directory / STRESS_METADATA
    comparison_path = directory / STRESS_COMPARISON
    if not request_path.exists() or not metadata_path.exists() or not comparison_path.exists():
        return None

    request_payload = _read_json(request_path)
    metadata = _read_json(metadata_path)
    return StressTestResult(
        request=StressTestRequest(**_stress_request_payload(request_payload)),
        scenarios=(),
        comparison=_safe_read_csv(comparison_path),
        conclusion=str(metadata.get("conclusion", "")),
        flags=tuple(str(flag) for flag in metadata.get("flags", [])),
    )


def summarize_robustness(result: RobustnessResult | None) -> dict[str, Any] | None:
    if result is None or result.diagnostics.empty:
        return None
    subset = result.diagnostics
    if "strategy" in subset:
        non_benchmark = subset[subset["strategy"].astype(str) != "buy_and_hold"]
        if not non_benchmark.empty:
            subset = non_benchmark
    row = subset.iloc[0].to_dict()
    return {
        "comment": robustness_comment(result.diagnostics),
        "symbols": int(result.diagnostics["symbol"].nunique()) if "symbol" in result.diagnostics else 0,
        "rows": int(len(result.diagnostics)),
        "strategy": str(row.get("strategy", "")),
        "score": _optional_float(row.get("robustness_score")),
        "flags": str(row.get("flags", "") or ""),
        "has_walk_forward": not result.walk_forward.empty,
    }


def summarize_stress(result: StressTestResult | None) -> dict[str, Any] | None:
    if result is None:
        return None
    comparison = result.comparison
    worst_delta = None
    if not comparison.empty and "delta_return_vs_base" in comparison:
        deltas = pd.to_numeric(comparison["delta_return_vs_base"], errors="coerce").dropna()
        worst_delta = float(deltas.min()) if not deltas.empty else None
    return {
        "conclusion": result.conclusion,
        "flags": tuple(result.flags),
        "scenarios": int(len(comparison)),
        "worst_delta_return_vs_base": worst_delta,
    }


def recommend_next_action(
    *,
    verdict: ResearchVerdict,
    evidence_score: EvidenceScore,
    notes: ResearchNotes,
    has_robustness: bool,
    stress: StressTestResult | None,
) -> str:
    if not has_robustness:
        return "Correr robustez desde este experimento: train/test y, si hay datos suficientes, walk-forward."
    if stress is None:
        return "Correr stress test asociado para revisar sensibilidad a costos, delay y eventos extremos."
    if stress.conclusion == "No confiable":
        return "Marcar como Rejected o volver a la hipotesis: el stress test rompio el resultado."
    if stress.conclusion == "Fragil":
        return "Revisar supuestos y ampliar validacion antes de considerar paper trading simulado."
    if evidence_score.score < 50:
        return "Mejorar evidencia: mas datos, mas activos o menos parametros antes de seguir."
    if not notes.conclusion.strip():
        return "Completar conclusion del journal con lo aprendido de resultados, robustez y stress."
    return verdict.next_action


def suggested_journal_status(summary: ResearchSummary) -> str:
    robustness = load_robustness_for_experiment(summary.experiment_path)
    stress = load_stress_for_experiment(summary.experiment_path)
    return recommend_journal_status(
        robustness_result=robustness,
        stress_result=stress,
        fallback=summary.journal_state or "Needs Review",
    )


def _research_record_row(record: ExperimentRecord, summary: ResearchSummary | None) -> dict[str, Any]:
    if summary is None:
        return {
            "name": record.name,
            "run_id": record.run_id,
            "created_at": record.created_at,
            "strategy": record.strategy,
            "symbols": ", ".join(record.symbols),
            "pipeline_state": PIPELINE_BACKTEST_CREATED,
            "journal_status": record.status,
            "evidence_score": None,
            "has_robustness": False,
            "has_stress": False,
            "has_journal": False,
            "favorite": record.favorite,
            "tags": ", ".join(record.tags),
            "total_return": record.total_return,
            "sharpe_ratio": record.sharpe_ratio,
            "max_drawdown": record.max_drawdown,
            "research_preset": "Sanity Check",
            "data_quality_score": None,
            "data_quality_severity": "no disponible",
            "path": str(record.path),
        }
    return _research_summary_row(summary)


def _research_summary_row(summary: ResearchSummary) -> dict[str, Any]:
    details = summary.details
    first_row = details.summary.iloc[0].to_dict() if not details.summary.empty else {}
    config = details.config if isinstance(details.config, dict) else {}
    strategy_config = config.get("strategy", {}) if isinstance(config.get("strategy", {}), dict) else {}
    symbols = config.get("symbols", [])
    if not isinstance(symbols, list):
        symbols = [details.symbol] if details.symbol else []
    return {
        "name": str(config.get("experiment_name", details.path.name)),
        "run_id": str(config.get("run_id", details.path.name)),
        "created_at": str(details.metadata.get("created_at_utc", "")),
        "strategy": str(first_row.get("strategy") or strategy_config.get("name", "")),
        "symbols": ", ".join(str(symbol) for symbol in symbols),
        "pipeline_state": summary.pipeline_state,
        "journal_status": summary.journal_state,
        "evidence_score": summary.evidence_score.score,
        "has_robustness": summary.has_robustness,
        "has_stress": summary.has_stress,
        "has_journal": summary.has_journal,
        "favorite": summary.journal_favorite,
        "tags": ", ".join(summary.journal_tags),
        "total_return": _optional_float(first_row.get("total_return")),
        "sharpe_ratio": _optional_float(first_row.get("sharpe_ratio")),
        "max_drawdown": _optional_float(first_row.get("max_drawdown")),
        "research_preset": summary.research_preset.label,
        "data_quality_score": summary.data_quality.score if summary.data_quality else None,
        "data_quality_severity": summary.data_quality.severity if summary.data_quality else "no disponible",
        "path": str(details.path),
    }


def _research_preset_from_details(details: ExperimentDetails) -> ResearchPreset:
    config = details.config if isinstance(details.config, dict) else {}
    research_config = config.get("research", {}) if isinstance(config.get("research", {}), dict) else {}
    metadata = load_experiment_metadata(details.path, details=details)
    metadata_research = metadata.get("research", {}) if isinstance(metadata.get("research", {}), dict) else {}
    key = (
        config.get("research_preset")
        or research_config.get("preset")
        or metadata_research.get("preset")
        or metadata_research.get("preset_key")
    )
    return get_research_preset(normalize_preset_key(str(key) if key else None))


def _experiment_fingerprint(experiment_dir: Path | str) -> float:
    directory = Path(experiment_dir)
    paths = [
        directory / "config.json",
        directory / "metadata.json",
        directory / "summary.csv",
        directory / "research_notes.json",
        directory / EXPERIMENT_METADATA_FILENAME,
        directory / DATA_QUALITY_FILENAME,
        directory / RESEARCH_DIR / ROBUSTNESS_DIAGNOSTICS,
        directory / RESEARCH_DIR / STRESS_COMPARISON,
        directory / RESEARCH_DIR / STRESS_METADATA,
    ]
    mtimes = [path.stat().st_mtime for path in paths if path.exists()]
    return max(mtimes) if mtimes else 0.0


def _has_journal(notes: ResearchNotes) -> bool:
    return any(
        [
            notes.updated_at_utc,
            notes.status != "Draft",
            notes.hypothesis.strip(),
            notes.conclusion.strip(),
            notes.next_test.strip(),
            notes.tags,
            notes.favorite,
        ]
    )


def _journal_completed(notes: ResearchNotes) -> bool:
    return bool(
        notes.hypothesis.strip()
        and notes.conclusion.strip()
        and notes.next_test.strip()
    )


def _fallback_experiment_metadata(details: ExperimentDetails) -> dict[str, Any]:
    config = details.config if isinstance(details.config, dict) else {}
    backtest = config.get("backtest", {}) if isinstance(config.get("backtest", {}), dict) else {}
    strategy = config.get("strategy", {}) if isinstance(config.get("strategy", {}), dict) else {}
    metadata = details.metadata if isinstance(details.metadata, dict) else {}
    return {
        "schema_version": 1,
        "metadata_available": False,
        "experiment_name": config.get("experiment_name", "no disponible"),
        "run_id": config.get("run_id", details.path.name),
        "created_at_utc": metadata.get("created_at_utc", "no disponible"),
        "project": {
            "package_version": metadata.get("package_version", "no disponible"),
            "git_commit": metadata.get("git_commit", "no disponible"),
            "git_dirty": metadata.get("git_dirty", "no disponible"),
        },
        "data": {
            "data_dir": config.get("data_dir", "no disponible"),
            "symbols": config.get("symbols", []),
            "interval": config.get("interval", "no disponible"),
            "start": config.get("start") or _summary_value(details, "start_date"),
            "end": config.get("end") or _summary_value(details, "end_date"),
            "price_column": config.get("price_column", "no disponible"),
        },
        "strategy": {
            "name": strategy.get("name", "no disponible"),
            "parameters": strategy.get("parameters", {}),
        },
        "research": {
            "preset": config.get("research_preset", "sanity_check"),
        },
        "costs": {
            "commission_bps": backtest.get("commission_bps", "no disponible"),
            "slippage_bps": backtest.get("slippage_bps", "no disponible"),
        },
        "risk": _risk_payload(backtest),
        "outputs": _discover_output_files(details.path),
    }


def _summary_value(details: ExperimentDetails, key: str) -> str:
    if details.summary.empty or key not in details.summary:
        return "no disponible"
    value = details.summary[key].iloc[0]
    return "no disponible" if pd.isna(value) else str(value)


def _risk_payload(backtest: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "position_fraction",
        "max_total_exposure",
        "max_drawdown_pct",
        "max_trades_per_day",
        "stop_loss_pct",
        "take_profit_pct",
        "volatility_target_pct",
        "volatility_window",
    )
    return {key: backtest.get(key, "no disponible") for key in keys}


def _discover_output_files(experiment_dir: Path) -> dict[str, str]:
    paths = {
        "config": experiment_dir / "config.json",
        "metadata": experiment_dir / "metadata.json",
        "summary": experiment_dir / "summary.csv",
        "notes": experiment_dir / "notes.md",
        "research_notes": experiment_dir / "research_notes.json",
    }
    outputs = {
        key: str(path)
        for key, path in paths.items()
        if path.exists()
    }
    children = experiment_dir.iterdir() if experiment_dir.exists() else []
    for child in children:
        if child.is_dir() and child.name != RESEARCH_DIR and (child / "metrics.json").exists():
            outputs[f"{child.name}_metrics"] = str(child / "metrics.json")
            outputs[f"{child.name}_equity"] = str(child / "equity.csv")
            outputs[f"{child.name}_trades"] = str(child / "trades.csv")
            outputs[f"{child.name}_orders"] = str(child / "orders.csv")
    return outputs


def _add_issue_if_multiple(
    issues: list[ComparisonFairnessIssue],
    category: str,
    message: str,
    values: list[object],
) -> None:
    if len({str(value) for value in values}) > 1:
        issues.append(ComparisonFairnessIssue(category=category, message=message))


def _symbols_key(details: ExperimentDetails) -> tuple[str, ...]:
    symbols = details.config.get("symbols", []) if isinstance(details.config, dict) else []
    if isinstance(symbols, list) and symbols:
        return tuple(str(symbol) for symbol in symbols)
    return (str(details.symbol),) if details.symbol else ()


def _period_key(details: ExperimentDetails) -> tuple[str, str]:
    config = details.config if isinstance(details.config, dict) else {}
    return (
        str(config.get("start") or _summary_value(details, "start_date")),
        str(config.get("end") or _summary_value(details, "end_date")),
    )


def _benchmark_key(details: ExperimentDetails) -> str:
    config = details.config if isinstance(details.config, dict) else {}
    benchmark = config.get("benchmark")
    if benchmark:
        return str(benchmark)
    if details.metrics and "benchmark_total_return" in details.metrics:
        return "buy_and_hold"
    return "no disponible"


def _costs_key(details: ExperimentDetails) -> tuple[object, object]:
    backtest = details.config.get("backtest", {}) if isinstance(details.config, dict) else {}
    if not isinstance(backtest, dict):
        return ("no disponible", "no disponible")
    return (
        backtest.get("commission_bps", "no disponible"),
        backtest.get("slippage_bps", "no disponible"),
    )


def _risk_key(details: ExperimentDetails) -> tuple[tuple[str, object], ...]:
    backtest = details.config.get("backtest", {}) if isinstance(details.config, dict) else {}
    if not isinstance(backtest, dict):
        return ()
    return tuple(sorted(_risk_payload(backtest).items()))


def _critical_flags(
    verdict: ResearchVerdict,
    robustness_summary: dict[str, Any] | None,
    stress_summary: dict[str, Any] | None,
) -> list[str]:
    flags = list(verdict.flags)
    if robustness_summary and robustness_summary.get("flags"):
        flags.append(f"Robustez: {robustness_summary['flags']}")
    if stress_summary:
        stress_flags = stress_summary.get("flags") or ()
        flags.extend(f"Stress: {flag}" for flag in stress_flags)
    return flags


def _research_dir(experiment_dir: Path | str) -> Path:
    directory = Path(experiment_dir) / RESEARCH_DIR
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _stress_request_payload(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = set(StressTestRequest.__dataclass_fields__)
    normalized = {key: value for key, value in payload.items() if key in allowed}
    normalized.setdefault("symbol", "")
    normalized.setdefault("strategy_key", "")
    normalized.setdefault("strategy_parameters", {})
    return normalized


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _optional_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
