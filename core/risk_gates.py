"""Pre-trade risk gates. Pure functions; each returns a GateResult.

The composition function `run_universal_gates` evaluates gates in order and
SHORT-CIRCUITS on the first failure. This is intentional: if the kill switch
is on, we don't care about the rest.

Every gate function is independently testable and reusable.
"""

from collections.abc import Callable
from decimal import Decimal, InvalidOperation

from core.types import AccountState, GateResult, OrderIntent

VALID_KILL_SWITCH_STATES = {"ACTIVE", "PAUSED", "KILLED"}
VALID_PHASES = {"paper", "live_25", "live_50", "live_100"}


def check_kill_switch(state: str) -> GateResult:
    if state == "ACTIVE":
        return GateResult(passed=True, gate_name="kill_switch", reason=None)
    if state in VALID_KILL_SWITCH_STATES:
        return GateResult(
            passed=False,
            gate_name="kill_switch",
            reason=f"Kill switch is {state}; new entries blocked",
        )
    return GateResult(
        passed=False,
        gate_name="kill_switch",
        reason=f"Unknown kill switch state '{state}' (corrupted state file?); failing closed",
    )


def check_phase_valid(phase: str) -> GateResult:
    if phase in VALID_PHASES:
        return GateResult(passed=True, gate_name="phase", reason=None)
    return GateResult(
        passed=False,
        gate_name="phase",
        reason=f"Unknown phase '{phase}'; valid: {sorted(VALID_PHASES)}",
    )


def check_daily_loss_limit(day_pl_pct: Decimal, limit_pct: Decimal) -> GateResult:
    """Day P&L must be > -limit_pct (i.e. losses smaller than limit)."""
    if limit_pct < 0:
        return GateResult(
            passed=False,
            gate_name="daily_loss_limit",
            reason=f"invalid limit_pct {limit_pct} (must be non-negative)",
        )
    try:
        if day_pl_pct > -limit_pct:
            return GateResult(passed=True, gate_name="daily_loss_limit", reason=None)
        return GateResult(
            passed=False,
            gate_name="daily_loss_limit",
            reason=f"Day P&L {day_pl_pct:.2%} exceeds limit -{limit_pct:.2%}",
        )
    except (InvalidOperation, ArithmeticError) as e:
        return GateResult(
            passed=False,
            gate_name="daily_loss_limit",
            reason=f"invalid input (NaN/arithmetic): {e}",
        )


def check_drawdown_limit(phase_pl_pct: Decimal, limit_pct: Decimal) -> GateResult:
    if limit_pct < 0:
        return GateResult(
            passed=False,
            gate_name="drawdown_limit",
            reason=f"invalid limit_pct {limit_pct} (must be non-negative)",
        )
    try:
        if phase_pl_pct > -limit_pct:
            return GateResult(passed=True, gate_name="drawdown_limit", reason=None)
        return GateResult(
            passed=False,
            gate_name="drawdown_limit",
            reason=f"Phase drawdown {phase_pl_pct:.2%} exceeds limit -{limit_pct:.2%}",
        )
    except (InvalidOperation, ArithmeticError) as e:
        return GateResult(
            passed=False,
            gate_name="drawdown_limit",
            reason=f"invalid input (NaN/arithmetic): {e}",
        )


def check_position_count(current: int, max_allowed: int) -> GateResult:
    if current < 0 or max_allowed < 0:
        return GateResult(
            passed=False,
            gate_name="position_count",
            reason=f"invalid inputs (negative): current={current}, max={max_allowed}",
        )
    if current < max_allowed:
        return GateResult(passed=True, gate_name="position_count", reason=None)
    return GateResult(
        passed=False,
        gate_name="position_count",
        reason=f"Already at {current}/{max_allowed} open positions",
    )


def check_position_size(
    intended_cost_usd: Decimal, equity: Decimal, max_pct: Decimal
) -> GateResult:
    try:
        if intended_cost_usd < 0 or equity <= 0 or max_pct < 0:
            return GateResult(
                passed=False,
                gate_name="position_size",
                reason=f"invalid inputs: intended={intended_cost_usd}, equity={equity}, max_pct={max_pct}",
            )
        max_cost = equity * max_pct
        if intended_cost_usd <= max_cost:
            return GateResult(passed=True, gate_name="position_size", reason=None)
        return GateResult(
            passed=False,
            gate_name="position_size",
            reason=f"Intended ${intended_cost_usd} exceeds max ${max_cost} ({max_pct:.0%} of equity)",
        )
    except (InvalidOperation, ArithmeticError) as e:
        return GateResult(
            passed=False,
            gate_name="position_size",
            reason=f"invalid input (NaN/arithmetic): {e}",
        )


def check_available_cash(intended_cost_usd: Decimal, available: Decimal) -> GateResult:
    try:
        if intended_cost_usd < 0 or available < 0:
            return GateResult(
                passed=False,
                gate_name="available_cash",
                reason=f"invalid inputs: intended={intended_cost_usd}, available={available}",
            )
        if intended_cost_usd <= available:
            return GateResult(passed=True, gate_name="available_cash", reason=None)
        return GateResult(
            passed=False,
            gate_name="available_cash",
            reason=f"Intended ${intended_cost_usd} exceeds available ${available}",
        )
    except (InvalidOperation, ArithmeticError) as e:
        return GateResult(
            passed=False,
            gate_name="available_cash",
            reason=f"invalid input (NaN/arithmetic): {e}",
        )


def check_rate_limit(trades_last_hour: int, max_per_hour: int) -> GateResult:
    if trades_last_hour < 0 or max_per_hour < 0:
        return GateResult(
            passed=False,
            gate_name="rate_limit",
            reason=f"invalid inputs: trades={trades_last_hour}, max={max_per_hour}",
        )
    if trades_last_hour < max_per_hour:
        return GateResult(passed=True, gate_name="rate_limit", reason=None)
    return GateResult(
        passed=False,
        gate_name="rate_limit",
        reason=f"Already executed {trades_last_hour}/{max_per_hour} trades this hour",
    )


def run_universal_gates(
    kill_switch_state: str,
    phase: str,
    state: AccountState,
    intent: OrderIntent,
    daily_loss_limit_pct: Decimal,
    drawdown_limit_pct: Decimal,
    max_positions: int,
    max_position_pct: Decimal,
    rate_limit_per_hour: int,
) -> list[GateResult]:
    """Run all universal gates in order. SHORT-CIRCUITS on first failure.

    Returns list of GateResult; if any fail, the trade is rejected.
    The list always contains at least one element. If empty, that's a bug.
    """
    gates: list[Callable[[], GateResult]] = [
        lambda: check_kill_switch(kill_switch_state),
        lambda: check_phase_valid(phase),
        lambda: check_daily_loss_limit(state.day_pl_pct, daily_loss_limit_pct),
        lambda: check_drawdown_limit(state.phase_pl_pct, drawdown_limit_pct),
        lambda: check_position_count(state.open_positions_count, max_positions),
        lambda: check_position_size(intent.intended_cost_usd, state.equity, max_position_pct),
        lambda: check_available_cash(intent.intended_cost_usd, state.cash),
        lambda: check_rate_limit(state.trades_last_hour, rate_limit_per_hour),
    ]

    results: list[GateResult] = []
    for gate in gates:
        result = gate()
        results.append(result)
        if not result.passed:
            break  # short-circuit on first failure
    return results
