import pandas as pd
import pytest

from algotrading.paper_trading import (
    BreakoutPaperStrategy,
    BuyAndHoldPaperStrategy,
    FakeBroker,
    HistoricalDataProvider,
    MovingAverageCrossoverPaperStrategy,
    OrderSide,
    PaperTradingEngine,
    RSIPaperStrategy,
    RiskManager,
    RiskManagerConfig,
    TrendFilterPaperStrategy,
)
from algotrading.data.schema import ValidationError
from algotrading.paper_trading.models import Order, OrderStatus


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


def test_historical_data_provider_reuses_ohlcv_validation_contract():
    duplicated = _frame([100, 101])
    duplicated.loc[1, "date"] = duplicated.loc[0, "date"]

    with pytest.raises(ValidationError, match="duplicadas"):
        HistoricalDataProvider("SPY", duplicated)


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


def test_risk_manager_caps_target_and_can_round_to_whole_shares():
    risk = RiskManager(
        RiskManagerConfig(
            max_position_fraction=0.5,
            min_trade_value=1.0,
            allow_fractional=False,
        )
    )

    order = risk.create_order_for_target_weight(
        order_id=1,
        timestamp=pd.Timestamp("2024-01-01"),
        symbol="SPY",
        target_weight=1.0,
        current_quantity=0.0,
        price=300.0,
        equity=1_000.0,
    )

    assert order is not None
    assert order.side == OrderSide.BUY
    assert order.quantity == pytest.approx(1.0)


def test_risk_manager_caps_total_exposure():
    risk = RiskManager(
        RiskManagerConfig(
            max_position_fraction=1.0,
            max_total_exposure=0.25,
            min_trade_value=1.0,
        )
    )

    order = risk.create_order_for_target_weight(
        order_id=1,
        timestamp=pd.Timestamp("2024-01-01"),
        symbol="SPY",
        target_weight=1.0,
        current_quantity=0.0,
        price=100.0,
        equity=1_000.0,
    )

    assert order is not None
    assert order.quantity == pytest.approx(2.5)


def test_risk_manager_blocks_after_trade_limit():
    risk = RiskManager(RiskManagerConfig(max_trades_per_day=1, min_trade_value=1.0))

    first = risk.create_order_for_target_weight(
        order_id=1,
        timestamp=pd.Timestamp("2024-01-01"),
        symbol="SPY",
        target_weight=1.0,
        current_quantity=0.0,
        price=100.0,
        equity=1_000.0,
    )
    second = risk.create_order_for_target_weight(
        order_id=2,
        timestamp=pd.Timestamp("2024-01-01"),
        symbol="SPY",
        target_weight=0.0,
        current_quantity=10.0,
        price=100.0,
        equity=1_000.0,
    )

    assert first is not None
    assert second is None
    assert risk.last_blocked_reason == "trade_limit"


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
    assert [event.status for event in broker.order_events[:3]] == [
        OrderStatus.CREATED,
        OrderStatus.SUBMITTED,
        OrderStatus.FILLED,
    ]


def test_fake_broker_rejects_invalid_quantity_and_sell_without_position():
    broker = FakeBroker(initial_cash=1_000, commission_bps=0, slippage_bps=0)
    bar = next(HistoricalDataProvider("SPY", _frame([100])).iter_bars())

    invalid_fill = broker.submit_market_order(
        Order(
            order_id=1,
            timestamp=bar.date,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=0,
        ),
        bar,
    )
    missing_position_fill = broker.submit_market_order(
        Order(
            order_id=2,
            timestamp=bar.date,
            symbol="SPY",
            side=OrderSide.SELL,
            quantity=1,
        ),
        bar,
    )

    assert invalid_fill is None
    assert missing_position_fill is None
    assert [order.status for order in broker.orders] == [
        OrderStatus.REJECTED,
        OrderStatus.REJECTED,
    ]
    assert [order.reason for order in broker.orders] == ["quantity <= 0", "no position"]
    assert [error.error_type for error in broker.error_events] == [
        "OrderRejected",
        "OrderRejected",
    ]


def test_fake_broker_dry_run_records_cancelled_order_without_fill():
    broker = FakeBroker(initial_cash=1_000, commission_bps=0, slippage_bps=0, dry_run=True)
    bar = next(HistoricalDataProvider("SPY", _frame([100])).iter_bars())

    fill = broker.submit_market_order(
        Order(
            order_id=1,
            timestamp=bar.date,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=5,
        ),
        bar,
    )

    assert fill is None
    assert broker.cash == pytest.approx(1_000)
    assert broker.get_position("SPY") == pytest.approx(0)
    assert broker.orders[-1].status == OrderStatus.CANCELLED
    assert broker.orders[-1].reason == "dry_run"
    assert [event.status for event in broker.order_events] == [
        OrderStatus.CREATED,
        OrderStatus.SUBMITTED,
        OrderStatus.CANCELLED,
    ]


def test_fake_broker_can_persist_and_reload_state():
    broker = FakeBroker(initial_cash=1_000, commission_bps=0, slippage_bps=0)
    bar = next(HistoricalDataProvider("SPY", _frame([100])).iter_bars())
    broker.submit_market_order(
        Order(
            order_id=1,
            timestamp=bar.date,
            symbol="SPY",
            side=OrderSide.BUY,
            quantity=5,
        ),
        bar,
    )
    path = "tests/.tmp/broker_state.json"

    broker.save_state(path)
    restored = FakeBroker.load_state(path)

    assert restored.cash == pytest.approx(500)
    assert restored.get_position("SPY") == pytest.approx(5)
    assert len(restored.orders) == 1
    assert len(restored.fills) == 1
    assert len(restored.order_events) == 3


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
    assert result.summary["order_events"] == 3
    assert result.summary["fills"] == 1
    assert result.summary["errors"] == 0
    assert result.summary["final_equity"] == pytest.approx((1_000 / 110) * 120)
    assert not result.order_events.empty
    assert result.errors.empty


def test_rsi_paper_strategy_uses_only_available_history():
    strategy = RSIPaperStrategy(window=2, oversold=60, overbought=80)

    assert strategy.target_weight(_frame([100, 99])) == 0.0
    assert strategy.target_weight(_frame([100, 99, 98, 97])) == 1.0


def test_breakout_paper_strategy_generates_target_from_history():
    strategy = BreakoutPaperStrategy(entry_window=2, exit_window=2)

    assert strategy.target_weight(_frame([100, 101])) == 0.0
    assert strategy.target_weight(_frame([100, 101, 102])) == 1.0


def test_trend_filter_paper_strategy_generates_target_from_history():
    strategy = TrendFilterPaperStrategy(fast_window=2, slow_window=3, trend_window=3)

    assert strategy.target_weight(_frame([100, 101])) == 0.0
    assert strategy.target_weight(_frame([100, 101, 102, 103])) == 1.0


def test_paper_trading_risk_halt_liquidates_and_blocks_new_entries():
    provider = HistoricalDataProvider("SPY", _frame([100, 100, 80, 120, 130]))
    broker = FakeBroker(initial_cash=1_000, commission_bps=0, slippage_bps=0)
    engine = PaperTradingEngine(
        data_provider=provider,
        strategy=BuyAndHoldPaperStrategy(),
        broker=broker,
        risk_manager=RiskManager(
            RiskManagerConfig(min_trade_value=0, max_drawdown_pct=0.10)
        ),
    )

    result = engine.run()

    assert "max_drawdown" in result.account_history["risk_event"].tolist()
    assert result.summary["risk_halt_triggered"] == 1
    assert result.summary["final_position_quantity"] == pytest.approx(0.0)


def test_paper_trading_engine_dry_run_outputs_order_events_without_fills():
    provider = HistoricalDataProvider("SPY", _frame([100, 110, 120]))
    broker = FakeBroker(initial_cash=1_000, commission_bps=0, slippage_bps=0, dry_run=True)
    engine = PaperTradingEngine(
        data_provider=provider,
        strategy=BuyAndHoldPaperStrategy(),
        broker=broker,
        risk_manager=RiskManager(RiskManagerConfig(min_trade_value=0)),
    )

    result = engine.run()

    assert result.summary["dry_run"] == 1
    assert result.summary["fills"] == 0
    assert result.orders.loc[0, "status"] == "cancelled"
    assert result.orders["status"].tolist() == ["cancelled", "cancelled"]
    assert result.order_events["status"].tolist() == [
        "created",
        "submitted",
        "cancelled",
        "created",
        "submitted",
        "cancelled",
    ]
    assert result.account_history.loc[1, "action"] == "dry_run"
