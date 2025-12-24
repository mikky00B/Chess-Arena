from django.shortcuts import render, get_object_or_404, redirect
from .models import Game, Profile
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login


def signup(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("lobby")
    else:
        form = UserCreationForm()
    return render(request, "main/signup.html", {"form": form})


@login_required
def game_detail(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    return render(request, "main/board2.html", {"game": game})


@login_required
def lobby(request):
    open_games = Game.objects.filter(black_player__isnull=True, is_active=True).exclude(
        white_player=request.user
    )
    my_games = (
        Game.objects.filter(is_active=True)
        .filter(Q(white_player=request.user) | Q(black_player=request.user))
        .distinct()
    )

    # Get Top 10 Players
    leaderboard = Profile.objects.order_by("-rating")[:10]

    return render(
        request,
        "main/lobby.html",
        {"open_games": open_games, "my_games": my_games, "leaderboard": leaderboard},
    )


@login_required
def create_game(request):
    existing_game = Game.objects.filter(
        white_player=request.user, is_active=True, black_player__isnull=True
    ).first()
    if existing_game:
        return redirect("game_detail", game_id=existing_game.id)
    new_game = Game.objects.create(white_player=request.user)
    return redirect("game_detail", game_id=new_game.id)


@login_required
def join_game(request, game_id):
    game = get_object_or_404(Game, id=game_id)
    if game.white_player != request.user and game.black_player is None:
        game.black_player = request.user
        game.save()  # This is critical!
    return redirect("game_detail", game_id=game.id)
