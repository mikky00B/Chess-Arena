from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET

from .blockchain_utils import get_network_info
from .fairplay import analyze_game_moves
from .models import Game


@require_GET
def health_live(request):
    return JsonResponse({"status": "ok", "service": "djangoChess"})


@require_GET
def health_ready(request):
    checks = {"database": False, "redis_configured": False}

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = True
    except Exception:
        checks["database"] = False

    checks["redis_configured"] = bool(settings.CHANNEL_LAYERS.get("default"))

    ok = all(checks.values())
    return JsonResponse(
        {"status": "ok" if ok else "degraded", "checks": checks},
        status=200 if ok else 503,
    )


@require_GET
def network_info(request):
    info = get_network_info()
    return JsonResponse(info, status=200 if info.get("success") else 503)


@login_required
@require_GET
def fairplay_report(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    if request.user not in [game.white_player, game.black_player] and not request.user.is_staff:
        return JsonResponse({"success": False, "message": "Not authorized"}, status=403)

    moves = list(game.moves.order_by("move_number"))
    report = analyze_game_moves(moves)
    return JsonResponse({"success": True, "game_id": game.id, "report": report})
