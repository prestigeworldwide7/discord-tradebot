"""Emergency controls for the trading system.

Trading systems must have safety valves to cope with unexpected situations
such as API outages, runaway execution, or market anomalies.  This module
provides a simple kill switch and circuit breaker implementation that can
disable trading when triggered.  You can extend these controls to add
time‑based resets, manual override via Discord commands, or integration
with external monitoring services.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from .risk import RiskManager


@dataclass
class EmergencyControls:
    """Encapsulates kill switch and circuit breaker logic."""

    risk_manager: RiskManager
    max_consecutive_failures: int = 3
    trading_enabled: bool = True
    consecutive_failures: int = 0

    def record_failure(self) -> None:
        """Record a failed order submission or other error.

        If the number of consecutive failures exceeds the configured
        threshold trading is disabled and all open positions are cleared.
        """
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.trading_enabled = False
            # Close all positions in the risk manager to reset exposure
            self.risk_manager.close_all()

    def reset_failures(self) -> None:
        """Reset the failure counter (e.g. after a successful order)."""
        self.consecutive_failures = 0

    def is_enabled(self) -> bool:
        """Return True if trading is currently enabled."""
        return self.trading_enabled
