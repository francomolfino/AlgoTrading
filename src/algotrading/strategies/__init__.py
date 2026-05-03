"""Estrategias simples que generan senales long-only 0/1."""

from algotrading.strategies.breakout import generate_breakout_signals
from algotrading.strategies.buy_and_hold import generate_buy_and_hold_signals
from algotrading.strategies.moving_average import generate_sma_crossover_signals
from algotrading.strategies.rsi import calculate_rsi, generate_rsi_signals
from algotrading.strategies.registry import StrategySpec, build_default_strategy_specs
from algotrading.strategies.trend_filter import generate_trend_filter_signals

__all__ = [
    "StrategySpec",
    "build_default_strategy_specs",
    "calculate_rsi",
    "generate_breakout_signals",
    "generate_buy_and_hold_signals",
    "generate_rsi_signals",
    "generate_sma_crossover_signals",
    "generate_trend_filter_signals",
]
