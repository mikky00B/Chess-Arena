from django.shortcuts import render, get_object_or_404, redirect
from .models import Game, Profile
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, authenticate
from django.db import transaction
from django.utils import timezone
from django.contrib import messages


def signin(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("lobby")
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "main/login.html")


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

    # Check if user is part of this game
    if request.user not in [game.white_player, game.black_player]:
        messages.error(request, "You are not part of this game.")
        return redirect("lobby")

    from django.conf import settings

    context = {
        "game": game,
        "user_ethereum_address": request.user.profile.ethereum_address,
        "CHESS_CONTRACT_ADDRESS": settings.CHESS_CONTRACT_ADDRESS,
        "BLOCKCHAIN_RPC_URL": settings.BLOCKCHAIN_RPC_URL,
    }
    return render(request, "main/board2.html", context)


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
    leaderboard = Profile.objects.order_by("-rating")[:10]

    context = {
        "open_games": open_games,
        "my_games": my_games,
        "leaderboard": leaderboard,
        "user_ethereum_address": request.user.profile.ethereum_address,
    }
    return render(request, "main/lobby.html", context)


@login_required
def lobby_list_partial(request):
    open_games = Game.objects.filter(black_player__isnull=True, is_active=True).exclude(
        white_player=request.user
    )
    return render(request, "main/partials/game_list.html", {"open_games": open_games})


@login_required
def create_game(request):
    """Create a new game with optional bet amount"""

    # Check if user has Ethereum address set
    if not request.user.profile.ethereum_address:
        messages.warning(
            request, "Please set your Ethereum address in your profile first."
        )
        return redirect("set_ethereum_address")

    # Check for existing open game by this user
    existing_game = Game.objects.filter(
        white_player=request.user, is_active=True, black_player__isnull=True
    ).first()

    if existing_game:
        return redirect("game_detail", game_id=existing_game.id)

    if request.method == "POST":
        bet_amount = request.POST.get("bet_amount", "0")

        try:
            bet_amount = float(bet_amount)
            if bet_amount < 0:
                messages.error(request, "Bet amount cannot be negative.")
                return redirect("lobby")
        except ValueError:
            bet_amount = 0

        # Create game with bet amount
        new_game = Game.objects.create(white_player=request.user, bet_amount=bet_amount)

        if bet_amount > 0:
            messages.info(
                request,
                f"Game created with {bet_amount} ETH bet. "
                "You and your opponent must deposit to the smart contract before playing.",
            )

        return redirect("game_detail", game_id=new_game.id)

    # GET request - show create game form
    return render(request, "main/create_game.html")


@login_required
def join_game(request, game_id):
    """Join an existing game - shows confirmation page first"""

    game = get_object_or_404(Game, id=game_id)

    # Check if user has Ethereum address set
    if not request.user.profile.ethereum_address:
        messages.warning(
            request, "Please set your Ethereum address in your profile first."
        )
        return redirect("set_ethereum_address")

    # Validation checks
    if game.white_player == request.user:
        messages.error(request, "You cannot join your own game.")
        return redirect("lobby")

    if game.black_player is not None:
        messages.error(request, "This game is already full.")
        return redirect("lobby")

    # GET request - show confirmation page
    if request.method == "GET":
        context = {
            "game": game,
            "opponent": game.white_player,
            "opponent_rating": game.white_player.profile.rating,
            "bet_amount": game.bet_amount,
        }
        return render(request, "main/join_game.html", context)

    # POST request - actually join the game
    if request.method == "POST":
        with transaction.atomic():
            game = Game.objects.select_for_update().get(id=game_id)

            # Double-check it's still available
            if game.black_player is not None:
                messages.error(request, "Someone else just joined this game.")
                return redirect("lobby")

            # Join the game
            game.black_player = request.user
            game.save()

            if game.bet_amount > 0:
                messages.info(
                    request,
                    f"You joined a game with {game.bet_amount} ETH bet. "
                    "Both players must deposit to the smart contract before playing.",
                )

            return redirect("game_detail", game_id=game.id)

    return redirect("lobby")


@login_required
def set_ethereum_address(request):
    """Allow user to set their Ethereum address"""
    if request.method == "POST":
        ethereum_address = request.POST.get("ethereum_address", "").strip()

        # Basic validation
        if not ethereum_address.startswith("0x") or len(ethereum_address) != 42:
            messages.error(request, "Invalid Ethereum address format.")
            return render(request, "main/set_address.html")

        # Check if address is already taken
        if (
            Profile.objects.filter(ethereum_address=ethereum_address)
            .exclude(user=request.user)
            .exists()
        ):
            messages.error(
                request, "This Ethereum address is already registered to another user."
            )
            return render(request, "main/set_address.html")

        # Update profile
        profile = request.user.profile
        profile.ethereum_address = ethereum_address
        profile.save()

        messages.success(request, "Ethereum address updated successfully!")
        return redirect("lobby")

    return render(
        request,
        "main/set_address.html",
        {"current_address": request.user.profile.ethereum_address},
    )


@login_required
def profile_view(request):
    """View user profile"""
    context = {
        "profile": request.user.profile,
        "games_won": Game.objects.filter(winner=request.user).count(),
        "games_played": Game.objects.filter(
            Q(white_player=request.user) | Q(black_player=request.user), is_active=False
        ).count(),
    }
    return render(request, "main/profile.html", context)
