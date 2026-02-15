"""Manual signature debug helper.

Run with:
python manage.py shell -c "from main.test_signature import debug_latest_game_signature; debug_latest_game_signature()"
"""

from django.conf import settings

from main.blockchain_utils import (
    generate_winner_signature,
    get_chess_contract,
    get_judge_account,
)
from main.models import Game

__test__ = False


def debug_latest_game_signature():
    game = Game.objects.filter(is_active=False, winner__isnull=False).order_by("-id").first()
    if not game:
        print("No completed games found.")
        return

    contract = get_chess_contract()
    judge = get_judge_account()
    contract_judge = contract.functions.judge_address().call()
    winner_address = game.winner.profile.ethereum_address
    v, r, s = generate_winner_signature(game.id, winner_address)

    print(f"Game ID: {game.id}")
    print(f"Winner: {game.winner.username}")
    print(f"Winner address: {winner_address}")
    print(f"Contract address: {settings.CHESS_CONTRACT_ADDRESS}")
    print(f"Judge in contract: {contract_judge}")
    print(f"Judge in env: {judge.address}")
    print(f"Signature v: {v}")
    print(f"Signature r: {r}")
    print(f"Signature s: {s}")
