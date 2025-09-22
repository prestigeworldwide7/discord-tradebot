"""Minimal TradeStation REST API client.

This client encapsulates interactions with the TradeStation REST API,
including OAuth2 token refresh, fetching account information, and
submitting bracket orders for options.  It is deliberately lightweight and
stateless beyond token caching; you can layer additional functionality on
top as needed.

The API endpoints used here are documented at
https://tradestation.github.io/api-docs/ .  You should consult the
documentation for the most up -to date details on request/response formats
and additional capabilities such as fetching positions or order status.
"""

from __future__ import annotations

import os
import time
from datetime import date, datetime
from typing import Any, Dict, Optional

import requests


class TradeStationClient:
    """A simple client for interacting with the TradeStation REST API.

    Parameters are loaded from either the provided configuration dictionary
    or environment variables.  An access token is cached and automatically
    refreshed when expired.  Methods are provided for retrieving account
    information and placing bracket orders for option trades.
    """

    def __init__(self, config: Dict[str, Any] | None = None) -> None:
        config = config or {}
        # Base API URL (simulator or live).  Default to simulator if not
        # specified.  Remove trailing slash for consistency.
        self.base_url: str = (
            config.get("base_url")
            or os.getenv("TS_BASE_URL", "https://sim-api.tradestation.com/v3")
        ).rstrip("/")
        # OAuth2 credentials
        self.client_id: Optional[str] = config.get("client_id") or os.getenv("TS_CLIENT_ID")
        self.client_secret: Optional[str] = config.get("client_secret") or os.getenv("TS_CLIENT_SECRET")
        self.account_key: Optional[str] = config.get("account_key") or os.getenv("TS_ACCOUNT_KEY")
        self.redirect_uri: Optional[str] = config.get("redirect_uri") or os.getenv("TS_REDIRECT_URI")
        self.refresh_token: Optional[str] = config.get("refresh_token") or os.getenv("TS_REFRESH_TOKEN")
        # Access token state
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------
    def _refresh_access_token(self) -> None:
        """Refresh the OAuth2 access token using the refresh token.

        The TradeStation API expects a POST to /security/authorize with
        `grant_type=refresh_token` and the client credentials.  See
        https://tradestation.github.io/api-docs/authentication for details.
        """
        if not all([self.client_id, self.client_secret, self.refresh_token, self.redirect_uri]):
            raise RuntimeError("TradeStation client missing OAuth credentials")
        url = f"{self.base_url}/security/authorize"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "redirect_uri": self.redirect_uri,
        }
        resp = requests.post(url, data=data)
        resp.raise_for_status()
        payload = resp.json()
        self._access_token = payload.get("access_token")
        expires_in = float(payload.get("expires_in", 0))
        # Subtract 60s to proactively refresh before expiry
        self._token_expires_at = time.time() + expires_in - 60

    def _get_access_token(self) -> str:
        """Return a valid access token, refreshing it if necessary."""
        if not self._access_token or time.time() >= self._token_expires_at:
            self._refresh_access_token()
        assert self._access_token is not None  # type checker
        return self._access_token

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        """Perform an HTTP request to the API with authentication.

        Parameters
        ----------
        method: str
            The HTTP method (e.g. 'GET', 'POST').
        path: str
            The API path relative to ``base_url`` (without leading slash).
        **kwargs: Any
            Additional keyword arguments passed to ``requests.request``.

        Returns
        -------
        dict
            The JSON decoded response body.
        """
        token = self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        url = f"{self.base_url}/{path.lstrip('/') }"
        resp = requests.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        if resp.content:
            return resp.json()
        return {}

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def get_account(self) -> Dict[str, Any]:
        """Retrieve account details for the configured account_key.

        The API returns a JSON array of accounts for the authenticated user.
        We filter for the configured account key.  Raises an exception if
        the account is not found.
        """
        accounts = self._request("GET", "/user/accounts")
        if not isinstance(accounts, list):
            raise RuntimeError("Unexpected response for accounts endpoint")
        for acct in accounts:
            if acct.get("AccountKey") == self.account_key:
                return acct
        raise RuntimeError(f"Account {self.account_key} not found in response")

    def submit_bracket_order(
        self,
        signal: Any,
        quantity: int = 1,
    ) -> Dict[str, Any]:
        """Submit a bracket order for the given trade signal.

        Constructs an OSI option symbol from the signal, builds a primary
        buy-to-open order and a secondary stop-loss order, and sends them as
        an OCO (One-Cancels-Other) group.  Returns the API response.
        """
        # Ensure signal has required attributes
        symbol = signal.symbol
        strike = signal.strike
        option_type = signal.option_type
        expiration_date = signal.expiration_date
        entry = signal.entry_price
        stop = signal.stop_price
        # Build OSI symbol (root padded to 6 chars, YYMMDD, type, strike price)
        exp_dt = expiration_date if isinstance(expiration_date, date) else date.fromisoformat(str(expiration_date))
        yy = exp_dt.strftime("%y")
        mmdd = exp_dt.strftime("%m%d")
        type_code = "C" if option_type.lower().startswith("c") else "P"
        strike_formatted = f"{strike:08.3f}".replace(".", "")
        root = symbol.ljust(6)
        option_symbol = f"{root}{yy}{mmdd}{type_code}{strike_formatted}"
        primary = {
            "AccountKey": self.account_key,
            "Symbol": option_symbol,
            "Quantity": quantity,
            "OrderAction": "Buy",
            "OrderType": "Limit",
            "LimitPrice": entry,
            "TimeInForce": "Day",
            "Route": "AUTO",
        }
        secondary = {
            "AccountKey": self.account_key,
            "Symbol": option_symbol,
            "Quantity": quantity,
            "OrderAction": "Sell",
            "OrderType": "Stop",
            "StopPrice": stop,
            "TimeInForce": "Day",
            "Route": "AUTO",
        }
        payload = {"Orders": [primary, secondary]}
        return self._request("POST", "/order/groups", json=payload)
