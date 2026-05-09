"""Arquitectura educativa para preparar paper trading."""

from algotrading.paper_trading.broker import FakeBroker
from algotrading.paper_trading.data_provider import (
    FakeLiveDataProvider,
    HistoricalDataProvider,
    MarketDataProvider,
    MarketEventProvider,
    YahooHistoricalDataProvider,
)
from algotrading.paper_trading.engine import PaperTradingEngine, PaperTradingResult
from algotrading.paper_trading.execution import (
    ExecutionLoopConfig,
    ExecutionLoopError,
    ExecutionLoopResult,
    SafeExecutionLoop,
)
from algotrading.paper_trading.models import (
    Bar,
    BrokerError,
    Fill,
    MarketEvent,
    MarketEventType,
    Order,
    OrderEvent,
    OrderSide,
    OrderStatus,
)
from algotrading.paper_trading.risk import RiskManager, RiskManagerConfig
from algotrading.paper_trading.strategy import (
    BreakoutPaperStrategy,
    BuyAndHoldPaperStrategy,
    MovingAverageCrossoverPaperStrategy,
    RSIPaperStrategy,
    TrendFilterPaperStrategy,
)

__all__ = [
    "Bar",
    "BrokerError",
    "BreakoutPaperStrategy",
    "BuyAndHoldPaperStrategy",
    "ExecutionLoopConfig",
    "ExecutionLoopError",
    "ExecutionLoopResult",
    "FakeLiveDataProvider",
    "FakeBroker",
    "Fill",
    "HistoricalDataProvider",
    "MarketDataProvider",
    "MarketEvent",
    "MarketEventProvider",
    "MarketEventType",
    "MovingAverageCrossoverPaperStrategy",
    "Order",
    "OrderEvent",
    "OrderSide",
    "OrderStatus",
    "PaperTradingEngine",
    "PaperTradingResult",
    "RiskManager",
    "RiskManagerConfig",
    "RSIPaperStrategy",
    "SafeExecutionLoop",
    "TrendFilterPaperStrategy",
    "YahooHistoricalDataProvider",
]
