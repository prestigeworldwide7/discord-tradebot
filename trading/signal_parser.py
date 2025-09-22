"""Signal parsing and validation.

This module defines the :class:`TradeSignal` model using Pydantic for
declarative validation and conversion of trade alerts into structured data.
It exposes a single function, :func:`parse_discord_message`, which accepts
free form Discord messages and attempts to produce a :class:`TradeSignal`.

Examples
--------

>>> from trading.signal_parser import parse_discord_message
>>> signal = parse_discord_message("AAPL - $250 CALLS EXPIRATION 10/10 $1.29 STOP LOSS AT $1.00")
>>> signal.symbol
'AAPL'
>>> signal.strike
250.0
>>> signal.option_type
'Call'
>>> signal.expiration_date.isoformat()
'2025-10-10'
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Tuple

from dateutil import parser as date_parser
from pydantic import BaseModel, validator


class SignalParserError(Exception):
    """Raised when a Discord message cannot be parsed into a trade signal."""


class TradeSignal(BaseModel):
    """Structured representation of a trade alert.

    Attributes
    ----------
    symbol: str
        The underlying equity symbol (e.g. ``AAPL``).  Always upper -cased.
    strike: float
        The option strike price.
    option_type: str
        Either ``Call`` or ``Put``.
    expiration_date: date
        The option expiration date.  Always a date in the future.
    entry_price: float
        The desired limit price to pay per contract.
    stop_price: float
        The stop -loss trigger price per contract.
    raw_message: str
        The original Discord message text.
    """

    symbol: str
    strike: float
    option_type: str
    expiration_date: date
    entry_price: float
    stop_price: float
    raw_message: str

    @validator("symbol")
    def _upper_symbol(cls, v: str) -> str:
        return v.upper()

    @validator("option_type")
    def _normalize_option_type(cls, v: str) -> str:
        v = v.strip().lower()
        if v.startswith("c"):
            return "Call"
        elif v.startswith("p"):
            return "Put"
        raise ValueError("option_type must start with 'C' or 'P'")

    @validator("expiration_date")
    def _future_date(cls, v: date) -> date:
        if v <= date.today():
            raise ValueError("expiration_date must be in the future")
        return v


def _normalize_expiration(expiry_str: str) -> date:
    """Convert a date string into a future date.

    Accepts formats like '10/10', '10/10/25', or '2025-10-10'.  If the
    provided date lacks a year, it is interpreted as a date in the future
    relative to today.  If the parsed date is on or before today the year is
    incremented by one.
    """
    # If it looks like YYYY-MM-DD use the dateutil parser directly
    try:
        dt = date_parser.parse(expiry_str, fuzzy=False).date()
    except (ValueError, OverflowError):
        # We might be dealing with MM/DD or MM/DD/YY
        parts = expiry_str.split("/")
        if len(parts) not in (2, 3):
            raise ValueError(f"Invalid expiration format: {expiry_str}")
        month, day = map(int, parts[:2])
        if len(parts) == 3:
            year = int(parts[2])
            if year < 100:
                year += 2000
        else:
            year = date.today().year
        dt = date(year, month, day)
    # Roll over if date is not strictly in the future
    today = date.today()
    if dt <= today:
        dt = date(dt.year + 1, dt.month, dt.day)
    return dt


def parse_discord_message(message: str) -> TradeSignal:
    """Parse a Discord message into a :class:`TradeSignal`.

    This function strips custom emoji and mentions, normalises whitespace,
    extracts the expected fields with a regular expression, and validates
    them using the :class:`TradeSignal` Pydantic model.  If parsing fails a
    :class:`SignalParserError` is raised.

    Parameters
    ----------
    message: str
        The raw Discord message content.

    Returns
    -------
    TradeSignal
        A validated trade signal.

    Raises
    ------
    SignalParserError
        If the message does not conform to the expected pattern or fails
        validation.
    """
    # Remove emoji/mentions
    cleaned = re.sub(r"<[^>]+>", "", message)
    cleaned = " ".join(cleaned.split())
    pattern = (
        r"(?P<symbol>[A-Za-z]+)\s*-\s*\$(?P<strike>[0-9]+(?:\.[0-9]+)?)\s*"
        r"(?P<otype>CALLS?|PUTS?)\s*"
        r"EXPIRATION\s*(?P<expiry>[0-9/\-]+)\s*"
        r"\$(?P<entry>[0-9]+(?:\.[0-9]+)?)\s*"
        r"STOP\s*LOSS\s*AT\s*\$(?P<stop>[0-9]+(?:\.[0-9]+)?)"
    )
    m = re.search(pattern, cleaned, re.IGNORECASE)
    if not m:
        raise SignalParserError(f"Message does not match expected pattern: {message!r}")
    groups = m.groupdict()
    try:
        expiration = _normalize_expiration(groups["expiry"])
    except ValueError as exc:
        raise SignalParserError(str(exc))
    try:
        signal = TradeSignal(
            symbol=groups["symbol"],
            strike=float(groups["strike"]),
            option_type=groups["otype"],
            expiration_date=expiration,
            entry_price=float(groups["entry"]),
            stop_price=float(groups["stop"]),
            raw_message=message,
        )
    except Exception as exc:
        raise SignalParserError(str(exc))
    return signal
