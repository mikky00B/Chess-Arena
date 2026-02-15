from types import SimpleNamespace

from main.fairplay import analyze_game_moves


def test_fairplay_empty_game():
    report = analyze_game_moves([])
    assert report["risk"] == "unknown"


def test_fairplay_high_risk_pattern():
    moves = [SimpleNamespace(think_time_seconds=0.8) for _ in range(24)]
    report = analyze_game_moves(moves)
    assert report["risk"] in {"medium", "high"}
    assert "very_low_average_think_time" in report["signals"]
