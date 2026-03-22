from django.utils import timezone


def sync_game_clock(game, now=None):
    if now is None:
        now = timezone.now()

    if not game.is_active or not game.black_player or not game.last_move_timestamp:
        return {"changed": False, "elapsed": 0.0, "timed_out": False}

    elapsed = max(0.0, (now - game.last_move_timestamp).total_seconds())
    if elapsed <= 0:
        return {"changed": False, "elapsed": 0.0, "timed_out": False}

    current_turn_before_tick = game.current_fen.split()[1]
    if current_turn_before_tick == "w":
        game.white_time = max(0.0, float(game.white_time) - elapsed)
    else:
        game.black_time = max(0.0, float(game.black_time) - elapsed)

    game.last_move_timestamp = now
    timed_out = False
    if game.white_time <= 0:
        game.is_active = False
        game.winner = game.black_player
        game.draw_offered_by = None
        timed_out = True
    elif game.black_time <= 0:
        game.is_active = False
        game.winner = game.white_player
        game.draw_offered_by = None
        timed_out = True

    return {"changed": True, "elapsed": elapsed, "timed_out": timed_out}
