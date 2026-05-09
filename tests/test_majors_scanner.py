"""Tests for majors.scanner orchestration."""

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from majors.alpaca_client import AlpacaError
from majors.scanner import ScannerConfig, ScanReport, run_scan


def _bars(n: int = 60) -> pd.DataFrame:
    closes = [60000.0 + i for i in range(n)]
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c * 1.001 for c in closes],
            "low": [c * 0.999 for c in closes],
            "close": closes,
            "volume": [10.0] * n,
        }
    )


def _account(equity: str = "100000", cash: str = "50000") -> SimpleNamespace:
    return SimpleNamespace(
        equity=Decimal(equity),
        cash=Decimal(cash),
        trading_blocked=False,
    )


def _quote(bid: str = "59950", ask: str = "60050") -> SimpleNamespace:
    bid_decimal = Decimal(bid)
    ask_decimal = Decimal(ask)
    mid = (bid_decimal + ask_decimal) / Decimal("2")
    return SimpleNamespace(
        bid=bid_decimal,
        ask=ask_decimal,
        mid=mid,
        spread_pct=((ask_decimal - bid_decimal) / mid).copy_abs(),
    )


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "memory"
    directory.mkdir()
    (directory / "KILL-SWITCH.md").write_text(
        "# Kill Switch\n\nState: ACTIVE\n\nHistory:\n",
        encoding="utf-8",
    )
    (directory / "PHASE.md").write_text(
        "# Current Phase\n\nPhase: paper\n\nHistory:\n",
        encoding="utf-8",
    )
    (directory / "TRADE-LOG.md").write_text("# Trade Log\n", encoding="utf-8")
    (directory / "MONITOR-LOG.md").write_text("# Monitor Log\n", encoding="utf-8")
    (directory / "NOTIFICATIONS.md").write_text("# Notifications\n", encoding="utf-8")
    return directory


def _config(memory_dir: Path) -> ScannerConfig:
    return ScannerConfig(
        universe=["BTC/USD"],
        memory_dir=memory_dir,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
        intended_position_pct=Decimal("0.20"),
        max_spread_pct=Decimal("0.005"),
        alpaca_api_key="k",
        alpaca_secret_key="s",
        alpaca_base_url="https://paper-api.alpaca.markets",
        alpaca_data_url="https://data.alpaca.markets",
        telegram_token=None,
        telegram_chat_id=None,
    )


def _patch_buy_signal(mocker: MockerFixture) -> None:
    mocker.patch(
        "majors.scanner.compute_signal",
        return_value=SimpleNamespace(symbol_action="BUY", reason="MA cross + RSI healthy"),
    )


def test_scanner_bails_when_kill_switch_paused(
    mocker: MockerFixture,
    memory_dir: Path,
) -> None:
    (memory_dir / "KILL-SWITCH.md").write_text(
        "# Kill Switch\n\nState: PAUSED\n\nHistory:\n",
        encoding="utf-8",
    )
    client_class = mocker.patch("majors.scanner.AlpacaClient")
    send_mock = mocker.patch("majors.scanner.send")

    report = run_scan(_config(memory_dir))

    assert isinstance(report, ScanReport)
    assert report.aborted_reason == "kill_switch_PAUSED"
    assert report.entries_placed == 0
    client_class.assert_not_called()
    send_mock.assert_called_once()
    assert send_mock.call_args.kwargs["telegram_token"] is None


def test_scanner_places_entry_on_buy_signal(mocker: MockerFixture, memory_dir: Path) -> None:
    _patch_buy_signal(mocker)
    client = mocker.MagicMock()
    client.get_account.return_value = _account()
    client.list_positions.return_value = []
    client.list_open_orders.return_value = []
    client.get_bars.return_value = _bars()
    client.get_latest_quote.return_value = _quote()
    mocker.patch("majors.scanner.AlpacaClient", return_value=client)
    exec_mock = mocker.patch("majors.scanner.execute_buy")
    send_mock = mocker.patch("majors.scanner.send")

    report = run_scan(_config(memory_dir), now=datetime(2026, 5, 4, 15, 0, tzinfo=UTC))

    assert report.entries_placed == 1
    assert report.entries_skipped_by_gate == 0
    exec_mock.assert_called_once()
    send_mock.assert_called_once()
    assert send_mock.call_args.kwargs["telegram_token"] is None


def test_scanner_skips_when_spread_too_wide(
    mocker: MockerFixture,
    memory_dir: Path,
) -> None:
    _patch_buy_signal(mocker)
    client = mocker.MagicMock()
    client.get_account.return_value = _account()
    client.list_positions.return_value = []
    client.list_open_orders.return_value = []
    client.get_bars.return_value = _bars()
    client.get_latest_quote.return_value = _quote(bid="59000", ask="60000")
    mocker.patch("majors.scanner.AlpacaClient", return_value=client)
    exec_mock = mocker.patch("majors.scanner.execute_buy")

    report = run_scan(_config(memory_dir), now=datetime(2026, 5, 4, 15, 0, tzinfo=UTC))

    assert report.entries_placed == 0
    assert report.entries_skipped_by_gate == 1
    exec_mock.assert_not_called()
    monitor = (memory_dir / "MONITOR-LOG.md").read_text(encoding="utf-8")
    assert "spread" in monitor.lower()


def test_scanner_skips_when_position_already_open(
    mocker: MockerFixture,
    memory_dir: Path,
) -> None:
    _patch_buy_signal(mocker)
    client = mocker.MagicMock()
    client.get_account.return_value = _account()
    client.list_positions.return_value = [
        SimpleNamespace(
            symbol="BTC/USD",
            qty=Decimal("0.01"),
            avg_entry_price=Decimal("60000"),
            current_price=Decimal("62000"),
        )
    ]
    client.list_open_orders.return_value = []
    client.get_bars.return_value = _bars()
    client.get_latest_quote.return_value = _quote()
    mocker.patch("majors.scanner.AlpacaClient", return_value=client)
    exec_mock = mocker.patch("majors.scanner.execute_buy")

    report = run_scan(_config(memory_dir), now=datetime(2026, 5, 4, 15, 0, tzinfo=UTC))

    assert report.entries_placed == 0
    exec_mock.assert_not_called()


def test_scanner_logs_rate_limit_gate_failure_and_skips(
    mocker: MockerFixture,
    memory_dir: Path,
) -> None:
    _patch_buy_signal(mocker)
    client = mocker.MagicMock()
    client.get_account.return_value = _account()
    client.list_positions.return_value = []
    client.list_open_orders.return_value = [
        SimpleNamespace(symbol="OTHER/USD", type="market", side="buy") for _ in range(5)
    ]
    client.get_bars.return_value = _bars()
    client.get_latest_quote.return_value = _quote()
    mocker.patch("majors.scanner.AlpacaClient", return_value=client)
    exec_mock = mocker.patch("majors.scanner.execute_buy")

    report = run_scan(_config(memory_dir), now=datetime(2026, 5, 4, 15, 0, tzinfo=UTC))

    assert report.entries_placed == 0
    assert report.entries_skipped_by_gate == 1
    exec_mock.assert_not_called()
    monitor = (memory_dir / "MONITOR-LOG.md").read_text(encoding="utf-8")
    assert "rate_limit" in monitor


def test_scanner_tightens_trailing_stop_when_position_runs_up(
    mocker: MockerFixture,
    memory_dir: Path,
) -> None:
    client = mocker.MagicMock()
    client.get_account.return_value = _account()
    client.list_positions.return_value = [
        SimpleNamespace(
            symbol="BTC/USD",
            qty=Decimal("0.01"),
            avg_entry_price=Decimal("60000"),
            current_price=Decimal("72000"),
        )
    ]
    client.list_open_orders.return_value = [
        SimpleNamespace(
            id="stop-old",
            symbol="BTC/USD",
            type="stop_limit",
            side="sell",
            qty=Decimal("0.01"),
            stop_price=Decimal("55800.00"),
        )
    ]
    client.get_bars.return_value = _bars()
    client.get_latest_quote.return_value = _quote()
    mocker.patch("majors.scanner.AlpacaClient", return_value=client)
    send_mock = mocker.patch("majors.scanner.send")

    report = run_scan(_config(memory_dir), now=datetime(2026, 5, 4, 15, 0, tzinfo=UTC))

    assert report.trails_tightened == 1
    client.cancel_order.assert_called_with("stop-old")
    client.place_stop_limit_sell.assert_called_once()
    new_stop_kwargs = client.place_stop_limit_sell.call_args.kwargs
    assert new_stop_kwargs["stop_price"] == Decimal("68400.00")
    send_mock.assert_called_once()
    assert send_mock.call_args.kwargs["telegram_token"] is None


def test_scanner_dedupes_repeated_broker_read_failures(
    mocker: MockerFixture,
    memory_dir: Path,
) -> None:
    client = mocker.MagicMock()
    client.get_account.side_effect = AlpacaError("HTTP 401: unauthorized")
    mocker.patch("majors.scanner.AlpacaClient", return_value=client)
    send_mock = mocker.patch("majors.scanner.send")

    base = _config(memory_dir)
    config = ScannerConfig(
        **{**base.__dict__, "telegram_token": "token", "telegram_chat_id": "chat"}
    )

    first = run_scan(config, now=datetime(2026, 5, 4, 15, 0, tzinfo=UTC))
    assert first.aborted_reason == "alpaca_read_error:HTTP 401: unauthorized"
    send_mock.assert_called_once()
    assert send_mock.call_args.kwargs["telegram_token"] == "token"

    send_mock.reset_mock()
    second = run_scan(config, now=datetime(2026, 5, 4, 16, 0, tzinfo=UTC))
    assert second.aborted_reason == "alpaca_read_error:HTTP 401: unauthorized"
    send_mock.assert_not_called()
