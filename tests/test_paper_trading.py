import pandas as pd
import pytest

from algotrading.paper_trading import (
    BuyAndHoldPaperStrategy,
    FakeBroker,
    HistoricalDataProvider,
    MovingAverageCrossoverPaperStrategy,
    OrderSide,
    PaperTradingEngine,
    RiskManager,
    RiskManagerConfig,
)
from algotrading.paper_trading.models import Order


def _frame(prices):
    return pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=len(prices), freq="D"),
            "open": prices,
            "high": prices,
            "low": prices,
            "close": prices,
            "adj_close": prices,
            "volume": [100] * len(prices),
        }
    )


def test_historical_data_provider_yields_sorted_bars():
    frame = _frame([100, 101, 102]).sort_values("date", ascending=False)
    provider = HistoricalDataProvider("SPY", frame)

    bars = list(provider.iter_bars())

    assert [bar.date for bar in bars] == list(pd.date_range("2024-01-01", periods=3, freq="D"))
    assert bars[0].symbol == "SPY"
    assert bars[0].price("adj_close") == 100


def test_moving_average_paper_strategy_waits_for_slow_window():
    strategy = MovingAverageCrossoverPaperStrategy(fast_window=2, slow_window=3)

    assert strategy.target_weight(_frame([10, 11])) == 0.0
    assert strategy.target_weight(_frame([10, 11, 12])) == 1.0


def test_risk_manager_creates_buy_and_sell_orders_from_target_weight():
    risk = RiskManager(RiskManagerConfig(max_position_fraction=1.0, min_trade_value=1.0))

    buy = risk.create_order_for_target_weight(
        order_id=1,
        timestamp=pd.Timestamp("2024-01-01"),
        symbol="SPY",
        target_weight=1.0,
        current_quantity=0.0,
        price=100.0,
        equity=1_000.0,
    )
    sell = risk.create_order_for_target_weight(
        order_id=2,
        timestamp=pd.Timestamp("2024-01-02"),
        symbol="SPY",
        target_weight=0.0,
        current_quantity=10.0,
        price=100.0,
        equity=1_000.0,
    )

    assert buy is not None
    assert buy.side == OrderSide.BUY
    assert buy.quantity == pytest.approx(10.0)
    assert sell is not None
    assert sell.side == OrderSide.SELL
    assert sell.quantity == pytest.approx(10.0)


def test_risk_manager_rejects_short_targets():
    risk = RiskManager()

    with pytest.raises(ValueError, match="short"):
        risk.create_order_for_target_weight(
            order_id=1,
            timestamp=pd.Timestamp("2024-01-01"),
            symbol="SPY",
            target_weight=-1.0,
            current_quantity=0.0,
            price=100.0,
            equity=1_000.0,
        )


def test_fake_broker_fills_buy_and_sell_with_costs():
    broker = FakeBroker(initial_cash=1_000, commission_bps=10, slippage_bps=10)
    bar = next(HistoricalDataProvider("SPY", _frame([100])).iter_bars())

    buy_fill = broker.submit_market_order(
        Order(
            order_id=1,
            timestamp=bar.date,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=5,
        ),
        bar,
    )
    sell_fill = broker.submit_market_order(
        Order(
            order_id=2,
            timestamp=bar.date,
            symbol="SPY",
            side=OrderSide.SELL,
            quantity=2,
        ),
        bar,
    )

    assert buy_fill is not None
    assert buy_fill.price == pytest.approx(100.1)
    assert broker.get_position("SPY") == pytest.approx(3.0)
    assert sell_fill is not None
    assert sell_fill.price == pytest.approx(99.9)
    assert len(broker.fills) == 2


def test_paper_trading_engine_executes_target_on_next_bar():
    provider = HistoricalDataProvider("SPY", _frame([100, 110, 120]))
    broker = FakeBroker(initial_cash=1_000, commission_bps=0, slippage_bps=0)
    engine = PaperTradingEngine(
        data_provider=provider,
        strategy=BuyAndHoldPaperStrategy(),
        broker=broker,
        risk_manager=RiskManager(RiskManagerConfig(min_trade_value=0)),
    )

    result = engine.run()

    assert result.account_history.loc[0, "position_quantity"] == 0
    assert result.account_history.loc[1, "action"] == "buy"
    assert result.account_history.loc[1, "position_quantity"] == pytest.approx(1_000 / 110)
    assert result.summary["orders"] == 1
    assert result.summary["fills"] == 1
    assert result.summary["final_equity"] == pytest.approx((1_000 / 110) * 120)
