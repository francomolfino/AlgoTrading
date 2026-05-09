"""Evaluacion de robustez y controles contra autoengano."""

from algotrading.evaluation.guardrails import (
    count_parameter_combinations,
    validate_parameter_grid_size,
)
from algotrading.evaluation.diagnostics import (
    analyze_parameter_sensitivity,
    build_robustness_diagnostics,
    evaluate_multi_asset_train_test,
    evaluate_multi_asset_walk_forward,
)
from algotrading.evaluation.robustness import (
    evaluate_train_test,
    evaluate_walk_forward,
    make_train_test_split,
    make_walk_forward_splits,
)

__all__ = [
    "count_parameter_combinations",
    "analyze_parameter_sensitivity",
    "build_robustness_diagnostics",
    "evaluate_multi_asset_train_test",
    "evaluate_multi_asset_walk_forward",
    "evaluate_train_test",
    "evaluate_walk_forward",
    "make_train_test_split",
    "make_walk_forward_splits",
    "validate_parameter_grid_size",
]
