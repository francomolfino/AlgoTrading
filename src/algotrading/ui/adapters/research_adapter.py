from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import pandas as pd

from algotrading.ui.adapters.evidence_adapter import EvidenceScore, build_evidence_score_from_details
from algotrading.ui.adapters.experiment_adapter import (
    ExperimentDetails,
    ExperimentRecord,
    load_experiment_details,
)
from algotrading.ui.adapters.guided_adapter import recommend_journal_status
from algotrading.ui.adapters.journal_adapter import ResearchNotes, load_research_notes
from algotrading.ui.adapters.robustness_adapter import RobustnessRequest, RobustnessResult, robustness_comment
from algotrading.ui.adapters.stress_adapter import StressTestRequest, StressTestResult
from algotrading.ui.adapters.verdict_adapter import ResearchVerdict, build_research_verdict_from_details


RESEARCH_DIR = "research"
ROBUSTNESS_REQUEST = "robustness_request.json"
ROBUSTNESS_DIAGNOSTICS = "robustness_diagnostics.csv"
ROBUSTNESS_TRAIN_TEST = "robustness_train_test.csv"
ROBUSTNESS_WALK_FORWARD = "robustness_walk_forward.csv"
ROBUSTNESS_REGIMES = "robustness_regimes.csv"
STRESS_REQUEST = "stress_request.json"
STRESS_METADATA = "stress_metadata.json"
STRESS_COMPARISON = "stress_comparison.csv"


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
    has_robustness: bool
    robustness_summary: dict[str, Any] | None
    has_stress: bool
    stress_summary: dict[str, Any] | None
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
        has_robustness=robustness is not None,
        robustness_summary=robustness_summary,
        has_stress=stress is not None,
        stress_summary=stress_summary,
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
        rows.append(
            {
                "name": record.name,
                "run_id": record.run_id,
                "created_at": record.created_at,
                "strategy": record.strategy,
                "symbols": ", ".join(record.symbols),
                "journal_status": summary.journal_state if summary else record.status,
                "evidence_score": summary.evidence_score.score if summary else None,
                "has_robustness": bool(summary and summary.has_robustness),
                "has_stress": bool(summary and summary.has_stress),
                "favorite": summary.journal_favorite if summary else record.favorite,
                "tags": ", ".join(summary.journal_tags if summary else record.tags),
                "total_return": record.total_return,
                "sharpe_ratio": record.sharpe_ratio,
                "max_drawdown": record.max_drawdown,
                "path": str(record.path),
            }
        )
    return pd.DataFrame(rows)


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
