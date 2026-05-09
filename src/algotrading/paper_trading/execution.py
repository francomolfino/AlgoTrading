from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from algotrading.paper_trading.data_provider import MarketEventProvider
from algotrading.paper_trading.models import Bar, MarketEvent, MarketEventType


@dataclass(frozen=True)
class ExecutionLoopConfig:
    max_events: int | None = None
    stop_on_provider_error: bool = True
    stop_on_handler_error: bool = True

    def __post_init__(self) -> None:
        if self.max_events is not None and self.max_events <= 0:
            raise ValueError("max_events debe ser positivo o None.")


@dataclass(frozen=True)
class ExecutionLoopError:
    timestamp: pd.Timestamp
    event_type: str
    symbol: str
    error_type: str
    message: str


@dataclass(frozen=True)
class ExecutionLoopResult:
    events_seen: int
    bars_seen: int
    heartbeats_seen: int
    errors: tuple[ExecutionLoopError, ...]
    stopped_reason: str

    def errors_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "timestamp": error.timestamp,
                    "event_type": error.event_type,
                    "symbol": error.symbol,
                    "error_type": error.error_type,
                    "message": error.message,
                }
                for error in self.errors
            ],
            columns=["timestamp", "event_type", "symbol", "error_type", "message"],
        )


class SafeExecutionLoop:
    """Loop defensivo para replay/live sin depender de un broker real.

    El loop solo orquesta eventos. La logica de estrategia, riesgo y broker se
    enchufa via callbacks, lo que permite probar cada parte por separado.
    """

    def __init__(
        self,
        provider: MarketEventProvider,
        on_bar: Callable[[Bar], None] | None = None,
        on_event: Callable[[MarketEvent], None] | None = None,
        config: ExecutionLoopConfig | None = None,
    ):
        self.provider = provider
        self.on_bar = on_bar
        self.on_event = on_event
        self.config = config or ExecutionLoopConfig()

    def run(self) -> ExecutionLoopResult:
        events_seen = 0
        bars_seen = 0
        heartbeats_seen = 0
        errors: list[ExecutionLoopError] = []
        stopped_reason = "provider_finished"

        try:
            for event in self.provider.iter_events():
                events_seen += 1
                should_stop = False

                try:
                    if self.on_event is not None:
                        self.on_event(event)

                    if event.event_type == MarketEventType.BAR:
                        if event.bar is None:
                            raise ValueError("Evento BAR sin bar.")
                        bars_seen += 1
                        if self.on_bar is not None:
                            self.on_bar(event.bar)
                    elif event.event_type == MarketEventType.HEARTBEAT:
                        heartbeats_seen += 1
                    elif event.event_type == MarketEventType.PROVIDER_ERROR:
                        errors.append(_event_error(event, "ProviderError", event.message))
                        should_stop = self.config.stop_on_provider_error
                    elif event.event_type == MarketEventType.MARKET_CLOSED:
                        stopped_reason = "market_closed"
                        should_stop = True
                    else:
                        errors.append(
                            _event_error(
                                event,
                                "UnsupportedEvent",
                                f"Evento no soportado: {event.event_type}",
                            )
                        )
                except Exception as exc:
                    errors.append(_event_error(event, type(exc).__name__, str(exc)))
                    should_stop = self.config.stop_on_handler_error

                if (
                    self.config.max_events is not None
                    and events_seen >= self.config.max_events
                    and not should_stop
                ):
                    stopped_reason = "max_events"
                    should_stop = True

                if should_stop:
                    if stopped_reason == "provider_finished":
                        stopped_reason = "error" if errors else "stopped"
                    break
        except Exception as exc:
            errors.append(
                ExecutionLoopError(
                    timestamp=pd.Timestamp.utcnow().tz_localize(None),
                    event_type="provider_exception",
                    symbol=getattr(self.provider, "symbol", ""),
                    error_type=type(exc).__name__,
                    message=str(exc),
                )
            )
            stopped_reason = "provider_exception"

        return ExecutionLoopResult(
            events_seen=events_seen,
            bars_seen=bars_seen,
            heartbeats_seen=heartbeats_seen,
            errors=tuple(errors),
            stopped_reason=stopped_reason,
        )


def _event_error(event: MarketEvent, error_type: str, message: str) -> ExecutionLoopError:
    return ExecutionLoopError(
        timestamp=event.timestamp,
        event_type=event.event_type.value,
        symbol=event.symbol,
        error_type=error_type,
        message=message,
    )
