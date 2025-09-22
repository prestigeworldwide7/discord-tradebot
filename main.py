"""Application entry point for the automated trading bot.

This script orchestrates the various components of the trading system.
It loads configuration from a YAML file, applies environment variable
substitution, initializes the event bus, risk manager, API client and
execution manager, and starts the Discord monitoring client.  It also
registers simple handlers for risk and order events to implement a
rudimentary circuit breaker.

Usage
-----

Install dependencies and run the bot:

```
pip install -r requirements.txt
export DISCORD_TOKEN=...  # from your Discord developer portal
python main.py
```

Alternatively you can place credentials and configuration in an `.env` file
and a `config.yaml` as described in the README.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

import yaml
import discord

from trading import (
    EventBus,
    OrderEvent,
    RiskEvent,
    AlertEvent,
    TradeStationClient,
    DiscordMonitor,
    RiskManager,
    ExecutionManager,
    EmergencyControls,
)


def load_config(path: str | Path) -> Dict[str, Any]:
    """Load configuration from a YAML file with environment variable expansion.

    Supports syntax of the form ``${VAR}`` and ``${VAR:-default}``, which are
    replaced with the value of the environment variable ``VAR`` or the
    provided default if the variable is unset.  Nested dictionaries and
    lists are traversed recursively.
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    pattern = re.compile(r"\$\{([^}]+)\}")

    def substitute(value: Any) -> Any:
        if isinstance(value, str):
            def replacer(match: re.Match[str]) -> str:
                expr = match.group(1)
                if ":-" in expr:
                    var, default = expr.split(":-", 1)
                    return os.getenv(var, default)
                return os.getenv(expr, "")
            return pattern.sub(replacer, value)
        elif isinstance(value, dict):
            return {k: substitute(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [substitute(v) for v in value]
        else:
            return value
    return substitute(data)


async def main_async() -> None:
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s:%(name)s: %(message)s",
    )
    # Load configuration file
    config_path = Path(__file__).with_name("config.yaml")
    config = load_config(config_path)
    # Instantiate components
    bus = EventBus()
    ts_config = config.get("tradestation", {})
    ts_client = TradeStationClient(ts_config)
    risk_cfg = config.get("risk", {})
    risk_manager = RiskManager(**risk_cfg)
    exec_quantity = int(config.get("trade", {}).get("quantity", 1))
    exec_manager = ExecutionManager(bus, ts_client, risk_manager, quantity=exec_quantity)
    controls_cfg = config.get("controls", {})
    controls = EmergencyControls(
        risk_manager=risk_manager,
        max_consecutive_failures=int(controls_cfg.get("max_consecutive_failures", 3)),
    )
    # Event handlers to implement circuit breaker
    async def on_risk(event: RiskEvent) -> None:
        # Reset failure counter on accepted trades; do nothing otherwise
        if event.accepted:
            controls.reset_failures()

    async def on_order(event: OrderEvent) -> None:
        # Record a failure if the response contains an error
        if isinstance(event.response, dict) and event.response.get("error"):
            controls.record_failure()
        else:
            controls.reset_failures()

    bus.subscribe(RiskEvent, on_risk)
    bus.subscribe(OrderEvent, on_order)
    # Start Discord monitor
    discord_cfg = config.get("discord", {})
    channel_id = discord_cfg.get("channel_id")
    token = os.getenv("DISCORD_TOKEN") or discord_cfg.get("token")
    if not token:
        raise RuntimeError("DISCORD_TOKEN not provided in environment or config")
    # Initialise Discord bot with privileged intents to read message content
    intents = discord.Intents.default()
    intents.message_content = True
    monitor = DiscordMonitor(channel_id=int(channel_id), bus=bus, intents=intents)
    # Handle kill switch: if trading disabled, do not publish events
    async def wrap_publish(event: Any) -> None:
        if isinstance(event, AlertEvent) and not controls.is_enabled():
            # Ignore new alerts when trading is disabled
            logging.warning("Trading disabled; ignoring incoming alert for %s", event.signal.symbol)
            return
        await bus.publish(event)
    # Override bus.publish with wrapper for kill switch
    bus.publish = wrap_publish  # type: ignore[assignment]
    # Run the Discord bot until cancelled
    await monitor.start(token)


def main() -> None:
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logging.info("Bot interrupted by user")


if __name__ == "__main__":
    main()
