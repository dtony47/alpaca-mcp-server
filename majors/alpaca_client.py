"""Thin HTTP wrapper for Alpaca trading and crypto market-data APIs."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pandas as pd
import requests


class AlpacaError(RuntimeError):
    """Raised on any non-2xx Alpaca HTTP response."""


@dataclass(frozen=True)
class AlpacaAccount:
    account_number: str
    status: str
    equity: Decimal
    cash: Decimal
    buying_power: Decimal
    portfolio_value: Decimal
    trading_blocked: bool


@dataclass(frozen=True)
class AlpacaPosition:
    symbol: str
    asset_class: str
    qty: Decimal
    avg_entry_price: Decimal
    current_price: Decimal
    unrealized_plpc: Decimal
    side: str


@dataclass(frozen=True)
class AlpacaOrder:
    id: str
    client_order_id: str
    status: str
    symbol: str
    side: str
    type: str
    qty: Decimal
    filled_qty: Decimal
    filled_avg_price: Decimal | None
    stop_price: Decimal | None = None


@dataclass(frozen=True)
class AlpacaQuote:
    symbol: str
    bid: Decimal
    ask: Decimal

    @property
    def mid(self) -> Decimal:
        return (self.bid + self.ask) / Decimal("2")

    @property
    def spread_pct(self) -> Decimal:
        if self.mid <= 0:
            return Decimal("9999")
        return ((self.ask - self.bid) / self.mid).copy_abs()


class AlpacaClient:
    def __init__(
        self,
        api_key: str,
        secret_key: str,
        base_url: str,
        data_url: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._data_url = data_url.rstrip("/")
        self._timeout = timeout_seconds
        self._session = requests.Session()
        self._session.headers.update(
            {
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key,
                "Content-Type": "application/json",
            }
        )

    def get_account(self) -> AlpacaAccount:
        body = self._get(f"{self._base_url}/v2/account")
        return AlpacaAccount(
            account_number=body["account_number"],
            status=body["status"],
            equity=Decimal(body["equity"]),
            cash=Decimal(body["cash"]),
            buying_power=Decimal(body["buying_power"]),
            portfolio_value=Decimal(body["portfolio_value"]),
            trading_blocked=bool(body.get("trading_blocked", False)),
        )

    def list_positions(self) -> list[AlpacaPosition]:
        body = self._get(f"{self._base_url}/v2/positions")
        return [
            AlpacaPosition(
                symbol=p["symbol"],
                asset_class=p.get("asset_class", "crypto"),
                qty=Decimal(p["qty"]),
                avg_entry_price=Decimal(p["avg_entry_price"]),
                current_price=Decimal(p["current_price"]),
                unrealized_plpc=Decimal(p["unrealized_plpc"]),
                side=p["side"],
            )
            for p in body
        ]

    def get_bars(self, symbol: str, timeframe: str = "1Hour", limit: int = 100) -> pd.DataFrame:
        params = {"symbols": symbol, "timeframe": timeframe, "limit": limit}
        body = self._get(f"{self._data_url}/v1beta3/crypto/us/bars", params=params)
        bars = body.get("bars", {}).get(symbol, [])
        if not bars:
            raise AlpacaError(f"no bars returned for {symbol}")
        return pd.DataFrame(
            [
                {
                    "timestamp": b["t"],
                    "open": float(b["o"]),
                    "high": float(b["h"]),
                    "low": float(b["l"]),
                    "close": float(b["c"]),
                    "volume": float(b["v"]),
                }
                for b in bars
            ]
        )

    def get_latest_quote(self, symbol: str) -> AlpacaQuote:
        params = {"symbols": symbol}
        body = self._get(f"{self._data_url}/v1beta3/crypto/us/latest/quotes", params=params)
        quote = body.get("quotes", {}).get(symbol)
        if not quote:
            raise AlpacaError(f"no quote returned for {symbol}")
        return AlpacaQuote(
            symbol=symbol,
            bid=Decimal(str(quote["bp"])),
            ask=Decimal(str(quote["ap"])),
        )

    def place_market_buy(
        self,
        symbol: str,
        notional: Decimal,
        client_order_id: str,
    ) -> AlpacaOrder:
        payload = {
            "symbol": symbol,
            "side": "buy",
            "type": "market",
            "time_in_force": "gtc",
            "notional": str(notional),
            "client_order_id": client_order_id,
        }
        body = self._post(f"{self._base_url}/v2/orders", payload)
        return self._parse_order(body)

    def place_stop_limit_sell(
        self,
        symbol: str,
        qty: Decimal,
        stop_price: Decimal,
        limit_price: Decimal,
        client_order_id: str,
    ) -> AlpacaOrder:
        payload = {
            "symbol": symbol,
            "side": "sell",
            "type": "stop_limit",
            "time_in_force": "gtc",
            "qty": str(qty),
            "stop_price": str(stop_price),
            "limit_price": str(limit_price),
            "client_order_id": client_order_id,
        }
        body = self._post(f"{self._base_url}/v2/orders", payload)
        return self._parse_order(body)

    def cancel_order(self, order_id: str) -> None:
        resp = self._session.delete(
            f"{self._base_url}/v2/orders/{order_id}",
            timeout=self._timeout,
        )
        if resp.status_code >= 400 and resp.status_code != 422:
            self._raise(resp)

    def list_open_orders(self, symbol: str | None = None) -> list[AlpacaOrder]:
        params: dict[str, Any] = {"status": "open"}
        if symbol:
            params["symbols"] = symbol
        body = self._get(f"{self._base_url}/v2/orders", params=params)
        return [self._parse_order(order) for order in body]

    def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._session.get(url, params=params, timeout=self._timeout)
        if resp.status_code >= 400:
            self._raise(resp)
        return resp.json()

    def _post(self, url: str, payload: dict[str, Any]) -> Any:
        resp = self._session.post(url, json=payload, timeout=self._timeout)
        if resp.status_code >= 400:
            self._raise(resp)
        return resp.json()

    @staticmethod
    def _raise(resp: requests.Response) -> None:
        try:
            body = resp.json()
            msg = body.get("message") or body.get("error") or resp.text
        except Exception:
            msg = resp.text
        raise AlpacaError(f"HTTP {resp.status_code}: {msg}")

    @staticmethod
    def _parse_order(body: dict[str, Any]) -> AlpacaOrder:
        return AlpacaOrder(
            id=body["id"],
            client_order_id=body["client_order_id"],
            status=body["status"],
            symbol=body["symbol"],
            side=body["side"],
            type=body["type"],
            qty=Decimal(str(body.get("qty") or body.get("filled_qty") or "0")),
            filled_qty=Decimal(str(body.get("filled_qty") or "0")),
            filled_avg_price=(
                Decimal(str(body["filled_avg_price"])) if body.get("filled_avg_price") else None
            ),
            stop_price=Decimal(str(body["stop_price"])) if body.get("stop_price") else None,
        )
