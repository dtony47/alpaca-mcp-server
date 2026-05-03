from pathlib import Path

import pytest

from core.kill_switch import current_state, set_state, should_auto_pause


def test_current_state_active(tmp_path: Path):
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("# Kill Switch\n\nState: ACTIVE\n\nHistory:\n- 2026-05-03: init\n")
    assert current_state(p) == "ACTIVE"


def test_current_state_paused(tmp_path: Path):
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("# Kill Switch\n\nState: PAUSED\n\nHistory:\n")
    assert current_state(p) == "PAUSED"


def test_current_state_killed(tmp_path: Path):
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("# Kill Switch\n\nState: KILLED\n")
    assert current_state(p) == "KILLED"


def test_current_state_missing_file_returns_killed(tmp_path: Path):
    """Defensive default: if file is missing, assume KILLED (fail-safe)."""
    p = tmp_path / "missing.md"
    assert current_state(p) == "KILLED"


def test_current_state_unparseable_returns_killed(tmp_path: Path):
    """Defensive default: if file is malformed, assume KILLED."""
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("garbage\n\nno state line here\n")
    assert current_state(p) == "KILLED"


def test_current_state_invalid_value_returns_killed(tmp_path: Path):
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("# Kill Switch\n\nState: WEIRD\n")
    assert current_state(p) == "KILLED"


def test_set_state_writes_new_state_and_appends_history(tmp_path: Path):
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("# Kill Switch\n\nState: ACTIVE\n\nHistory:\n- 2026-05-03: init\n")
    set_state(p, new_state="PAUSED", reason="daily loss limit hit")
    content = p.read_text()
    assert "State: PAUSED" in content
    assert "daily loss limit hit" in content
    assert "2026-05-03: init" in content  # original history preserved


def test_set_state_rejects_invalid_state(tmp_path: Path):
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("State: ACTIVE\n")
    with pytest.raises(ValueError):
        set_state(p, new_state="YOLO", reason="test")


def test_set_state_creates_file_when_missing(tmp_path: Path):
    """set_state on a nonexistent file should create it with the new state."""
    p = tmp_path / "nonexistent.md"
    set_state(p, new_state="KILLED", reason="emergency stop")
    content = p.read_text()
    assert "State: KILLED" in content
    assert "emergency stop" in content


def test_set_state_appends_state_when_no_state_line(tmp_path: Path):
    """If the file exists but has no State: line, one should be appended."""
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("# Kill Switch\n\nHistory:\n- 2026-05-03: init\n")
    set_state(p, new_state="PAUSED", reason="test no-state-line")
    content = p.read_text()
    assert "State: PAUSED" in content
    assert "test no-state-line" in content


def test_set_state_adds_history_section_when_absent(tmp_path: Path):
    """If no History: section exists, one should be added along with the entry."""
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("# Kill Switch\n\nState: ACTIVE\n")
    set_state(p, new_state="PAUSED", reason="no history section")
    content = p.read_text()
    assert "State: PAUSED" in content
    assert "History:" in content
    assert "no history section" in content


def test_should_auto_pause_within_limit_returns_false():
    pause, reason = should_auto_pause(
        day_pl_pct_signed=-0.02,
        phase_pl_pct_signed=-0.10,
        consecutive_meme_losses=1,
        daily_pause_threshold=0.05,
        phase_halt_threshold=0.20,
        meme_loss_pause_threshold=3,
    )
    assert pause is False and reason is None


def test_should_auto_pause_daily_loss_triggers():
    pause, reason = should_auto_pause(
        day_pl_pct_signed=-0.06,
        phase_pl_pct_signed=-0.05,
        consecutive_meme_losses=0,
        daily_pause_threshold=0.05,
        phase_halt_threshold=0.20,
        meme_loss_pause_threshold=3,
    )
    assert pause is True and "daily" in (reason or "").lower()


def test_should_auto_pause_phase_drawdown_triggers():
    pause, reason = should_auto_pause(
        day_pl_pct_signed=0.0,
        phase_pl_pct_signed=-0.25,
        consecutive_meme_losses=0,
        daily_pause_threshold=0.05,
        phase_halt_threshold=0.20,
        meme_loss_pause_threshold=3,
    )
    assert pause is True and "drawdown" in (reason or "").lower()


def test_should_auto_pause_meme_loss_streak_triggers():
    pause, reason = should_auto_pause(
        day_pl_pct_signed=0.0,
        phase_pl_pct_signed=0.0,
        consecutive_meme_losses=3,
        daily_pause_threshold=0.05,
        phase_halt_threshold=0.20,
        meme_loss_pause_threshold=3,
    )
    assert pause is True and "meme" in (reason or "").lower()


def test_set_state_rejects_empty_reason(tmp_path: Path):
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("State: ACTIVE\n")
    with pytest.raises(ValueError, match="reason"):
        set_state(p, new_state="PAUSED", reason="")


def test_set_state_rejects_whitespace_only_reason(tmp_path: Path):
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("State: ACTIVE\n")
    with pytest.raises(ValueError, match="reason"):
        set_state(p, new_state="PAUSED", reason="   \n\t  ")


def test_set_state_does_not_treat_substring_history_as_header(tmp_path: Path):
    """A reason mentioning 'History:' shouldn't fool the History-section detector."""
    p = tmp_path / "KILL-SWITCH.md"
    # File has no real History header, but body text contains "History:"
    p.write_text("# Kill Switch\n\nState: ACTIVE\n\nNote: see History: archive\n")
    set_state(p, new_state="PAUSED", reason="test transition")
    content = p.read_text()
    # A new History: header must have been added (because no real one existed)
    assert content.count("History:") == 2  # one in body text, one as new header
    # The new history line should be under a real header, not glued onto the prose
    history_section_index = content.rfind("History:\n")
    history_line_index = content.rfind("- ")
    assert history_section_index < history_line_index


def test_set_state_atomicity_no_temp_file_left_on_success(tmp_path: Path):
    """After a successful write, the .tmp file should not exist."""
    p = tmp_path / "KILL-SWITCH.md"
    p.write_text("State: ACTIVE\n")
    set_state(p, new_state="PAUSED", reason="test")
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0
