from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import pandas as pd


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    SUBMITTED = "submitted"
    FILLED = "filled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class Bar:
    date: pd.Timestamp
    symbol: str
    open: float
    high: float
    low: float
    close: float
    adj_close: float
    volume: float

    def price(self, price_column: str = "adj_close") -> float:
        if price_column not in {"open", "high", "low", "close", "adj_close"}:
            raise ValueError(f"Columna de precio no soportada: {price_column}")
        return float(getattr(self, price_column))

    def to_record(self) -> dict[str, float | str | pd.Timestamp]:
        return {
            "date": self.date,
            "symbol": self.symbol,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "adj_close": self.adj_close,
            "volume": self.volume,
        }


@dataclass(frozen=True)
class Order:
    order_id: int
    timestamp: pd.Timestamp
    symbol: str
    side: OrderSide
    quantity: float
    status: OrderStatus = OrderStatus.SUBMITTED
    reason: str = ""


@dataclass(frozen=True)
class Fill:
    order_id: int
    timestamp: pd.Timestamp
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    notional: float
    commission: float
    slippage_bps: float
