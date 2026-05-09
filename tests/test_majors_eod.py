"""Tests for majors.eod."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from pytest_mock import MockerFixture

from majors.eod import EodConfig, run_eod


def _account(equity: str = "100000.50", cash: str = "50000") -> SimpleNamespace:
    return SimpleNamespace(equity=Decimal(equity), cash=Decimal(cash))


def _position(
    symbol: str,
    qty: str,
    entry: str,
    current: str,
    plpc: str,
) -> SimpleNamespace:
    return SimpleNamespace(
        symbol=symbol,
        qty=Decimal(qty),
        avg_entry_price=Decimal(entry),
        current_price=Decimal(current),
        unrealized_plpc=Decimal(plpc),
    )


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "memory"
    directory.mkdir()
    (directory / "TRADE-LOG.md").write_text("# Trade Log\n", encoding="utf-8")
    (directory / "PHASE.md").write_text(
        "# Current Phase\n\nPhase: paper\n\nHistory:\n",
        encoding="utf-8",
    )
    (directory / "NOTIFICATIONS.md").write_text("# Notifications\n", encoding="utf-8")
    return directory


def _config(memory_dir: Path) -> EodConfig:
    return EodConfig(
        memory_dir=memory_dir,
        alpaca_api_key="k",
        alpaca_secret_key="s",
        alpaca_base_url="https://paper-api.alpaca.markets",
        alpaca_data_url="https://data.alpaca.markets",
        telegram_token=None,
        telegram_chat_id=None,
    )


def test_eod_writes_dated_section_with_positions(
    mocker: MockerFixture,
    memory_dir: Path,
) -> None:
    client = mocker.MagicMock()
    client.get_account.return_value = _account()
    client.list_positions.return_value = [
        _position("BTC/USD", "0.01", "60000", "62500", "0.04166667"),
        _position("ETH/USD", "0.10", "3500", "3458", "-0.01200000"),
    ]
    mocker.patch("majors.eod.AlpacaClient", return_value=client)
    send_mock = mocker.patch("majors.eod.send")

    run_eod(_config(memory_dir), now=datetime(2026, 5, 4, 22, 0, 0))

    log = (memory_dir / "TRADE-LOG.md").read_text(encoding="utf-8")
    assert "2026-05-04" in log
    assert "EOD" in log
    assert "$100000.50" in log
    assert "BTC/USD" in log
    assert "ETH/USD" in log
    assert "+4.17%" in log
    assert "-1.20%" in log
    send_mock.assert_called_once()
    assert send_mock.call_args.kwargs["telegram_token"] is None


def test_eod_handles_zero_positions(mocker: MockerFixture, memory_dir: Path) -> None:
    client = mocker.MagicMock()
    client.get_account.return_value = _account(equity="100000", cash="100000")
    client.list_positions.return_value = []
    mocker.patch("majors.eod.AlpacaClient", return_value=client)

    run_eod(_config(memory_dir), now=datetime(2026, 5, 4, 22, 0, 0))

    log = (memory_dir / "TRADE-LOG.md").read_text(encoding="utf-8")
    assert "Open positions:** 0" in log


def test_eod_idempotent_on_same_day(mocker: MockerFixture, memory_dir: Path) -> None:
    client = mocker.MagicMock()
    client.get_account.return_value = _account()
    client.list_positions.return_value = []
    mocker.patch("majors.eod.AlpacaClient", return_value=client)

    run_eod(_config(memory_dir), now=datetime(2026, 5, 4, 22, 0, 0))
    run_eod(_config(memory_dir), now=datetime(2026, 5, 4, 22, 30, 0))

    log = (memory_dir / "TRADE-LOG.md").read_text(encoding="utf-8")
    assert log.count("2026-05-04 EOD") == 1
