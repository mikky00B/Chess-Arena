"""Signal handlers for profile creation, ratings, and payout signatures."""

import logging
import os

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .blockchain_utils import generate_draw_signature, generate_winner_signature
from .models import Game, Profile
from .utils import calculate_elo

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Game)
def update_rankings_on_game_end(sender, instance, **kwargs):
    if instance.is_active:
        return
    if getattr(instance, "_outcome_processed", False):
        return
    if not instance.white_player or not instance.black_player:
        return

    white_profile = Profile.objects.get(user=instance.white_player)
    black_profile = Profile.objects.get(user=instance.black_player)

    if instance.winner == instance.white_player:
        score_white, score_black = 1, 0
    elif instance.winner == instance.black_player:
        score_white, score_black = 0, 1
    else:
        score_white, score_black = 0.5, 0.5

    white_profile.rating = calculate_elo(white_profile.rating, black_profile.rating, score_white)
    black_profile.rating = calculate_elo(black_profile.rating, white_profile.rating, score_black)
    white_profile.save(update_fields=["rating"])
    black_profile.save(update_fields=["rating"])

    is_test_runtime = settings.ENVIRONMENT == "test" or bool(os.getenv("PYTEST_CURRENT_TEST"))
    if not is_test_runtime and instance.bet_amount and instance.bet_amount > 0:
        try:
            instance._outcome_processed = True
            if instance.winner:
                winner_profile = Profile.objects.get(user=instance.winner)
                if winner_profile.ethereum_address:
                    v, r, s = generate_winner_signature(instance.id, winner_profile.ethereum_address)
                else:
                    logger.warning("Winner has no Ethereum address. Game %s", instance.id)
                    instance._outcome_processed = True
                    return
            else:
                v, r, s = generate_draw_signature(instance.id)

            instance.signature_v = v
            instance.signature_r = r
            instance.signature_s = s
            instance.save(update_fields=["signature_v", "signature_r", "signature_s"])
        except Exception as exc:
            logger.error("Error generating blockchain signature for game %s: %s", instance.id, exc, exc_info=True)
            instance._outcome_processed = True
            return

    instance._outcome_processed = True


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
