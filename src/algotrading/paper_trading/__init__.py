"""Arquitectura educativa para preparar paper trading."""

from algotrading.paper_trading.broker import FakeBroker
from algotrading.paper_trading.data_provider import HistoricalDataProvider
from algotrading.paper_trading.engine import PaperTradingEngine, PaperTradingResult
from algotrading.paper_trading.models import Bar, Fill, Order, OrderSide, OrderStatus
from algotrading.paper_trading.risk import RiskManager, RiskManagerConfig
from algotrading.paper_trading.strategy import (
    BuyAndHoldPaperStrategy,
    MovingAverageCrossoverPaperStrategy,
)

__all__ = [
    "Bar",
    "BuyAndHoldPaperStrategy",
    "FakeBroker",
    "Fill",
    "HistoricalDataProvider",
    "MovingAverageCrossoverPaperStrategy",
    "Order",
    "OrderSide",
    "OrderStatus",
    "PaperTradingEngine",
    "PaperTradingResult",
    "RiskManager",
    "RiskManagerConfig",
]
