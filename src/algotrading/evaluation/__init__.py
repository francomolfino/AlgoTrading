"""Evaluacion de robustez y controles contra autoengano."""

from algotrading.evaluation.guardrails import (
    count_parameter_combinations,
    validate_parameter_grid_size,
)
from algotrading.evaluation.robustness import (
    evaluate_train_test,
    evaluate_walk_forward,
    make_train_test_split,
    make_walk_forward_splits,
)

__all__ = [
    "count_parameter_combinations",
    "evaluate_train_test",
    "evaluate_walk_forward",
    "make_train_test_split",
    "make_walk_forward_splits",
    "validate_parameter_grid_size",
]
