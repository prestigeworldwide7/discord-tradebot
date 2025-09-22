"""Discord monitoring client.

This module defines :class:`DiscordMonitor`, a thin wrapper around
`discord.Client` which listens to a specific channel for trade alerts,
parses them into :class:`TradeSignal` objects, and publishes
:class:`AlertEvent`s to the system event bus.  It can be extended to
support slash commands or additional administrative features.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any

import discord

from .events import AlertEvent, EventBus
from .signal_parser import parse_discord_message, SignalParserError


class DiscordMonitor(discord.Client):
    """Discord bot that parses alert messages and dispatches events."""

    def __init__(self, channel_id: int, bus: EventBus, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.channel_id = channel_id
        self.bus = bus
        self.logger = logging.getLogger("discord_monitor")

    async def on_ready(self) -> None:
        self.logger.info(f"Connected to Discord as {self.user}")

    async def on_message(self, message: discord.Message) -> None:
        # Ignore messages from bots
        if message.author.bot:
            return
        # Only process messages from the configured channel
        if message.channel.id != self.channel_id:
            return
        content = message.content
        try:
            signal = parse_discord_message(content)
        except SignalParserError as exc:
            self.logger.debug(f"Failed to parse message: {exc}")
            return
        # Publish alert event
        await self.bus.publish(
            AlertEvent(timestamp=datetime.utcnow(), signal=signal, raw_message=content)
        )
