"""Position sizing functions. Pure — take inputs, return Decimal sizes."""

from decimal import Decimal


def position_size_majors(
    equity: Decimal,
    available_cash: Decimal,
    intended_pct: Decimal,
    max_pct: Decimal,
) -> Decimal:
    """Compute position cost (USD) for a majors-leg trade.

    Capped by the smaller of: intended_pct, max_pct, available_cash.
    """
    if equity < 0 or available_cash < 0 or intended_pct < 0 or max_pct < 0:
        raise ValueError("All sizing inputs must be non-negative")

    capped_pct = min(intended_pct, max_pct)
    by_pct = equity * capped_pct
    return min(by_pct, available_cash)


def position_size_meme(
    equity: Decimal,
    available_cash: Decimal,
    pool_liquidity_usd: Decimal,
    max_position_pct: Decimal,
    max_pool_pct: Decimal,
) -> Decimal:
    """Compute position cost (USD) for a memecoin-leg trade.

    Capped by the smaller of:
      - max_position_pct of equity
      - max_pool_pct of pool liquidity (slippage protection)
      - available_cash
    """
    if pool_liquidity_usd <= 0:
        raise ValueError("pool_liquidity_usd must be positive")
    if equity < 0 or available_cash < 0 or max_position_pct < 0 or max_pool_pct < 0:
        raise ValueError("All sizing inputs must be non-negative")

    by_equity = equity * max_position_pct
    by_pool = pool_liquidity_usd * max_pool_pct
    return min(by_equity, by_pool, available_cash)
