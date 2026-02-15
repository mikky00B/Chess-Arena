from statistics import mean, pstdev


def analyze_game_moves(moves):
    move_count = len(moves)
    if move_count == 0:
        return {"move_count": 0, "risk": "unknown", "signals": []}

    think_times = [max(0.0, float(m.think_time_seconds or 0.0)) for m in moves]
    avg_time = mean(think_times)
    std_time = pstdev(think_times) if move_count > 1 else 0.0

    signals = []
    if move_count >= 20 and avg_time < 1.2:
        signals.append("very_low_average_think_time")
    if move_count >= 20 and std_time < 0.35:
        signals.append("unusually_low_time_variance")

    risk = "low"
    if len(signals) == 1:
        risk = "medium"
    elif len(signals) >= 2:
        risk = "high"

    return {
        "move_count": move_count,
        "avg_think_time_seconds": round(avg_time, 3),
        "std_think_time_seconds": round(std_time, 3),
        "risk": risk,
        "signals": signals,
    }
