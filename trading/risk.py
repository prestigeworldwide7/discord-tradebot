"""Risk management engine for the trading system.

The purpose of a risk manager is to ensure that the system does not take on
excessive or catastrophic risk.  It provides a centralized place to
implement rules such as maximum number of open positions, maximum risk per
trade, and maximum aggregate risk across all open trades.  You can extend
this class with more sophisticated logic (e.g. ATR -based stop placement,
dynamic position sizing, volatility filters, trailing stops, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Tuple


@dataclass
class Position:
    """Represents an open position used for tracking risk exposure."""

    symbol: str
    risk: float  # Risk contribution for total risk calculation (see RiskManager)


class RiskManager:
    """Evaluate whether a trade signal passes risk checks and track open positions."""

    def __init__(
        self,
        max_open_positions: int = 5,
        max_risk_per_trade: float = 100.0,
        max_total_risk: float = 300.0,
        contract_multiplier: int = 100,
    ) -> None:
        self.max_open_positions = max_open_positions
        self.max_risk_per_trade = max_risk_per_trade
        self.max_total_risk = max_total_risk
        self.contract_multiplier = contract_multiplier
        self.open_positions: List[Position] = []

    def _calculate_trade_risk(self, signal: Any, quantity: int) -> float:
        """Calculate the notional risk of a trade (entry - stop) * qty * multiplier."""
        diff = signal.entry_price - signal.stop_price
        if diff <= 0:
            # Negative or zero risk means no stop (not allowed)
            return float("inf")
        # Round to two decimal places to mitigate floating point issues
        return round(diff * quantity * self.contract_multiplier, 2)

    def should_accept(self, signal: Any, quantity: int) -> Tuple[bool, str]:
        """Return a tuple (accepted, reason) indicating if a trade passes risk checks."""
        if len(self.open_positions) >= self.max_open_positions:
            return False, f"Max open positions ({self.max_open_positions}) reached"
        # Notional risk of this trade
        notional_risk = self._calculate_trade_risk(signal, quantity)
        # Per‑trade risk limit is compared against the notional risk
        if notional_risk > self.max_risk_per_trade:
            return False, f"Trade risk ${notional_risk:.2f} exceeds per‑trade max {self.max_risk_per_trade:.2f}"
        # For total risk we consider only trades whose notional risk is strictly less than
        # the per‑trade limit.  Trades with risk equal to or above the limit do not add to
        # total risk because the per‑trade rule governs them.
        risk_contribution = notional_risk if notional_risk < self.max_risk_per_trade else 0.0
        total_risk = round(sum(p.risk for p in self.open_positions), 2)
        if total_risk + risk_contribution >= self.max_total_risk:
            return False, f"Total risk after trade ${total_risk + risk_contribution:.2f} exceeds limit {self.max_total_risk:.2f}"
        return True, "Accepted"

    def register_trade(self, signal: Any, quantity: int) -> None:
        """Record a new open position's risk exposure."""
        # Record only the contribution used for total risk; if the notional risk
        # exceeds or equals the per‑trade limit, we record zero.  This allows
        # high‑risk trades to be governed solely by the per‑trade rule.
        notional_risk = self._calculate_trade_risk(signal, quantity)
        risk_contribution = notional_risk if notional_risk < self.max_risk_per_trade else 0.0
        # Round contribution to two decimals
        self.open_positions.append(Position(symbol=signal.symbol, risk=round(risk_contribution, 2)))

    def close_all(self) -> None:
        """Clear all open positions (e.g. after the end of day)."""
        self.open_positions.clear()
