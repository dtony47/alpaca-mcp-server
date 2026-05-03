from decimal import Decimal

from core.types import AccountState, GateResult, OrderIntent, Position


def test_account_state_construction():
    state = AccountState(
        equity=Decimal("10000"),
        cash=Decimal("5000"),
        venue="alpaca",
        day_pl_pct=Decimal("-0.01"),
        phase_pl_pct=Decimal("0.05"),
        open_positions_count=3,
        trades_last_hour=1,
    )
    assert state.equity == Decimal("10000")
    assert state.venue == "alpaca"


def test_position_construction():
    pos = Position(
        symbol="BTC/USD",
        venue="alpaca",
        qty=Decimal("0.05"),
        entry_price=Decimal("60000"),
        current_price=Decimal("62000"),
        unrealized_pl_pct=Decimal("0.0333"),
        stop_price=Decimal("54000"),
    )
    assert pos.symbol == "BTC/USD"
    assert pos.unrealized_pl_pct == Decimal("0.0333")


def test_order_intent_construction():
    intent = OrderIntent(
        symbol="BTC/USD",
        venue="alpaca",
        side="buy",
        qty=Decimal("0.01"),
        intended_cost_usd=Decimal("600"),
        leg="majors",
    )
    assert intent.side == "buy"
    assert intent.leg == "majors"


def test_gate_result_pass():
    result = GateResult(passed=True, gate_name="kill_switch", reason=None)
    assert result.passed is True
    assert result.reason is None


def test_gate_result_fail():
    result = GateResult(
        passed=False,
        gate_name="daily_loss_limit",
        reason="Day P&L -3.2% exceeds limit -3%",
    )
    assert result.passed is False
    assert "3.2%" in (result.reason or "")
