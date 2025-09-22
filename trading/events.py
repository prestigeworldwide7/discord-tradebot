"""Event definitions and a simple event bus.

The trading system is architected around an event driven design.  When the
Discord monitor parses a new trade alert it publishes an :class:`AlertEvent`
to the global :class:`EventBus`.  Downstream components, such as the risk
manager and execution manager, subscribe to these events and react
accordingly.  This decouples the source of events (Discord, CLI, etc.) from
the consumers, allowing each component to focus on its own responsibilities.

This module defines a handful of simple event types as dataclasses and a
minimal event bus capable of synchronous and asynchronous dispatch.  It is
intentionally lightweight; if your application grows more complex you may
wish to replace it with a more full featured pub/sub library.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Type


@dataclass
class BaseEvent:
    """Base class for all events.

    Each event carries a timestamp indicating when it was created.  Subclasses
    may define additional attributes.  Event classes should be immutable
    dataclasses to make it easy to inspect and log their contents.
    """

    timestamp: datetime


@dataclass
class AlertEvent(BaseEvent):
    """Represents a parsed trade alert from Discord.

    Attributes
    ----------
    signal: TradeSignal
        The parsed trade signal containing details such as the symbol,
        strike, option type, expiration date, entry price and stop price.
    raw_message: str
        The original Discord message content for auditing and debugging.
    """

    signal: Any  # Use Any here to avoid circular import; actual type is TradeSignal
    raw_message: str


@dataclass
class OrderEvent(BaseEvent):
    """Represents the submission of an order to the broker.

    Attributes
    ----------
    signal: TradeSignal
        The trade signal that triggered this order.
    response: Dict[str, Any]
        The JSON response returned by the broker API.  This often contains
        order identifiers, status information, or error details.
    """

    signal: Any
    response: Dict[str, Any]


@dataclass
class RiskEvent(BaseEvent):
    """Represents the result of a risk check.

    Attributes
    ----------
    signal: TradeSignal
        The trade signal that was evaluated.
    accepted: bool
        True if the trade passed risk checks and was accepted; False if
        rejected.
    reason: str
        A human readable explanation for the decision.  Useful for logging
        and debugging.
    """

    signal: Any
    accepted: bool
    reason: str


class EventBus:
    """A very simple synchronous/asynchronous event bus.

    Consumers can register callbacks for a particular event type by calling
    :meth:`subscribe`.  When :meth:`publish` is invoked with an event
    instance, the bus invokes all registered callbacks for that event type.
    Callbacks may be regular functions or coroutines; the bus awaits
    coroutine callbacks before returning.  Exceptions raised by subscribers
    are logged but do not stop other subscribers from running.
    """

    def __init__(self) -> None:
        # Mapping of event type to list of subscriber callbacks
        self._subscribers: Dict[Type[BaseEvent], List[Callable[[BaseEvent], Awaitable[None] | None]]] = {}
        self._lock = asyncio.Lock()

    def subscribe(self, event_cls: Type[BaseEvent], handler: Callable[[BaseEvent], Awaitable[None] | None]) -> None:
        """Register a callback for the given event type.

        Parameters
        ----------
        event_cls: Type[BaseEvent]
            The class of event you want to listen for (e.g. AlertEvent).
        handler: Callable[[BaseEvent], Awaitable[None] | None]
            A function or coroutine to call when an event of this type is published.
        """
        # Use list.setdefault to avoid key errors
        handlers = self._subscribers.setdefault(event_cls, [])
        handlers.append(handler)  # type: ignore[arg-type]

    async def publish(self, event: BaseEvent) -> None:
        """Publish an event to all registered subscribers.

        If a subscriber is a coroutine function it will be awaited.  Synchronous
        handlers are executed in the event loop's default executor via
        `asyncio.to_thread` to avoid blocking.  Exceptions are caught and
        logged; other handlers will still run.

        Parameters
        ----------
        event: BaseEvent
            The event instance to broadcast.
        """
        # Acquire a copy of handlers under lock to avoid race conditions if
        # subscribers are added or removed while we're iterating.
        async with self._lock:
            handlers = list(self._subscribers.get(type(event), []))
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(event)
                else:
                    # Offload synchronous handler to thread pool
                    await asyncio.to_thread(handler, event)
            except Exception as exc:  # pragma: no cover - best effort logging
                print(f"Error in event handler {handler}: {exc}")
