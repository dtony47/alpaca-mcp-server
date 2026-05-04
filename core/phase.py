"""Phase reader. Parses memory/PHASE.md to determine current phase.

Fail-safe to "paper" (the safest phase) on missing file, malformed file,
or unknown phase value.
"""

import re
from pathlib import Path

from core.types import VALID_PHASES, Phase

_PHASE_LINE = re.compile(r"^Phase:\s*(\w+)\s*$", re.MULTILINE)


def current_phase(path: Path) -> Phase:
    """Read the current phase from path. Fail-safe to 'paper'."""
    try:
        content = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return "paper"

    match = _PHASE_LINE.search(content)
    if not match:
        return "paper"

    value = match.group(1).strip()
    if value in VALID_PHASES:
        return value  # type: ignore[return-value]
    return "paper"
