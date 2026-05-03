from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from core.audit import TradeRecord, log_trade


def make_record(trade_id: str = "t1") -> TradeRecord:
    return TradeRecord(
        trade_id=trade_id,
        timestamp=datetime(2026, 5, 3, 14, 30, tzinfo=timezone.utc),
        leg="majors",
        venue="alpaca",
        symbol="BTC/USD",
        side="buy",
        qty=Decimal("0.01"),
        price=Decimal("60000"),
        cost_usd=Decimal("600"),
        thesis="composite score 1.7, BTC pumping on ETF flows",
        stop_price=Decimal("54000"),
        target_price=Decimal("70000"),
    )


def test_log_trade_appends_to_empty_file(tmp_path: Path):
    p = tmp_path / "TRADE-LOG.md"
    log_trade(make_record(), p)
    content = p.read_text()
    assert "BTC/USD" in content
    assert "t1" in content
    assert "60000" in content


def test_log_trade_appends_to_existing_file(tmp_path: Path):
    p = tmp_path / "TRADE-LOG.md"
    p.write_text("# Trade Log\n\n## Day 0 — baseline\nBaseline.\n")
    log_trade(make_record("t1"), p)
    log_trade(make_record("t2"), p)
    content = p.read_text()
    assert content.startswith("# Trade Log")
    assert "t1" in content
    assert "t2" in content


def test_log_trade_is_idempotent_on_same_trade_id(tmp_path: Path):
    p = tmp_path / "TRADE-LOG.md"
    log_trade(make_record("t-dedup"), p)
    log_trade(make_record("t-dedup"), p)
    log_trade(make_record("t-dedup"), p)
    content = p.read_text()
    # Should appear exactly once
    assert content.count("t-dedup") == 1


def test_log_trade_creates_parent_directory(tmp_path: Path):
    p = tmp_path / "nested" / "TRADE-LOG.md"
    log_trade(make_record(), p)
    assert p.exists()
