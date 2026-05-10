from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd


DEFAULT_RESEARCH_PRESET = "sanity_check"


@dataclass(frozen=True)
class ResearchPreset:
    key: str
    label: str
    description: str
    required_checks: tuple[str, ...]
    important_metrics: tuple[str, ...]
    minimum_evidence_score: int
    recommended_next_action: str
    ui_text: str


RESEARCH_PRESETS: dict[str, ResearchPreset] = {
    "sanity_check": ResearchPreset(
        key="sanity_check",
        label="Sanity Check",
        description="Primer filtro para detectar errores obvios antes de creer cualquier resultado.",
        required_checks=(
            "Datos validados",
            "Costos incluidos",
            "Comparacion contra buy and hold",
            "Lectura critica de trades y drawdown",
        ),
        important_metrics=("retorno total", "max drawdown", "trades", "exceso vs benchmark"),
        minimum_evidence_score=35,
        recommended_next_action="Si no aparecen errores obvios, correr robustez antes de optimizar.",
        ui_text="Usalo para revisar si el backtest tiene sentido mecanico. No busca confirmar una estrategia.",
    ),
    "benchmark_comparison": ResearchPreset(
        key="benchmark_comparison",
        label="Benchmark Comparison",
        description="Enfocado en comparar la estrategia contra buy and hold o benchmark equivalente.",
        required_checks=(
            "Benchmark disponible",
            "Mismo periodo para estrategia y benchmark",
            "Costos incluidos",
            "Drawdown comparado",
        ),
        important_metrics=("exceso vs benchmark", "benchmark total return", "benchmark max drawdown", "CAGR"),
        minimum_evidence_score=45,
        recommended_next_action="Explicar por que la estrategia gana o pierde contra benchmark antes de seguir.",
        ui_text="Sirve para evitar autoenganos: una estrategia activa tiene que justificar por que no es buy and hold.",
    ),
    "robustness_validation": ResearchPreset(
        key="robustness_validation",
        label="Robustness Validation",
        description="Validacion fuera de muestra, walk-forward y preferentemente multi-activo.",
        required_checks=(
            "Train/test corrido",
            "Walk-forward corrido si hay datos suficientes",
            "Prueba multi-activo si hay datos locales",
            "Comparacion contra benchmark",
        ),
        important_metrics=("out-of-sample", "walk-forward", "robustness score", "trades en test"),
        minimum_evidence_score=60,
        recommended_next_action="Si la evidencia es mixta, ampliar muestra o simplificar parametros.",
        ui_text="Usalo cuando una idea ya paso el sanity check y queres saber si sobrevive fuera del caso base.",
    ),
    "stress_test_only": ResearchPreset(
        key="stress_test_only",
        label="Stress Test Only",
        description="Revisa sensibilidad a costos, delay de ejecucion y eventos extremos.",
        required_checks=(
            "Stress test asociado al experimento",
            "Costos duplicados",
            "Slippage duplicado",
            "Mejores trades/mes removidos",
        ),
        important_metrics=("delta retorno", "delta drawdown", "delta Sharpe", "conclusion stress"),
        minimum_evidence_score=50,
        recommended_next_action="Si el stress rompe el resultado, marcarlo como fragil o rechazado.",
        ui_text="No reemplaza robustez. Sirve para ver si el resultado depende de supuestos demasiado delicados.",
    ),
    "paper_candidate_review": ResearchPreset(
        key="paper_candidate_review",
        label="Paper Trading Candidate Review",
        description="Revision final antes de pasar a simulacion paper mas detallada.",
        required_checks=(
            "Evidence Score razonable",
            "Robustez corrida",
            "Stress test corrido",
            "Journal con conclusion",
            "Risk management definido",
        ),
        important_metrics=("Evidence Score", "max drawdown", "stress conclusion", "exposure time"),
        minimum_evidence_score=70,
        recommended_next_action="Si pasa, correr paper trading simulado y revisar replay barra por barra.",
        ui_text="No habilita trading real. Solo ordena la evidencia antes de simular paper trading.",
    ),
    "strategy_rejection_review": ResearchPreset(
        key="strategy_rejection_review",
        label="Strategy Rejection Review",
        description="Checklist para descartar una idea con trazabilidad y sin borrarla de la historia.",
        required_checks=(
            "Motivo de rechazo escrito",
            "Benchmark revisado",
            "Flags criticos documentados",
            "Proximo test o decision de archivo",
        ),
        important_metrics=("flags criticos", "exceso vs benchmark", "drawdown", "trades"),
        minimum_evidence_score=0,
        recommended_next_action="Guardar conclusion en journal y marcar Rejected o Archived.",
        ui_text="Muy util cuando una estrategia falla: documentar por que se descarta evita repetir el mismo experimento.",
    ),
}


def list_research_presets() -> list[ResearchPreset]:
    return list(RESEARCH_PRESETS.values())


def preset_keys() -> list[str]:
    return list(RESEARCH_PRESETS)


def get_research_preset(key: str | None) -> ResearchPreset:
    normalized = normalize_preset_key(key)
    return RESEARCH_PRESETS[normalized]


def normalize_preset_key(key: str | None) -> str:
    if key in RESEARCH_PRESETS:
        return str(key)
    return DEFAULT_RESEARCH_PRESET


def preset_label(key: str | None) -> str:
    return get_research_preset(key).label


def preset_to_dict(preset: ResearchPreset | str | None) -> dict[str, Any]:
    if isinstance(preset, ResearchPreset):
        return asdict(preset)
    return asdict(get_research_preset(preset))


def preset_frame(preset: ResearchPreset | str | None) -> pd.DataFrame:
    item = preset if isinstance(preset, ResearchPreset) else get_research_preset(preset)
    rows = [
        ("Descripcion", item.description),
        ("Checks requeridos", "; ".join(item.required_checks)),
        ("Metricas importantes", "; ".join(item.important_metrics)),
        ("Evidence minimo", f"{item.minimum_evidence_score}/100"),
        ("Proxima accion", item.recommended_next_action),
    ]
    return pd.DataFrame([{"campo": field, "valor": value} for field, value in rows])
