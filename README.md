# Discord‑TradeStation Automated Trading System

This repository provides an end‑to‑end example of how to build an automated
options trading bot that listens for alerts on Discord, performs risk
assessment, and submits bracket orders to the [TradeStation](https://tradestation.github.io/)
brokerage API.  The goal of this project is not to encourage automated
trading but to demonstrate best practices in system design, configuration
management and safety for educational purposes.

## Highlights

- **Event‑driven architecture** – a central :class:`EventBus` decouples
  components.  Discord monitoring, risk management and order execution
  communicate via events, making it easy to swap out implementations or
  extend functionality.
- **Structured message parsing** – incoming messages are parsed into
  :class:`TradeSignal` objects using Pydantic.  Dates are normalised and
  validated to ensure expirations are always in the future.
- **Robust API client** – the :class:`TradeStationClient` handles OAuth2
  token refresh and can submit bracket orders for options via a single
  API call.  Account queries are supported to verify configuration.
- **Risk management** – a :class:`RiskManager` enforces limits on the
  number of open positions, per‑trade risk and aggregate risk.  It tracks
  open exposures and can be extended with more sophisticated logic such as
  ATR‑based stops or volatility filters.
- **Emergency controls** – a kill switch and simple circuit breaker
  disable trading after repeated failures and clear open exposures.
- **Configurable via YAML** – non‑secret settings live in `config.yaml`.
  Secrets such as tokens and API keys are injected via environment
  variables.  Placeholder syntax ``${VAR}`` and ``${VAR:-default}``
  supports environment expansion.
- **Testable components** – core modules are factored into discrete files
  under the `trading/` package, with basic tests in the `tests/` folder
  demonstrating how to exercise the parser and risk logic.

## Repository Structure

```
discord-tradestation-bot/
├── main.py               # Application entry point
├── config.yaml           # YAML configuration with environment interpolation
├── example.env           # Template .env file for sensitive variables
├── requirements.txt      # Python dependencies
├── trading/              # Package containing core modules
│   ├── __init__.py       # Package exports
│   ├── discord_monitor.py # Discord client that publishes AlertEvents
│   ├── signal_parser.py  # Pydantic TradeSignal model and parsing logic
│   ├── tradestation_client.py # REST client with token refresh and order submission
│   ├── risk.py           # RiskManager for position and exposure limits
│   ├── execution.py      # ExecutionManager subscribing to alerts and placing orders
│   ├── events.py         # Event definitions and EventBus implementation
│   └── controls.py       # EmergencyControls for kill switch / circuit breaker
└── tests/
    ├── test_parser.py    # Unit tests for the signal parser
    ├── test_risk.py      # Unit tests for risk management
    └── test_integration.py # Example integration tests (skeleton)
```

## Prerequisites

* **Python 3.9+** – the code uses modern Python features such as type hints and
  asynchronous I/O.
* **TradeStation developer account** – create an application on the
  TradeStation developer portal, enable paper trading, and obtain a
  refresh token for your account.
* **Discord bot** – register a bot on the [Discord Developer Portal](https://discord.com/developers/applications),
  enable the `message_content` intent, and invite it to the server/channel
  from which you receive trading signals.

## Installation

Clone the repository and install dependencies:

```bash
git clone <your fork>
cd discord-tradestation-bot
pip install -r requirements.txt
```

You may wish to create and activate a virtual environment beforehand.

## Configuration

1. Copy `example.env` to `.env` and fill in the required secrets (Discord
   token, TradeStation credentials, etc.).  Environment variables defined
   in `.env` are automatically loaded if you install [python‑dotenv](https://pypi.org/project/python-dotenv/) or call
   `load_dotenv()` yourself.
2. Review `config.yaml` and adjust parameters such as channel ID, risk
   limits, trade quantity and circuit breaker settings.  You can also set
   these values via environment variables using the `${VAR}` syntax.

**Important:** Do **not** commit your `.env` file or any credentials to
version control.  Secrets should be supplied via environment variables only.

### Environment Variables

The following variables are typically required (see `config.yaml`):

| Variable             | Description                                                           |
|----------------------|-----------------------------------------------------------------------|
| `DISCORD_TOKEN`      | Your Discord bot token                                                |
| `DISCORD_CHANNEL_ID` | Channel ID to listen for alerts                                       |
| `TS_CLIENT_ID`       | TradeStation application client ID                                    |
| `TS_CLIENT_SECRET`   | TradeStation application client secret                                |
| `TS_ACCOUNT_KEY`     | The account key for your brokerage account                            |
| `TS_REDIRECT_URI`    | Redirect URI registered with your TradeStation application            |
| `TS_REFRESH_TOKEN`   | Refresh token obtained via the OAuth2 authorization flow              |
| `TS_BASE_URL`        | Optional override for the API base URL; defaults to the simulator     |

## Running the Bot

Once dependencies are installed and configuration is in place, run:

```bash
python main.py
```

The bot will connect to Discord and log messages as it receives trade
alerts.  When a valid alert is parsed it passes through the risk manager
before being submitted to the TradeStation API as a bracket order.  Risk
and order events are logged and the emergency controls will disable
trading if repeated errors occur.

### Testing Mode

Point the API to the simulator (`https://sim-api.tradestation.com/v3`) to
practice without risking real money.  You can adjust risk parameters in
`config.yaml` to extremely low values while testing to ensure your code
behaves as expected.

## Notes & Limitations

* **Use at your own risk** – This repository is for educational purposes.  It
  is not financial advice and comes with no guarantees.  Thoroughly test
  your system in a simulator before considering live deployment.
* **No slippage or fill logic** – The execution manager assumes orders are
  filled immediately at your limit price.  Real markets may differ.
* **API stability** – TradeStation may change their API endpoints or
  authentication flow.  Always refer to the official documentation and
  update this client accordingly.
* **Time zones** – Expiration dates without a year roll forward to the
  future relative to your system's local time zone.  Adjust parsing if
  your requirements differ.

## Contributing

Contributions are welcome!  Feel free to open issues or pull requests with
bug fixes, improvements or suggestions.

## License

This project is licensed under the MIT License.  See the `LICENSE` file
for details.

## Contributing

Contributions are welcome!  Feel free to open issues or pull requests with
bug fixes, improvements or suggestions.

## License

This project is licensed under the MIT License.  See the `LICENSE` file
for details.
