"""Backtesting educativo, simple y long-only."""

from algotrading.backtesting.engine import BacktestConfig, BacktestResult, run_backtest
from algotrading.backtesting.correctness_audit import (
    BacktestCorrectnessAuditResult,
    CorrectnessCheck,
    run_backtest_correctness_audit,
)

__all__ = [
    "BacktestConfig",
    "BacktestCorrectnessAuditResult",
    "BacktestResult",
    "CorrectnessCheck",
    "run_backtest",
    "run_backtest_correctness_audit",
]
