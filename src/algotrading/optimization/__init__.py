"""Optimizacion controlada de parametros."""

from algotrading.optimization.grid_search import (
    OptimizationCandidate,
    OptimizationSearchResult,
    build_rsi_candidates,
    build_sma_candidates,
    run_controlled_search,
    validate_candidate_count,
)

__all__ = [
    "OptimizationCandidate",
    "OptimizationSearchResult",
    "build_rsi_candidates",
    "build_sma_candidates",
    "run_controlled_search",
    "validate_candidate_count",
]
