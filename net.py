"""
net.py — Small HTTP helper with retries + timeouts.

Purpose:
  - make external API calls more reliable (Polygon, DexScreener, CoinGecko, Alpaca news)
  - provide a single place to tune timeouts/backoff
"""

from __future__ import annotations

import time
from typing import Any, Optional

import requests


class HttpError(RuntimeError):
    pass


def get_json(
    url: str,
    *,
    params: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 12,
    retries: int = 3,
    backoff_s: float = 0.8,
) -> dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_err = e
            if attempt >= retries:
                break
            time.sleep(backoff_s * (2**attempt))
    raise HttpError(f"GET failed after {retries+1} attempts: {url} ({last_err})")

