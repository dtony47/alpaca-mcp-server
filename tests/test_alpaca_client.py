"""Tests for majors.alpaca_client -- HTTP wrapper.

All tests mock requests.Session; no live network.
"""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from majors.alpaca_client import (
    AlpacaAccount,
    AlpacaClient,
    AlpacaError,
    AlpacaOrder,
    AlpacaPosition,
    AlpacaQuote,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict[str, Any] | list[dict[str, Any]]:
    loaded = json.loads((FIXTURES / name).read_text())
    assert isinstance(loaded, dict | list)
    return loaded


@pytest.fixture
def client() -> AlpacaClient:
    return AlpacaClient(
        api_key="key",
        secret_key="secret",
        base_url="https://paper-api.alpaca.markets",
        data_url="https://data.alpaca.markets",
    )


def _mock_response(
    mocker: MockerFixture,
    status: int,
    body: dict[str, Any] | list[dict[str, Any]],
) -> Any:
    resp = mocker.MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    resp.text = json.dumps(body)
    resp.raise_for_status = (
        mocker.MagicMock()
        if status < 400
        else mocker.MagicMock(side_effect=Exception(f"{status}"))
    )
    return resp


def test_get_account_returns_typed_account(
    mocker: MockerFixture,
    client: AlpacaClient,
) -> None:
    body = _load("alpaca_account.json")
    mocker.patch("requests.Session.get", return_value=_mock_response(mocker, 200, body))

    account = client.get_account()

    assert isinstance(account, AlpacaAccount)
    assert account.equity == Decimal("100000.50")
    assert account.cash == Decimal("100000.50")
    assert account.account_number == "PA000000001"


def test_list_positions_returns_typed_positions(
    mocker: MockerFixture,
    client: AlpacaClient,
) -> None:
    body = _load("alpaca_positions.json")
    mocker.patch("requests.Session.get", return_value=_mock_response(mocker, 200, body))

    positions = client.list_positions()

    assert len(positions) == 1
    assert isinstance(positions[0], AlpacaPosition)
    assert positions[0].symbol == "BTC/USD"
    assert positions[0].qty == Decimal("0.01234567")
    assert positions[0].avg_entry_price == Decimal("60000.00")


def test_get_bars_returns_dataframe(mocker: MockerFixture, client: AlpacaClient) -> None:
    body = _load("alpaca_bars_btc.json")
    get_mock = mocker.patch("requests.Session.get", return_value=_mock_response(mocker, 200, body))

    df = client.get_bars("BTC/USD", timeframe="1Hour", limit=60)

    assert isinstance(df, pd.DataFrame)
    assert {"open", "high", "low", "close", "volume"}.issubset(df.columns)
    assert len(df) == 60
    assert df["close"].iloc[-1] == 60590

    _, kwargs = get_mock.call_args
    assert kwargs["params"]["limit"] == 60
    assert kwargs["params"]["timeframe"] == "1Hour"
    assert kwargs["params"]["start"].endswith("Z")


def test_get_latest_quote_returns_typed_quote(
    mocker: MockerFixture,
    client: AlpacaClient,
) -> None:
    body = _load("alpaca_quote_btc.json")
    mocker.patch("requests.Session.get", return_value=_mock_response(mocker, 200, body))

    quote = client.get_latest_quote("BTC/USD")

    assert isinstance(quote, AlpacaQuote)
    assert quote.symbol == "BTC/USD"
    assert quote.bid == Decimal("59950.00")
    assert quote.ask == Decimal("60050.00")
    assert quote.spread_pct < Decimal("0.005")


def test_place_market_buy_posts_correct_payload(
    mocker: MockerFixture,
    client: AlpacaClient,
) -> None:
    order_body = _load("alpaca_order_filled.json")
    post_mock = mocker.patch(
        "requests.Session.post",
        return_value=_mock_response(mocker, 200, order_body),
    )

    order = client.place_market_buy(
        symbol="BTC/USD",
        notional=Decimal("1000.00"),
        client_order_id="majors-BTC/USD-2026-05-04T15:00:00Z",
    )

    assert isinstance(order, AlpacaOrder)
    assert order.status == "filled"
    assert order.filled_qty == Decimal("0.01666666")

    _, kwargs = post_mock.call_args
    payload = kwargs["json"]
    assert payload["symbol"] == "BTC/USD"
    assert payload["side"] == "buy"
    assert payload["type"] == "market"
    assert payload["time_in_force"] == "gtc"
    assert payload["notional"] == "1000.00"
    assert payload["client_order_id"] == "majors-BTC/USD-2026-05-04T15:00:00Z"


def test_place_stop_limit_sell_posts_correct_payload(
    mocker: MockerFixture,
    client: AlpacaClient,
) -> None:
    order_body = _load("alpaca_stop_limit.json")
    post_mock = mocker.patch(
        "requests.Session.post",
        return_value=_mock_response(mocker, 200, order_body),
    )

    order = client.place_stop_limit_sell(
        symbol="BTC/USD",
        qty=Decimal("0.01666666"),
        stop_price=Decimal("55800.00"),
        limit_price=Decimal("55700.00"),
        client_order_id="majors-BTC/USD-2026-05-04T15:00:00Z-stop",
    )

    assert isinstance(order, AlpacaOrder)
    _, kwargs = post_mock.call_args
    payload = kwargs["json"]
    assert payload["type"] == "stop_limit"
    assert payload["stop_price"] == "55800.00"
    assert payload["limit_price"] == "55700.00"
    assert payload["qty"] == "0.01666666"
    assert payload["side"] == "sell"


def test_cancel_order_calls_delete(mocker: MockerFixture, client: AlpacaClient) -> None:
    delete_mock = mocker.patch(
        "requests.Session.delete",
        return_value=_mock_response(mocker, 204, {}),
    )

    client.cancel_order("abcd1234")

    delete_mock.assert_called_once()
    url = delete_mock.call_args.args[0]
    assert url.endswith("/v2/orders/abcd1234")


def test_http_error_raises_alpaca_error(
    mocker: MockerFixture,
    client: AlpacaClient,
) -> None:
    err_resp = mocker.MagicMock()
    err_resp.status_code = 422
    err_resp.text = '{"message": "insufficient buying power"}'
    err_resp.json.return_value = {"message": "insufficient buying power"}
    mocker.patch("requests.Session.post", return_value=err_resp)

    with pytest.raises(AlpacaError, match="insufficient buying power"):
        client.place_market_buy(
            symbol="BTC/USD",
            notional=Decimal("999999"),
            client_order_id="x",
        )
