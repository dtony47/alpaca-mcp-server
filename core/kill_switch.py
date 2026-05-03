"""Kill-switch read/write + auto-pause logic.

The kill switch is the master safety lever. State lives in
memory/KILL-SWITCH.md as a parseable markdown file. If the file is
missing or unparseable, we fail-safe to KILLED.
"""

import os
import re
from datetime import date
from pathlib import Path

from core.types import KillSwitchState

VALID_STATES: set[KillSwitchState] = {"ACTIVE", "PAUSED", "KILLED"}

_STATE_LINE = re.compile(r"^State:\s*(\w+)\s*$", re.MULTILINE)
_HISTORY_HEADER = re.compile(r"^History:\s*$", re.MULTILINE)


def current_state(path: Path) -> KillSwitchState:
    """Read the current kill-switch state from path. Fail-safe to KILLED."""
    try:
        content = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return "KILLED"

    match = _STATE_LINE.search(content)
    if not match:
        return "KILLED"

    value = match.group(1).strip().upper()
    if value in VALID_STATES:
        return value  # type: ignore[return-value]
    return "KILLED"


def set_state(path: Path, new_state: str, reason: str) -> None:
    """Write a new kill-switch state to path, appending a history entry.

    Raises ValueError if new_state is not a valid state or reason is empty.
    The write is atomic (write-temp-then-rename) to protect the audit log.
    """
    if new_state not in VALID_STATES:
        raise ValueError(f"Invalid state '{new_state}'; valid: {sorted(VALID_STATES)}")

    if not reason.strip():
        raise ValueError("reason is required (cannot be empty)")

    today = date.today().isoformat()

    try:
        content = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        content = "# Kill Switch\n\nState: ACTIVE\n\nHistory:\n"

    # Replace the State line
    new_content = _STATE_LINE.sub(f"State: {new_state}", content)
    if new_content == content:
        # No State line existed; append one
        new_content = content.rstrip() + f"\n\nState: {new_state}\n\nHistory:\n"

    # Append history line if a real History: header exists; else add one.
    # Use anchored regex to avoid matching "History:" embedded in body text.
    history_line = f"- {today}: {new_state} — {reason}\n"
    if _HISTORY_HEADER.search(new_content):
        new_content = new_content.rstrip() + "\n" + history_line
    else:
        new_content = new_content.rstrip() + "\n\nHistory:\n" + history_line

    # Atomic write: write to a .tmp sibling then rename so a mid-write crash
    # cannot corrupt the audit log.
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    os.replace(tmp_path, path)  # atomic on POSIX and Windows


def should_auto_pause(
    day_pl_pct_signed: float,
    phase_pl_pct_signed: float,
    consecutive_meme_losses: int,
    daily_pause_threshold: float,
    phase_halt_threshold: float,
    meme_loss_pause_threshold: int,
) -> tuple[bool, str | None]:
    """Decide whether the bot should auto-pause itself.

    Inputs are signed percentages (dimensionless ratios), not money values —
    `float` is intentional and consistent with the rest of the percentage-handling
    code paths. Money math elsewhere uses `Decimal`.

    -0.05 == -5%. Thresholds are positive magnitudes: 0.05 == "pause when loss exceeds 5%".
    """
    if day_pl_pct_signed <= -daily_pause_threshold:
        return True, f"daily loss {day_pl_pct_signed:.2%} ≤ -{daily_pause_threshold:.2%}"
    if phase_pl_pct_signed <= -phase_halt_threshold:
        return True, f"phase drawdown {phase_pl_pct_signed:.2%} ≤ -{phase_halt_threshold:.2%}"
    if consecutive_meme_losses >= meme_loss_pause_threshold:
        return (
            True,
            f"meme loss streak {consecutive_meme_losses} ≥ {meme_loss_pause_threshold}",
        )
    return False, None
