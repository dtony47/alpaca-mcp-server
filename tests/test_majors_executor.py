"""Tests for majors.executor."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pytest_mock import MockerFixture

from core.types import OrderIntent
from majors.alpaca_client import AlpacaError, AlpacaOrder
from majors.executor import ExecutionResult, execute_buy


@pytest.fixture
def intent() -> OrderIntent:
    return OrderIntent(
        symbol="BTC/USD",
        venue="alpaca",
        side="buy",
        qty=Decimal("0.01666666"),
        intended_cost_usd=Decimal("1000.00"),
        leg="majors",
    )


def _filled(client_order_id: str = "majors-BTC/USD-2026-05-04T15:00:00Z") -> AlpacaOrder:
    return AlpacaOrder(
        id="order-123",
        client_order_id=client_order_id,
        status="filled",
        symbol="BTC/USD",
        side="buy",
        type="market",
        qty=Decimal("0.01666666"),
        filled_qty=Decimal("0.01666666"),
        filled_avg_price=Decimal("60000.00"),
    )


def _stop_accepted(client_order_id: str) -> AlpacaOrder:
    return AlpacaOrder(
        id="stop-456",
        client_order_id=client_order_id,
        status="accepted",
        symbol="BTC/USD",
        side="sell",
        type="stop_limit",
        qty=Decimal("0.01666666"),
        filled_qty=Decimal("0"),
        filled_avg_price=None,
    )


def test_execute_buy_places_market_then_stop_and_audits(
    mocker: MockerFixture,
    tmp_path: Path,
    intent: OrderIntent,
) -> None:
    client = mocker.MagicMock()
    client.place_market_buy.return_value = _filled()
    client.place_stop_limit_sell.return_value = _stop_accepted(
        "majors-BTC/USD-2026-05-04T15:00:00Z-stop"
    )

    trade_log = tmp_path / "TRADE-LOG.md"
    trade_log.write_text("# Trade Log\n", encoding="utf-8")

    result = execute_buy(
        client=client,
        intent=intent,
        now=datetime(2026, 5, 4, 15, 0, 0),
        trade_log_path=trade_log,
        thesis="MA cross + RSI healthy",
    )

    assert isinstance(result, ExecutionResult)
    assert result.buy_order_id == "order-123"
    assert result.stop_order_id == "stop-456"
    assert result.fill_price == Decimal("60000.00")
    assert result.stop_price == Decimal("55800.00")

    client.place_market_buy.assert_called_once()
    client.place_stop_limit_sell.assert_called_once()
    stop_kwargs = client.place_stop_limit_sell.call_args.kwargs
    assert stop_kwargs["stop_price"] == Decimal("55800.00")
    assert stop_kwargs["qty"] == Decimal("0.01666666")

    log = trade_log.read_text(encoding="utf-8")
    assert "BTC/USD" in log
    assert "MA cross + RSI healthy" in log
    assert "$60000.00" in log


def test_execute_buy_raises_if_not_filled(
    mocker: MockerFixture,
    tmp_path: Path,
    intent: OrderIntent,
) -> None:
    client = mocker.MagicMock()
    client.place_market_buy.return_value = AlpacaOrder(
        id="x",
        client_order_id="y",
        status="rejected",
        symbol="BTC/USD",
        side="buy",
        type="market",
        qty=Decimal("0"),
        filled_qty=Decimal("0"),
        filled_avg_price=None,
    )

    trade_log = tmp_path / "TRADE-LOG.md"
    trade_log.write_text("# Trade Log\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="not filled"):
        execute_buy(
            client=client,
            intent=intent,
            now=datetime(2026, 5, 4, 15, 0, 0),
            trade_log_path=trade_log,
            thesis="x",
        )

    client.place_stop_limit_sell.assert_not_called()


def test_execute_buy_swallows_duplicate_client_order_id(
    mocker: MockerFixture,
    tmp_path: Path,
    intent: OrderIntent,
) -> None:
    client = mocker.MagicMock()
    client.place_market_buy.side_effect = AlpacaError(
        "HTTP 422: client_order_id has already been used"
    )
    client.list_open_orders.return_value = [_filled()]
    client.place_stop_limit_sell.return_value = _stop_accepted(
        "majors-BTC/USD-2026-05-04T15:00:00Z-stop"
    )

    trade_log = tmp_path / "TRADE-LOG.md"
    trade_log.write_text("# Trade Log\n", encoding="utf-8")

    result = execute_buy(
        client=client,
        intent=intent,
        now=datetime(2026, 5, 4, 15, 0, 0),
        trade_log_path=trade_log,
        thesis="x",
    )

    assert result.buy_order_id == "order-123"
