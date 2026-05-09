"""Sistema simple de experimentos reproducibles."""

from algotrading.experiments.compare import compare_experiments, find_experiment_dirs
from algotrading.experiments.runner import (
    ExperimentRunResult,
    build_strategy_spec,
    load_experiment_config,
    run_experiment,
    run_experiment_config,
)

__all__ = [
    "ExperimentRunResult",
    "build_strategy_spec",
    "compare_experiments",
    "find_experiment_dirs",
    "load_experiment_config",
    "run_experiment",
    "run_experiment_config",
]
