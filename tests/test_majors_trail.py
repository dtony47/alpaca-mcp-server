"""Tests for majors.trail -- trailing-stop calculator."""

from decimal import Decimal

import pytest

from majors.trail import MIN_DISTANCE_FROM_PRICE, compute_new_stop, initial_stop


def test_initial_stop_is_minus_7_pct():
    entry = Decimal("100")

    assert initial_stop(entry) == Decimal("93.00")


def test_initial_stop_rejects_non_positive_entry():
    with pytest.raises(ValueError, match="positive"):
        initial_stop(Decimal("0"))
    with pytest.raises(ValueError, match="positive"):
        initial_stop(Decimal("-5"))


def test_no_change_when_price_below_plus_15():
    entry = Decimal("100")
    current_price = Decimal("110")
    current_stop = entry * Decimal("0.90")

    new = compute_new_stop(entry=entry, current_price=current_price, current_stop=current_stop)

    assert new is None


def test_tightens_to_7pct_band_at_plus_15():
    entry = Decimal("100")
    current_price = Decimal("116")
    current_stop = Decimal("93.00")

    new = compute_new_stop(entry=entry, current_price=current_price, current_stop=current_stop)

    assert new is not None
    assert new == Decimal("107.88")


def test_tightens_to_5pct_band_at_plus_20():
    entry = Decimal("100")
    current_price = Decimal("125")
    current_stop = Decimal("107.88")

    new = compute_new_stop(entry=entry, current_price=current_price, current_stop=current_stop)

    assert new is not None
    assert new == Decimal("118.75")


def test_never_moves_stop_down():
    entry = Decimal("100")
    current_price = Decimal("125")
    current_stop = Decimal("123.00")

    new = compute_new_stop(entry=entry, current_price=current_price, current_stop=current_stop)

    assert new is None


def test_min_distance_constant_documents_3pct_rule():
    assert Decimal("0.03") == MIN_DISTANCE_FROM_PRICE


def test_rejects_invalid_inputs():
    with pytest.raises(ValueError):
        compute_new_stop(
            entry=Decimal("0"),
            current_price=Decimal("100"),
            current_stop=Decimal("90"),
        )
    with pytest.raises(ValueError):
        compute_new_stop(
            entry=Decimal("100"),
            current_price=Decimal("0"),
            current_stop=Decimal("90"),
        )
    with pytest.raises(ValueError):
        compute_new_stop(
            entry=Decimal("100"),
            current_price=Decimal("100"),
            current_stop=Decimal("-1"),
        )
