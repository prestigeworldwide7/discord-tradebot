"""Execution manager for the trading system.

The execution manager bridges the gap between parsed signals, risk
assessment, and order submission.  It subscribes to :class:`AlertEvent`
events on the event bus, uses a :class:`RiskManager` to decide whether
trades should be accepted, and if so instructs a :class:`TradeStationClient`
to place bracket orders.  It publishes :class:`RiskEvent` and
:class:`OrderEvent` events to inform other components of the outcome.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from .events import AlertEvent, EventBus, OrderEvent, RiskEvent
from .risk import RiskManager
from .tradestation_client import TradeStationClient


class ExecutionManager:
    """Handle execution of trade signals subject to risk checks."""

    def __init__(self, bus: EventBus, ts_client: TradeStationClient, risk: RiskManager, quantity: int = 1) -> None:
        self.bus = bus
        self.ts_client = ts_client
        self.risk = risk
        self.quantity = quantity
        # Subscribe to AlertEvents
        self.bus.subscribe(AlertEvent, self.handle_alert)

    async def handle_alert(self, event: AlertEvent) -> None:
        """Handle a new alert by performing risk checks and placing an order if permitted."""
        signal = event.signal
        accepted, reason = self.risk.should_accept(signal, self.quantity)
        # Publish risk event
        await self.bus.publish(
            RiskEvent(timestamp=datetime.utcnow(), signal=signal, accepted=accepted, reason=reason)
        )
        if not accepted:
            return
        # Risk accepted: attempt to submit order in executor to avoid blocking
        loop = asyncio.get_running_loop()
        try:
            response = await loop.run_in_executor(
                None, self.ts_client.submit_bracket_order, signal, self.quantity
            )
        except Exception as exc:
            # On failure, still publish an order event with error details
            await self.bus.publish(
                OrderEvent(timestamp=datetime.utcnow(), signal=signal, response={"error": str(exc)})
            )
            return
        # Register position in risk manager (we assume the order will fill; you could also wait for confirmation)
        self.risk.register_trade(signal, self.quantity)
        await self.bus.publish(
            OrderEvent(timestamp=datetime.utcnow(), signal=signal, response=response)
        )
