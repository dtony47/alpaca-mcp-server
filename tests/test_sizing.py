from decimal import Decimal

import pytest

from core.sizing import position_size_majors, position_size_meme


# ---------- majors ----------

def test_majors_sizing_simple_pct():
    """20% of $10k equity = $2k position cost"""
    size = position_size_majors(
        equity=Decimal("10000"),
        available_cash=Decimal("10000"),
        intended_pct=Decimal("0.20"),
        max_pct=Decimal("0.20"),
    )
    assert size == Decimal("2000")


def test_majors_sizing_capped_by_max_pct():
    """Intended 30% but max is 20% → capped at 20%"""
    size = position_size_majors(
        equity=Decimal("10000"),
        available_cash=Decimal("10000"),
        intended_pct=Decimal("0.30"),
        max_pct=Decimal("0.20"),
    )
    assert size == Decimal("2000")


def test_majors_sizing_capped_by_cash():
    """Want $2k but only $500 cash available → $500"""
    size = position_size_majors(
        equity=Decimal("10000"),
        available_cash=Decimal("500"),
        intended_pct=Decimal("0.20"),
        max_pct=Decimal("0.20"),
    )
    assert size == Decimal("500")


def test_majors_sizing_zero_cash():
    size = position_size_majors(
        equity=Decimal("10000"),
        available_cash=Decimal("0"),
        intended_pct=Decimal("0.20"),
        max_pct=Decimal("0.20"),
    )
    assert size == Decimal("0")


def test_majors_sizing_rejects_negative_inputs():
    with pytest.raises(ValueError):
        position_size_majors(
            equity=Decimal("-1"),
            available_cash=Decimal("100"),
            intended_pct=Decimal("0.20"),
            max_pct=Decimal("0.20"),
        )


# ---------- meme ----------

def test_meme_sizing_pct_of_equity():
    """3% of $10k = $300"""
    size = position_size_meme(
        equity=Decimal("10000"),
        available_cash=Decimal("10000"),
        pool_liquidity_usd=Decimal("500000"),
        max_position_pct=Decimal("0.03"),
        max_pool_pct=Decimal("0.005"),
    )
    assert size == Decimal("300")


def test_meme_sizing_capped_by_pool_liquidity():
    """3% of $10k = $300, but 0.5% of $40k pool = $200 → $200"""
    size = position_size_meme(
        equity=Decimal("10000"),
        available_cash=Decimal("10000"),
        pool_liquidity_usd=Decimal("40000"),
        max_position_pct=Decimal("0.03"),
        max_pool_pct=Decimal("0.005"),
    )
    assert size == Decimal("200")


def test_meme_sizing_capped_by_cash():
    size = position_size_meme(
        equity=Decimal("10000"),
        available_cash=Decimal("50"),
        pool_liquidity_usd=Decimal("500000"),
        max_position_pct=Decimal("0.03"),
        max_pool_pct=Decimal("0.005"),
    )
    assert size == Decimal("50")


def test_meme_sizing_rejects_zero_pool():
    with pytest.raises(ValueError):
        position_size_meme(
            equity=Decimal("10000"),
            available_cash=Decimal("100"),
            pool_liquidity_usd=Decimal("0"),
            max_position_pct=Decimal("0.03"),
            max_pool_pct=Decimal("0.005"),
        )
