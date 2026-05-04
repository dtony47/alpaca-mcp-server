from decimal import Decimal

import pytest

from core.risk_gates import (
    check_available_cash,
    check_daily_loss_limit,
    check_drawdown_limit,
    check_kill_switch,
    check_phase_valid,
    check_position_count,
    check_position_size,
    check_rate_limit,
    run_universal_gates,
)
from core.types import AccountState, OrderIntent

# ---------- shared fixtures ----------

@pytest.fixture
def healthy_state() -> AccountState:
    return AccountState(
        equity=Decimal("10000"),
        cash=Decimal("8000"),
        venue="alpaca",
        day_pl_pct=Decimal("0.01"),
        phase_pl_pct=Decimal("0.05"),
        open_positions_count=2,
        trades_last_hour=1,
    )


@pytest.fixture
def majors_intent() -> OrderIntent:
    return OrderIntent(
        symbol="BTC/USD",
        venue="alpaca",
        side="buy",
        qty=Decimal("0.01"),
        intended_cost_usd=Decimal("600"),
        leg="majors",
    )


# ---------- check_kill_switch ----------

def test_kill_switch_active_passes():
    r = check_kill_switch(state="ACTIVE")
    assert r.passed and r.reason is None


def test_kill_switch_paused_fails():
    r = check_kill_switch(state="PAUSED")
    assert not r.passed and "PAUSED" in (r.reason or "")


def test_kill_switch_killed_fails():
    r = check_kill_switch(state="KILLED")
    assert not r.passed and "KILLED" in (r.reason or "")


def test_kill_switch_unknown_fails():
    r = check_kill_switch(state="WEIRD")
    assert not r.passed


# ---------- check_phase_valid ----------

def test_phase_paper_passes():
    assert check_phase_valid("paper").passed


def test_phase_live_25_passes():
    assert check_phase_valid("live_25").passed


def test_phase_unknown_fails():
    r = check_phase_valid("yolo_max")
    assert not r.passed and "yolo_max" in (r.reason or "")


# ---------- check_daily_loss_limit ----------

def test_daily_loss_within_limit_passes():
    r = check_daily_loss_limit(day_pl_pct=Decimal("-0.02"), limit_pct=Decimal("0.03"))
    assert r.passed


def test_daily_loss_exactly_at_limit_fails():
    r = check_daily_loss_limit(day_pl_pct=Decimal("-0.03"), limit_pct=Decimal("0.03"))
    assert not r.passed


def test_daily_loss_exceeds_limit_fails():
    r = check_daily_loss_limit(day_pl_pct=Decimal("-0.05"), limit_pct=Decimal("0.03"))
    assert not r.passed and "5" in (r.reason or "")


def test_daily_gain_passes():
    r = check_daily_loss_limit(day_pl_pct=Decimal("0.10"), limit_pct=Decimal("0.03"))
    assert r.passed


# ---------- check_drawdown_limit ----------

def test_drawdown_within_limit_passes():
    r = check_drawdown_limit(phase_pl_pct=Decimal("-0.10"), limit_pct=Decimal("0.15"))
    assert r.passed


def test_drawdown_exceeds_limit_fails():
    r = check_drawdown_limit(phase_pl_pct=Decimal("-0.20"), limit_pct=Decimal("0.15"))
    assert not r.passed


# ---------- check_position_count ----------

def test_position_count_under_max_passes():
    r = check_position_count(current=3, max_allowed=6)
    assert r.passed


def test_position_count_at_max_fails():
    r = check_position_count(current=6, max_allowed=6)
    assert not r.passed


# ---------- check_position_size ----------

def test_position_size_within_limit_passes():
    r = check_position_size(
        intended_cost_usd=Decimal("1500"),
        equity=Decimal("10000"),
        max_pct=Decimal("0.20"),
    )
    assert r.passed


def test_position_size_exceeds_limit_fails():
    r = check_position_size(
        intended_cost_usd=Decimal("2500"),
        equity=Decimal("10000"),
        max_pct=Decimal("0.20"),
    )
    assert not r.passed


# ---------- check_available_cash ----------

def test_available_cash_sufficient_passes():
    r = check_available_cash(intended_cost_usd=Decimal("500"), available=Decimal("1000"))
    assert r.passed


def test_available_cash_insufficient_fails():
    r = check_available_cash(intended_cost_usd=Decimal("500"), available=Decimal("100"))
    assert not r.passed


# ---------- check_rate_limit ----------

def test_rate_limit_under_max_passes():
    r = check_rate_limit(trades_last_hour=3, max_per_hour=5)
    assert r.passed


def test_rate_limit_at_max_fails():
    r = check_rate_limit(trades_last_hour=5, max_per_hour=5)
    assert not r.passed


# ---------- run_universal_gates (composition) ----------

def test_run_universal_gates_all_pass(healthy_state, majors_intent):
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="paper",
        state=healthy_state,
        intent=majors_intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    assert all(r.passed for r in results), [r for r in results if not r.passed]


def test_run_universal_gates_kill_switch_short_circuits(healthy_state, majors_intent):
    results = run_universal_gates(
        kill_switch_state="KILLED",
        phase="paper",
        state=healthy_state,
        intent=majors_intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    # First gate (kill switch) failed; all subsequent gates skipped
    assert not results[0].passed
    assert results[0].gate_name == "kill_switch"
    # Length should be 1 (short-circuit on first failure)
    assert len(results) == 1


def test_run_universal_gates_oversize_fails(healthy_state):
    oversize = OrderIntent(
        symbol="BTC/USD",
        venue="alpaca",
        side="buy",
        qty=Decimal("0.05"),
        intended_cost_usd=Decimal("3000"),  # 30% of $10k equity, exceeds 20% cap
        leg="majors",
    )
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="paper",
        state=healthy_state,
        intent=oversize,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    failed = [r for r in results if not r.passed]
    assert len(failed) == 1
    assert failed[0].gate_name == "position_size"


# ---------- M-1: kill switch unknown state ----------

def test_kill_switch_unknown_state_has_unknown_reason():
    r = check_kill_switch(state="WEIRD")
    assert not r.passed
    assert r.reason is not None
    assert "Unknown" in r.reason or "unknown" in r.reason.lower()


# ---------- I-1: negative / invalid numeric inputs ----------

def test_check_position_size_negative_intended_fails_closed():
    r = check_position_size(
        intended_cost_usd=Decimal("-100"),
        equity=Decimal("1000"),
        max_pct=Decimal("0.20"),
    )
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_position_size_zero_equity_fails_closed():
    r = check_position_size(
        intended_cost_usd=Decimal("100"),
        equity=Decimal("0"),
        max_pct=Decimal("0.20"),
    )
    assert not r.passed


def test_check_position_size_negative_equity_fails_closed():
    r = check_position_size(
        intended_cost_usd=Decimal("100"),
        equity=Decimal("-500"),
        max_pct=Decimal("0.20"),
    )
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_position_size_negative_max_pct_fails_closed():
    r = check_position_size(
        intended_cost_usd=Decimal("100"),
        equity=Decimal("1000"),
        max_pct=Decimal("-0.20"),
    )
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_rate_limit_negative_count_fails_closed():
    r = check_rate_limit(trades_last_hour=-5, max_per_hour=5)
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_rate_limit_negative_max_fails_closed():
    r = check_rate_limit(trades_last_hour=0, max_per_hour=-1)
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_available_cash_negative_intended_fails_closed():
    r = check_available_cash(
        intended_cost_usd=Decimal("-100"), available=Decimal("1000")
    )
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_available_cash_negative_available_fails_closed():
    r = check_available_cash(
        intended_cost_usd=Decimal("100"), available=Decimal("-50")
    )
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_position_count_negative_current_fails_closed():
    r = check_position_count(current=-1, max_allowed=6)
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_position_count_negative_max_fails_closed():
    r = check_position_count(current=0, max_allowed=-1)
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_daily_loss_limit_negative_limit_fails_closed():
    r = check_daily_loss_limit(day_pl_pct=Decimal("0.01"), limit_pct=Decimal("-0.03"))
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


def test_check_drawdown_limit_negative_limit_fails_closed():
    r = check_drawdown_limit(phase_pl_pct=Decimal("-0.10"), limit_pct=Decimal("-0.15"))
    assert not r.passed
    assert "invalid" in (r.reason or "").lower()


# ---------- I-2: NaN inputs ----------

def test_check_daily_loss_limit_nan_input_fails_closed():
    r = check_daily_loss_limit(day_pl_pct=Decimal("NaN"), limit_pct=Decimal("0.03"))
    assert not r.passed
    assert r.reason is not None
    assert "nan" in (r.reason or "").lower() or "invalid" in (r.reason or "").lower()


def test_check_drawdown_limit_nan_input_fails_closed():
    r = check_drawdown_limit(phase_pl_pct=Decimal("NaN"), limit_pct=Decimal("0.15"))
    assert not r.passed
    assert r.reason is not None


def test_check_position_size_nan_input_fails_closed():
    r = check_position_size(
        intended_cost_usd=Decimal("NaN"),
        equity=Decimal("10000"),
        max_pct=Decimal("0.20"),
    )
    assert not r.passed
    assert r.reason is not None


def test_check_available_cash_nan_input_fails_closed():
    r = check_available_cash(
        intended_cost_usd=Decimal("NaN"), available=Decimal("1000")
    )
    assert not r.passed
    assert r.reason is not None


# ---------- M-4: per-gate first-to-fail composition tests ----------

def test_run_universal_gates_phase_invalid_short_circuits_after_kill_switch(
    healthy_state, majors_intent
):
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="yolo",
        state=healthy_state,
        intent=majors_intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    assert len(results) == 2
    assert results[-1].gate_name == "phase"
    assert results[-1].passed is False


def test_run_universal_gates_daily_loss_short_circuits(healthy_state, majors_intent):
    # Override state so day_pl_pct breaches the limit
    breached_state = AccountState(
        equity=healthy_state.equity,
        cash=healthy_state.cash,
        venue=healthy_state.venue,
        day_pl_pct=Decimal("-0.06"),  # exceeds 0.03 limit
        phase_pl_pct=healthy_state.phase_pl_pct,
        open_positions_count=healthy_state.open_positions_count,
        trades_last_hour=healthy_state.trades_last_hour,
    )
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="paper",
        state=breached_state,
        intent=majors_intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    assert len(results) == 3
    assert results[-1].gate_name == "daily_loss_limit"
    assert results[-1].passed is False


def test_run_universal_gates_drawdown_short_circuits(healthy_state, majors_intent):
    breached_state = AccountState(
        equity=healthy_state.equity,
        cash=healthy_state.cash,
        venue=healthy_state.venue,
        day_pl_pct=Decimal("0.01"),  # daily fine
        phase_pl_pct=Decimal("-0.20"),  # breaches 0.15 drawdown limit
        open_positions_count=healthy_state.open_positions_count,
        trades_last_hour=healthy_state.trades_last_hour,
    )
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="paper",
        state=breached_state,
        intent=majors_intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    assert len(results) == 4
    assert results[-1].gate_name == "drawdown_limit"
    assert results[-1].passed is False


def test_run_universal_gates_position_count_short_circuits(healthy_state, majors_intent):
    at_max_state = AccountState(
        equity=healthy_state.equity,
        cash=healthy_state.cash,
        venue=healthy_state.venue,
        day_pl_pct=healthy_state.day_pl_pct,
        phase_pl_pct=healthy_state.phase_pl_pct,
        open_positions_count=6,  # at max
        trades_last_hour=healthy_state.trades_last_hour,
    )
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="paper",
        state=at_max_state,
        intent=majors_intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    assert len(results) == 5
    assert results[-1].gate_name == "position_count"
    assert results[-1].passed is False


def test_run_universal_gates_position_size_short_circuits(healthy_state):
    oversize_intent = OrderIntent(
        symbol="BTC/USD",
        venue="alpaca",
        side="buy",
        qty=Decimal("0.05"),
        intended_cost_usd=Decimal("3000"),  # 30% of 10k, exceeds 20% cap
        leg="majors",
    )
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="paper",
        state=healthy_state,
        intent=oversize_intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    assert len(results) == 6
    assert results[-1].gate_name == "position_size"
    assert results[-1].passed is False


def test_run_universal_gates_available_cash_short_circuits(healthy_state):
    # Intent cost > cash but within position size limit
    low_cash_state = AccountState(
        equity=healthy_state.equity,
        cash=Decimal("100"),  # very low cash
        venue=healthy_state.venue,
        day_pl_pct=healthy_state.day_pl_pct,
        phase_pl_pct=healthy_state.phase_pl_pct,
        open_positions_count=healthy_state.open_positions_count,
        trades_last_hour=healthy_state.trades_last_hour,
    )
    intent = OrderIntent(
        symbol="BTC/USD",
        venue="alpaca",
        side="buy",
        qty=Decimal("0.01"),
        intended_cost_usd=Decimal("600"),  # within 20% of 10k equity, but > 100 cash
        leg="majors",
    )
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="paper",
        state=low_cash_state,
        intent=intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    assert len(results) == 7
    assert results[-1].gate_name == "available_cash"
    assert results[-1].passed is False


def test_run_universal_gates_rate_limit_short_circuits(healthy_state, majors_intent):
    at_rate_limit_state = AccountState(
        equity=healthy_state.equity,
        cash=healthy_state.cash,
        venue=healthy_state.venue,
        day_pl_pct=healthy_state.day_pl_pct,
        phase_pl_pct=healthy_state.phase_pl_pct,
        open_positions_count=healthy_state.open_positions_count,
        trades_last_hour=5,  # at rate limit
    )
    results = run_universal_gates(
        kill_switch_state="ACTIVE",
        phase="paper",
        state=at_rate_limit_state,
        intent=majors_intent,
        daily_loss_limit_pct=Decimal("0.03"),
        drawdown_limit_pct=Decimal("0.15"),
        max_positions=6,
        max_position_pct=Decimal("0.20"),
        rate_limit_per_hour=5,
    )
    assert len(results) == 8
    assert results[-1].gate_name == "rate_limit"
    assert results[-1].passed is False


# ---------- M-5: every failing gate has a non-empty reason ----------

@pytest.mark.parametrize("gate_call,expected_failed", [
    (lambda: check_kill_switch("PAUSED"), True),
    (lambda: check_kill_switch("KILLED"), True),
    (lambda: check_kill_switch("WEIRD"), True),
    (lambda: check_phase_valid("yolo"), True),
    (lambda: check_daily_loss_limit(Decimal("-0.05"), Decimal("0.03")), True),
    (lambda: check_drawdown_limit(Decimal("-0.20"), Decimal("0.15")), True),
    (lambda: check_position_count(6, 6), True),
    (lambda: check_position_size(Decimal("3000"), Decimal("10000"), Decimal("0.20")), True),
    (lambda: check_available_cash(Decimal("1000"), Decimal("100")), True),
    (lambda: check_rate_limit(5, 5), True),
])
def test_every_failing_gate_has_a_reason(gate_call, expected_failed):
    result = gate_call()
    assert result.passed is not expected_failed
    assert result.reason is not None
    assert len(result.reason) > 0
