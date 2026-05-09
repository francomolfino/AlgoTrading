import pandas as pd
import pytest

from algotrading.paper_trading import (
    ExecutionLoopConfig,
    FakeLiveDataProvider,
    HistoricalDataProvider,
    MarketDataProvider,
    MarketEvent,
    MarketEventProvider,
    MarketEventType,
    SafeExecutionLoop,
    YahooHistoricalDataProvider,
)


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


def test_historical_provider_implements_bar_and_event_contracts():
    provider = HistoricalDataProvider("SPY", _frame([100, 101]))

    events = list(provider.iter_events())

    assert isinstance(provider, MarketDataProvider)
    assert isinstance(provider, MarketEventProvider)
    assert [event.event_type for event in events] == [
        MarketEventType.BAR,
        MarketEventType.BAR,
    ]
    assert events[0].bar is not None
    assert events[0].bar.close == pytest.approx(100)


def test_yahoo_historical_provider_wraps_download(monkeypatch):
    calls = {}

    def fake_download_ohlcv(symbol, start, end=None, interval="1d"):
        calls.update(
            {
                "symbol": symbol,
                "start": start,
                "end": end,
                "interval": interval,
            }
        )
        return _frame([100, 101])

    monkeypatch.setattr(
        "algotrading.paper_trading.data_provider.download_ohlcv",
        fake_download_ohlcv,
    )

    provider = YahooHistoricalDataProvider(
        symbol="SPY",
        start="2024-01-01",
        end="2024-01-03",
        interval="1d",
    )

    assert calls == {
        "symbol": "SPY",
        "start": "2024-01-01",
        "end": "2024-01-03",
        "interval": "1d",
    }
    assert len(list(provider.iter_bars())) == 2


def test_fake_live_provider_emits_heartbeats_and_market_closed():
    provider = FakeLiveDataProvider(
        "SPY",
        _frame([100, 101, 102]),
        heartbeat_every=2,
    )

    events = list(provider.iter_events())

    assert [event.event_type for event in events] == [
        MarketEventType.BAR,
        MarketEventType.BAR,
        MarketEventType.HEARTBEAT,
        MarketEventType.BAR,
        MarketEventType.MARKET_CLOSED,
    ]
    assert events[-1].message == "historical replay finished"


def test_safe_execution_loop_stops_on_max_events():
    provider = FakeLiveDataProvider(
        "SPY",
        _frame([100, 101, 102]),
        emit_market_closed=False,
    )
    received = []
    loop = SafeExecutionLoop(
        provider=provider,
        on_bar=lambda bar: received.append(bar.close),
        config=ExecutionLoopConfig(max_events=2),
    )

    result = loop.run()

    assert received == [100, 101]
    assert result.events_seen == 2
    assert result.bars_seen == 2
    assert result.stopped_reason == "max_events"
    assert result.errors == ()


def test_safe_execution_loop_records_provider_error_events():
    class BrokenProvider:
        symbol = "SPY"

        def iter_events(self):
            yield MarketEvent(
                timestamp=pd.Timestamp("2024-01-01"),
                event_type=MarketEventType.PROVIDER_ERROR,
                symbol="SPY",
                message="feed unavailable",
            )

    result = SafeExecutionLoop(BrokenProvider()).run()

    assert result.stopped_reason == "error"
    assert len(result.errors) == 1
    assert result.errors[0].error_type == "ProviderError"
    assert result.errors[0].message == "feed unavailable"


def test_safe_execution_loop_records_handler_errors():
    provider = FakeLiveDataProvider("SPY", _frame([100]), emit_market_closed=False)

    def broken_handler(_bar):
        raise RuntimeError("handler exploded")

    result = SafeExecutionLoop(provider=provider, on_bar=broken_handler).run()

    assert result.stopped_reason == "error"
    assert result.events_seen == 1
    assert result.bars_seen == 1
    assert result.errors[0].error_type == "RuntimeError"
