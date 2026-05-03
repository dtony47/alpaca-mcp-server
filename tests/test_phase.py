from pathlib import Path

from core.phase import current_phase


def test_current_phase_paper(tmp_path: Path):
    p = tmp_path / "PHASE.md"
    p.write_text("# Current Phase\n\nPhase: paper\n\nHistory:\n")
    assert current_phase(p) == "paper"


def test_current_phase_live_25(tmp_path: Path):
    p = tmp_path / "PHASE.md"
    p.write_text("Phase: live_25\n")
    assert current_phase(p) == "live_25"


def test_current_phase_live_50(tmp_path: Path):
    p = tmp_path / "PHASE.md"
    p.write_text("Phase: live_50\n")
    assert current_phase(p) == "live_50"


def test_current_phase_live_100(tmp_path: Path):
    p = tmp_path / "PHASE.md"
    p.write_text("Phase: live_100\n")
    assert current_phase(p) == "live_100"


def test_current_phase_missing_file_returns_paper(tmp_path: Path):
    p = tmp_path / "missing.md"
    assert current_phase(p) == "paper"


def test_current_phase_malformed_returns_paper(tmp_path: Path):
    p = tmp_path / "PHASE.md"
    p.write_text("garbage with no phase line\n")
    assert current_phase(p) == "paper"


def test_current_phase_unknown_value_returns_paper(tmp_path: Path):
    p = tmp_path / "PHASE.md"
    p.write_text("Phase: yolo_max\n")
    assert current_phase(p) == "paper"
