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
