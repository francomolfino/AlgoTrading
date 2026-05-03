from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from algotrading.strategies.breakout import generate_breakout_signals
from algotrading.strategies.buy_and_hold import generate_buy_and_hold_signals
from algotrading.strategies.moving_average import generate_sma_crossover_signals
from algotrading.strategies.rsi import generate_rsi_signals
from algotrading.strategies.trend_filter import generate_trend_filter_signals

StrategyFunction = Callable[..., pd.DataFrame]


@dataclass(frozen=True)
class StrategySpec:
    name: str
    function: StrategyFunction
    parameters: dict[str, int | float | str]


def build_default_strategy_specs(
    price_column: str = "adj_close",
    sma_fast: int = 50,
    sma_slow: int = 200,
    rsi_window: int = 14,
    rsi_oversold: float = 30,
    rsi_overbought: float = 70,
    breakout_entry_window: int = 55,
    breakout_exit_window: int = 20,
    trend_fast: int = 20,
    trend_slow: int = 100,
    trend_window: int = 200,
) -> list[StrategySpec]:
    return [
        StrategySpec(
            name="buy_and_hold",
            function=generate_buy_and_hold_signals,
            parameters={},
        ),
        StrategySpec(
            name=f"sma_cross_{sma_fast}_{sma_slow}",
            function=generate_sma_crossover_signals,
            parameters={
                "fast_window": sma_fast,
                "slow_window": sma_slow,
                "price_column": price_column,
            },
        ),
        StrategySpec(
            name=f"rsi_{rsi_window}_{int(rsi_oversold)}_{int(rsi_overbought)}",
            function=generate_rsi_signals,
            parameters={
                "window": rsi_window,
                "oversold": rsi_oversold,
                "overbought": rsi_overbought,
                "price_column": price_column,
            },
        ),
        StrategySpec(
            name=f"breakout_{breakout_entry_window}_{breakout_exit_window}",
            function=generate_breakout_signals,
            parameters={
                "entry_window": breakout_entry_window,
                "exit_window": breakout_exit_window,
                "price_column": price_column,
            },
        ),
        StrategySpec(
            name=f"trend_filter_{trend_fast}_{trend_slow}_{trend_window}",
            function=generate_trend_filter_signals,
            parameters={
                "fast_window": trend_fast,
                "slow_window": trend_slow,
                "trend_window": trend_window,
                "price_column": price_column,
            },
        ),
    ]
