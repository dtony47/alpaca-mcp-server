"""Trailing-stop calculator for the majors leg.

Pure functions; all money math is Decimal.
"""

from decimal import Decimal

INITIAL_STOP_PCT = Decimal("0.07")
TRAIL_BAND_DEFAULT = Decimal("0.10")
TRAIL_BAND_15 = Decimal("0.07")
TRAIL_BAND_20 = Decimal("0.05")
THRESHOLD_15 = Decimal("0.15")
THRESHOLD_20 = Decimal("0.20")
MIN_DISTANCE_FROM_PRICE = Decimal("0.03")


def initial_stop(entry: Decimal) -> Decimal:
    """Return the initial hard stop: 7% below entry."""
    if entry <= 0:
        raise ValueError(f"entry must be positive; got {entry}")
    return (entry * (Decimal("1") - INITIAL_STOP_PCT)).quantize(Decimal("0.01"))


def _trail_band(gain_pct: Decimal) -> Decimal | None:
    if gain_pct >= THRESHOLD_20:
        return TRAIL_BAND_20
    if gain_pct >= THRESHOLD_15:
        return TRAIL_BAND_15
    return None


def compute_new_stop(
    entry: Decimal,
    current_price: Decimal,
    current_stop: Decimal,
) -> Decimal | None:
    """Return a tightened stop, or None if no change is warranted."""
    if entry <= 0 or current_price <= 0 or current_stop < 0:
        raise ValueError(
            f"invalid inputs: entry={entry}, current_price={current_price}, "
            f"current_stop={current_stop}"
        )

    gain_pct = (current_price - entry) / entry
    band = _trail_band(gain_pct)
    if band is None:
        return None

    desired = (current_price * (Decimal("1") - band)).quantize(Decimal("0.01"))

    if desired <= current_stop:
        return None

    distance_from_price = (current_price - desired) / current_price
    if distance_from_price < MIN_DISTANCE_FROM_PRICE:
        return None

    return desired
