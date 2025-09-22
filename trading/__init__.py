"""Top-level package for the Discord‑TradeStation automated trading system.

This package exposes the core components used by the bot, including event
broadcasting primitives, a robust TradeStation API client, a signal parser
built with Pydantic, a risk management engine, an execution manager, and
emergency control mechanisms.  See the individual modules for more
documentation.
"""

from .events import EventBus, AlertEvent, OrderEvent, RiskEvent  # noqa:F401
from .signal_parser import TradeSignal, SignalParserError  # noqa:F401
from .tradestation_client import TradeStationClient  # noqa:F401
from .risk import RiskManager  # noqa:F401
from .execution import ExecutionManager  # noqa:F401
from .controls import EmergencyControls  # noqa:F401
